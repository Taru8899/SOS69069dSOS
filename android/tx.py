"""Build the data for dSOS transactions. Nothing here signs or sends: the wallet app does that.

Every builder returns a dict:
    to, value_wei, value_eth, data (0x hex), params (for Etherscan Write Contract)
Contract version: dSOSSystem + dSOSOffers (one dSOS, two contracts). The contract never writes to the
SOS ledger, so no call carries a ledger record any more. Every value-moving call ends with
`expectedNonce` = redeemNonce(wallet); the wallet's current nonce is passed in as `nonce=`.
The optional "Ledger record after success" of the transaction page is kept: builders that had it
still return `rec` (intended_to, payload_hash); the app writes that record as a separate transaction.
"""
import json
import os
import re
from decimal import Decimal, InvalidOperation

import strings as S
from core import DSOS, LEDGER, enc, keccak256, selector

CREATE_SIG = "createOfferS(address,uint256,uint256)"
CREATE_A_SIG = "createOfferA(uint256,uint256,uint256)"
CREATE_B_SIG = "createOfferB(address,uint256,uint256,uint256)"
SYNC_RECORDS_SIG = "syncRecords(uint256,uint256,uint256)"
KIND_ID = {"S": 1}                   # G (=0) goes through create_gated_tx; A (=2) / B (=3) below
UNIT_WEI = 10**15
WEI_PER_ETH = 10**18
DEAD = "0x000000000000000000000000000000000000dEaD"


# ---------------------------------------------------------------- small ABI helpers
def _pad(b):
    return bytes(b) + bytes((-len(b)) % 32)


def enc_bytes(b):
    """ABI tail of a `bytes` value: length word + padded data."""
    return enc(len(b)) + _pad(b)


def enc_str(s):
    return enc_bytes(s.encode())


def rec_tuple(ph, sig=b"", meta=""):
    """ABI encoding of the dynamic tuple Rec(bytes32 payloadHash, bytes signature, string metadata)."""
    sg, mt = enc_bytes(sig), enc_str(meta)
    return ph + enc(3 * 32) + enc(3 * 32 + len(sg)) + sg + mt


def eth_text(wei):
    """Exact ETH text for a wei amount, no float rounding, no trailing zeros."""
    t = format(Decimal(int(wei)).scaleb(-18), "f")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t or "0"


def valid_address(a):
    a = (a or "").strip()
    if len(a) != 42 or not a.startswith("0x"):
        return False
    try:
        int(a[2:], 16)
    except ValueError:
        return False
    return True


def _hex(b):
    return "0x" + bytes(b).hex()


def _with_rec(build, intended_to, ph):
    """Attach the optional ledger-record info to a transaction builder `build(sig, meta)`. The
    contract ignores records now; the transaction page writes this one as its own transaction."""
    t = build(b"", "")
    t["rec"] = {"intended_to": intended_to.strip(), "payload_hash": ph, "make": lambda sig=b"", meta="": t}
    return t


def _nonce(n):
    """The wallet's current redeemNonce, passed as the last argument of every value-moving call."""
    if n is None or int(n) < 0:
        raise ValueError(S.ERR_NONCE)
    return int(n)


def _final_holder(holder):
    """What the contract stores: the zero address becomes DEAD. The contract itself is refused."""
    h = holder.strip()
    if h.lower() == DSOS:
        raise ValueError(S.ERR_HOLDER_CONTRACT)
    return DEAD if h.lower() == "0x" + "0" * 40 else h


# ---------------------------------------------------------------- PIN (same rule as the dApp)
_HEX32 = re.compile(r"^0x[0-9a-fA-F]{64}$")


def to_pin(text):
    """dApp rule: '0x' + 64 hex digits is used as it is, anything else is keccak256(utf8 text)."""
    t = (text or "").strip()
    if _HEX32.match(t):
        return bytes.fromhex(t[2:])
    return keccak256(t.encode())


def pin_candidates(text):
    """Every plausible way a typed PIN could have become bytes32, best guess first."""
    t = (text or "").strip()
    if not t:
        return []
    out = [to_pin(t)]
    raw = t.encode()
    if len(raw) <= 32:
        out.append(raw.rjust(32, b"\0"))   # utf8 text, zeros on the left
        out.append(raw.ljust(32, b"\0"))   # utf8 text, zeros on the right (bytes32 string style)
    seen, res = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            res.append(c)
    return res


def pin_commitment(pin32, donor, to):
    """keccak256(abi.encode(pin, donor, to)): what createOfferGated stores and redeem checks."""
    return keccak256(bytes(pin32) + enc(donor.strip().lower()) + enc(to.strip().lower()))


def match_pin(text, commitment, donor, holder):
    """Return the bytes32 PIN that matches the on-chain commitment, or None."""
    for cand in pin_candidates(text):
        if pin_commitment(cand, donor, holder) == bytes(commitment):
            return cand
    return None


# ---------------------------------------------------------------- create offer (S: sendable, free redeem)
def create_offer_tx(kind, holder, slices, delay_blocks, nonce=None, payload_hash=None):
    """createOfferS(to, delayBlocks, expectedNonce). The old B / T / P offers are now S offers.
    `payload_hash` only names the optional ledger record that can follow the transaction."""
    if kind not in KIND_ID:
        raise ValueError(S.ERR_ONLY_S)
    if not valid_address(holder):
        raise ValueError(S.ERR_HOLDER_ADDR)
    _final_holder(holder)
    if slices < 1:
        raise ValueError(S.ERR_MIN_SLICE)
    if delay_blocks < 1:
        raise ValueError(S.ERR_MIN_WINDOW)
    nn = _nonce(nonce)
    ph = payload_hash if payload_hash is not None else os.urandom(32)
    to = holder.strip()
    value_wei = int(slices) * UNIT_WEI

    def build(sig, meta):
        data = _hex(selector(CREATE_SIG) + enc(to.lower()) + enc(int(delay_blocks)) + enc(nn))
        return {"to": DSOS, "value_wei": value_wei, "value_eth": eth_text(value_wei), "data": data,
                "params": {"to": to, "delayBlocks": str(int(delay_blocks)), "expectedNonce": str(nn)}}
    return _with_rec(build, to, ph)


# ---------------------------------------------------------------- create A (open) / B (named)
def _check_sale(slices, per_record, delay_blocks):
    if slices < 1:
        raise ValueError(S.ERR_MIN_SLICE)
    if per_record < 1 or per_record > slices or slices % per_record:
        raise ValueError(S.ERR_RATE)
    if delay_blocks < 1:
        raise ValueError(S.ERR_MIN_WINDOW)


def create_a_tx(slices, per_record, delay_blocks, nonce=None):
    """createOfferA(delayBlocks, slicesPerRecord, expectedNonce): open offer. The ETH is escrowed;
    any seller confirms SOS records addressed to you and gets `per_record` slices for each."""
    _check_sale(slices, per_record, delay_blocks)
    nn = _nonce(nonce)
    value_wei = int(slices) * UNIT_WEI
    data = _hex(selector(CREATE_A_SIG) + enc(int(delay_blocks)) + enc(int(per_record)) + enc(nn))
    return {"to": DSOS, "value_wei": value_wei, "value_eth": eth_text(value_wei), "data": data,
            "params": {"delayBlocks": str(int(delay_blocks)), "slicesPerRecord": str(int(per_record)),
                       "expectedNonce": str(nn)}}


def create_b_tx(seller, slices, per_record, delay_blocks, nonce=None):
    """createOfferB(to, delayBlocks, slicesPerRecord, expectedNonce): named offer, only `seller`
    (zero address = DEAD = nobody) can confirm records."""
    if not valid_address(seller):
        raise ValueError(S.ERR_HOLDER_ADDR)
    _final_holder(seller)
    _check_sale(slices, per_record, delay_blocks)
    nn = _nonce(nonce)
    value_wei = int(slices) * UNIT_WEI
    data = _hex(selector(CREATE_B_SIG) + enc(seller.strip().lower()) + enc(int(delay_blocks)) +
                enc(int(per_record)) + enc(nn))
    return {"to": DSOS, "value_wei": value_wei, "value_eth": eth_text(value_wei), "data": data,
            "params": {"to": seller.strip(), "delayBlocks": str(int(delay_blocks)),
                       "slicesPerRecord": str(int(per_record)), "expectedNonce": str(nn)}}


def sync_records_tx(offer_id, n, nonce=None):
    """syncRecords(id, n, expectedNonce): confirm your next n ledger records for an A / B offer."""
    if offer_id < 1:
        raise ValueError(S.ERR_OFFER_ID)
    if n < 1:
        raise ValueError(S.ERR_MIN_RECORDS)
    nn = _nonce(nonce)
    return {"to": DSOS, "value_wei": 0, "value_eth": "0",
            "data": _hex(selector(SYNC_RECORDS_SIG) + enc(int(offer_id)) + enc(int(n)) + enc(nn)),
            "params": {"id": str(int(offer_id)), "n": str(int(n)), "expectedNonce": str(nn)}}


# ---------------------------------------------------------------- create gated offer (G)
GATED_SIG = "createOfferGated(address,uint256,bytes32,uint256)"
SWEEP_SIG = "sweepOffer(uint256,uint256)"
GATE_DELAY = 1


def _gated(holder, delay, pin_c, value_wei, ph, with_rec, nonce):
    to = holder.strip()
    nn = _nonce(nonce)

    def build(sig, meta):
        data = _hex(selector(GATED_SIG) + enc(to.lower()) + enc(int(delay)) + pin_c + enc(nn))
        return {"to": DSOS, "value_wei": int(value_wei), "value_eth": eth_text(value_wei),
                "data": data,
                "params": {"to": to, "delayBlocks": str(int(delay)), "pinCommitment_": _hex(pin_c),
                           "expectedNonce": str(nn)}}
    return _with_rec(build, to, ph) if with_rec else build(b"", "")


def create_gated_tx(donor, holder, slices, delay_blocks, pin_text, nonce=None):
    """createOfferGated for a real PIN. The commitment is keccak256(abi.encode(pin, donor, holder))
    where `donor` is the wallet that sends the transaction. The PIN itself is never put in the data."""
    if not valid_address(donor):
        raise ValueError(S.ERR_USER_ADDR)
    if not valid_address(holder):
        raise ValueError(S.ERR_HOLDER_ADDR)
    if slices < 1:
        raise ValueError(S.ERR_MIN_SLICE)
    if delay_blocks < 1:
        raise ValueError(S.ERR_MIN_WINDOW)
    if not (pin_text or "").strip():
        raise ValueError(S.ERR_PIN_EMPTY)
    final = _final_holder(holder)         # the commitment uses the holder the contract will store
    pin_c = pin_commitment(to_pin(pin_text), donor, final)
    return _gated(holder, delay_blocks, pin_c, int(slices) * UNIT_WEI, os.urandom(32), True, nonce)


def stake_tx(holder, need_wei, nonce=None):
    """createOfferGated(holder, 1, randomCommitment, expectedNonce). The PIN commitment is
    random and the PIN is never kept, so nobody can redeem the offer: it can only be swept into
    the pool, which is what stakes the donor. `need_wei` = stakeRequirement()."""
    if not valid_address(holder):
        raise ValueError(S.ERR_HOLDER_ADDR)
    if need_wei < UNIT_WEI or need_wei % UNIT_WEI:
        raise ValueError(S.ERR_STAKE_VALUE)
    pin_c = os.urandom(32)
    while pin_c == bytes(32):
        pin_c = os.urandom(32)
    _final_holder(holder)
    return _gated(holder, GATE_DELAY, pin_c, need_wei, os.urandom(32), False, nonce)


# ---------------------------------------------------------------- send (ERC-20 style transfer)
TRANSFER_SIG = "transfer(address,uint256)"
MIN_SEND_WINDOW = 7200
SEND_WINDOW = MIN_SEND_WINDOW + 30     # blocks that must remain, with a safety margin
ZERO_ADDR = "0x" + "0" * 40


def transfer_tx(to, n):
    """Data for dSOS.transfer(to, n): wallet send of n slices, no ETH value."""
    if not valid_address(to):
        raise ValueError(S.ERR_RECIPIENT_ADDR)
    if n < 1:
        raise ValueError(S.ERR_MIN_SEND)
    data = _hex(selector(TRANSFER_SIG) + enc(to.strip().lower()) + enc(int(n)))
    return {"to": DSOS, "value_wei": 0, "value_eth": "0", "data": data,
            "params": {"to": to.strip(), "n": str(int(n))}}


def is_sendable(o, window=SEND_WINDOW):
    """Same rule as the contract: only S offers, and only with more than `window` blocks left."""
    return o["kind"] == "S" and o["left"] > window


def sendable_total(offers, window=SEND_WINDOW):
    return sum(o["count"] for o in offers if is_sendable(o, window))


def plan_send(offers, n, window=SEND_WINDOW):
    """Mirror of dSOS.transfer(): walk the holder's offer list from the newest entry
    (highest `pos`) to the oldest, skipping G / A / B and short-window offers, splitting the
    last one if needed. Returns (picks, remaining) with picks = [(offer, slices)]."""
    picks, remaining = [], n
    for o in sorted(offers, key=lambda x: x["pos"], reverse=True):
        if remaining <= 0:
            break
        if is_sendable(o, window):
            take = min(o["count"], remaining)
            picks.append((o, take))
            remaining -= take
    return picks, remaining


def blocked_summary(offers, window=SEND_WINDOW):
    """Slices that wallet send cannot move: (gated / A / B, short window, expired), each (offers, slices)."""
    g = [o for o in offers if o["kind"] != "S" and o["left"] > 0]
    s = [o for o in offers if o["kind"] == "S" and 0 < o["left"] <= window]
    e = [o for o in offers if o["left"] <= 0]
    tot = lambda xs: (len(xs), sum(o["count"] for o in xs))  # noqa: E731
    return tot(g), tot(s), tot(e)


# ---------------------------------------------------------------- credits
SYNC_SIG = "syncCredits()"
REDEEM_CREDIT_SIG = "redeemCredit(uint256,uint256)"
CHAIN_ID = 1


def sync_credits_tx():
    """syncCredits(): no arguments, no ETH."""
    return {"to": DSOS, "value_wei": 0, "value_eth": "0",
            "data": _hex(selector(SYNC_SIG)), "params": {}}


def redeem_hash(user, amount_wei, nonce):
    """Same as dSOS.redeemPayloadHash(user, 0, amount): keccak256(abi.encode(user, kind=0,
    amount, nonce, dSOS contract, chainid)). Informational: it names the next credit redeem."""
    return keccak256(enc(user.strip().lower()) + enc(0) + enc(int(amount_wei)) +
                     enc(int(nonce)) + enc(DSOS) + enc(CHAIN_ID))


def redeem_credit_tx(user, credits, nonce):
    """redeemCredit(credits, expectedNonce). `nonce` must equal redeemNonce(user)."""
    if not valid_address(user):
        raise ValueError(S.ERR_USER_ADDR)
    if credits < 1:
        raise ValueError(S.ERR_MIN_CREDIT)
    nn = _nonce(nonce)
    ph = redeem_hash(user, int(credits) * UNIT_WEI, nn)
    wei = int(credits) * UNIT_WEI

    def build(sig, meta):
        data = _hex(selector(REDEEM_CREDIT_SIG) + enc(int(credits)) + enc(nn))
        return {"to": DSOS, "value_wei": 0, "value_eth": "0", "data": data,
                "params": {"creditsToSpend": str(int(credits)), "expectedNonce": str(nn),
                           "payloadHash": _hex(ph)},
                "payout_eth": eth_text(wei)}
    # optional ledger record after success: addressed to the ledger contract itself, as before
    return _with_rec(build, LEDGER, ph)


# ---------------------------------------------------------------- sweep
def sweep_offer_tx(offer_id, nonce=None):
    """sweepOffer(id, expectedNonce): anyone may call it once the offer has expired. The nonce is
    the sender's own (the caller's), not the donor's."""
    if offer_id < 1:
        raise ValueError(S.ERR_OFFER_ID)
    nn = _nonce(nonce)
    return {"to": DSOS, "value_wei": 0, "value_eth": "0",
            "data": _hex(selector(SWEEP_SIG) + enc(int(offer_id)) + enc(nn)),
            "params": {"id": str(int(offer_id)), "expectedNonce": str(nn)}}


# ---------------------------------------------------------------- redeem slices of an offer
REDEEM_SLICES_SIG = "redeemSlices(uint256,uint256,bytes32,uint256)"


def redeem_slices_tx(offer_id, slices, pin=None, donor=None, nonce=None):
    """redeemSlices(id, slices, pin, expectedNonce). `pin` = 32 raw bytes for a gated offer (zeros
    for S / A / B). A / B redeems are capped by the slices you funded in your own A / B offers.
    `donor` only names the optional ledger record that can follow the transaction."""
    if offer_id < 1:
        raise ValueError(S.ERR_OFFER_ID)
    if slices < 1:
        raise ValueError(S.ERR_SLICES)
    pin = bytes(pin) if pin is not None else bytes(32)
    if len(pin) != 32:
        raise ValueError(S.ERR_PIN_BYTES)
    nn = _nonce(nonce)
    ph = os.urandom(32)
    wei = int(slices) * UNIT_WEI

    def build(sig, meta):
        data = _hex(selector(REDEEM_SLICES_SIG) + enc(int(offer_id)) + enc(int(slices)) + pin + enc(nn))
        return {"to": DSOS, "value_wei": 0, "value_eth": "0", "data": data,
                "params": {"id": str(int(offer_id)), "slices": str(int(slices)), "pin": _hex(pin),
                           "expectedNonce": str(nn)},
                "payout_eth": eth_text(wei)}
    if donor and valid_address(donor):
        return _with_rec(build, donor, ph)
    return build(b"", "")


# ---------------------------------------------------------------- transfer slices of an offer
TRANSFER_SLICES_SIG = "transferSlices(uint256,uint256,address,uint256)"


def transfer_slices_tx(offer_id, slices, to, nonce=None):
    """transferSlices(id, slices, to, expectedNonce): send part or all of one S offer by id, while
    more than 7,200 blocks of its window remain."""
    if offer_id < 1:
        raise ValueError(S.ERR_OFFER_ID)
    if slices < 1:
        raise ValueError(S.ERR_SLICES)
    if not valid_address(to):
        raise ValueError(S.ERR_RECIPIENT_ADDR)
    nn = _nonce(nonce)
    ph = os.urandom(32)

    def build(sig, meta):
        data = _hex(selector(TRANSFER_SLICES_SIG) + enc(int(offer_id)) + enc(int(slices)) +
                    enc(to.strip().lower()) + enc(nn))
        return {"to": DSOS, "value_wei": 0, "value_eth": "0", "data": data,
                "params": {"id": str(int(offer_id)), "slices": str(int(slices)), "to": to.strip(),
                           "expectedNonce": str(nn)}}
    return _with_rec(build, to, ph)


# ---------------------------------------------------------------- donate (plain ETH to the pool)
def parse_eth(text):
    """Decimal ETH text -> wei. Raises ValueError with a user-facing message."""
    t = (text or "").strip().replace(",", ".")
    try:
        d = Decimal(t)
    except InvalidOperation:
        raise ValueError(S.ERR_AMOUNT_ETH) from None
    if not d.is_finite() or d <= 0:
        raise ValueError(S.ERR_AMOUNT_ZERO)
    wei = d.scaleb(18)
    if wei != wei.to_integral_value():
        raise ValueError(S.ERR_AMOUNT_DECIMALS)
    return int(wei)


def donate_tx(amount_text):
    """Plain ETH transfer to the dSOS contract (its receive() adds it to the pool)."""
    wei = parse_eth(amount_text)
    return {"to": DSOS, "value_wei": wei, "value_eth": eth_text(wei), "data": "0x",
            "params": {}, "plain": True}


# ---------------------------------------------------------------- ledger record (EIP-712)
RECORD_TYPE = "Record(address signer,address intendedTo,bytes32 payloadHash,bytes32 metadataHash)"
REC_META = "dSOS tx"   # metadata of the record that follows a dSOS transaction (max 64 chars)
LEDGER_RECORD_SIG = "recordSignature(address,address,bytes32,bytes,string)"


def ledger_typed_data(signer, intended_to, payload_hash, metadata=""):
    """JSON for eth_signTypedData_v4: the exact struct SOS69069 verifies on every record."""
    return json.dumps({
        "types": {
            "EIP712Domain": [{"name": "name", "type": "string"}, {"name": "version", "type": "string"},
                             {"name": "chainId", "type": "uint256"},
                             {"name": "verifyingContract", "type": "address"}],
            "Record": [{"name": "signer", "type": "address"}, {"name": "intendedTo", "type": "address"},
                       {"name": "payloadHash", "type": "bytes32"},
                       {"name": "metadataHash", "type": "bytes32"}],
        },
        "primaryType": "Record",
        "domain": {"name": "69069", "version": "1", "chainId": CHAIN_ID, "verifyingContract": LEDGER},
        "message": {"signer": signer.strip().lower(), "intendedTo": intended_to.strip().lower(),
                    "payloadHash": _hex(payload_hash), "metadataHash": _hex(keccak256(metadata.encode()))},
    }, separators=(",", ":"))


def ledger_struct_hash(signer, intended_to, payload_hash, metadata=""):
    """SOS69069.recordStructHash(...) computed locally (used by tests)."""
    return keccak256(keccak256(RECORD_TYPE.encode()) + enc(signer.strip().lower()) +
                     enc(intended_to.strip().lower()) + bytes(payload_hash) +
                     keccak256(metadata.encode()))


def ledger_check_call(signer, intended_to, payload_hash, sig, metadata=""):
    """(to, data) for a dry run of SOS69069.recordSignature: it reverts InvalidSignature when the
    wallet's signature does not verify, so a bad signature is caught before anything is sent."""
    sg, mt = enc_bytes(sig), enc_str(metadata)
    head = [enc(signer.strip().lower()), enc(intended_to.strip().lower()), bytes(payload_hash),
            enc(5 * 32), enc(5 * 32 + len(sg))]
    return LEDGER, _hex(selector(LEDGER_RECORD_SIG) + b"".join(head) + sg + mt)


# ---------------------------------------------------------------- write records to the ledger (sellers)
LEDGER_BATCH_SIG = "recordSignatureOne(address,address,bytes32[],bytes[],string[])"
SELL_BATCH_MAX = 10          # records signed and written per round (the ledger itself allows 200)
PAYLOAD_SIG = "recordPayloadHash(uint256,address,uint256)"
USED_SIG = "isRecordHashUsed(bytes32)"


def _enc_dyn_array(items):
    """ABI tail of an array whose elements are dynamic: length, offsets, then the elements."""
    n = len(items)
    offs, cur = [], n * 32
    for it in items:
        offs.append(enc(cur))
        cur += len(it)
    return enc(n) + b"".join(offs) + b"".join(items)


def ledger_batch_tx(signer, intended_to, payload_hashes, signatures, metadatas=None):
    """SOS69069.recordSignatureOne(signer, intendedTo, payloadHashes[], signatures[], metadatas[]):
    one transaction that writes many records from one signer to one receiver. The transaction goes
    to the LEDGER, not to dSOS. `payload_hashes` are 32 raw bytes each, `signatures` 65 bytes each."""
    n = len(payload_hashes)
    if n < 1 or len(signatures) != n:
        raise ValueError(S.ERR_MIN_RECORDS)
    metas = list(metadatas) if metadatas is not None else [""] * n
    if len(metas) != n:
        raise ValueError(S.ERR_MIN_RECORDS)
    t1 = enc(n) + b"".join(bytes(p) for p in payload_hashes)
    t2 = _enc_dyn_array([enc_bytes(bytes(sg)) for sg in signatures])
    t3 = _enc_dyn_array([enc_str(m) for m in metas])
    head = [enc(signer.strip().lower()), enc(intended_to.strip().lower()),
            enc(5 * 32), enc(5 * 32 + len(t1)), enc(5 * 32 + len(t1) + len(t2))]
    data = _hex(selector(LEDGER_BATCH_SIG) + b"".join(head) + t1 + t2 + t3)
    return {"to": LEDGER, "value_wei": 0, "value_eth": "0", "data": data, "ledger": True,
            "params": {"signer": signer.strip(), "intendedTo": intended_to.strip(),
                       "payloadHashes": json.dumps([_hex(p) for p in payload_hashes], separators=(",", ":")),
                       "signatures": json.dumps([_hex(sg) for sg in signatures], separators=(",", ":")),
                       "metadatas": json.dumps(metas, separators=(",", ":"))}}
