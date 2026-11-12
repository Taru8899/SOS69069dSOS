"""Build the data for dSOS transactions. Nothing here signs or sends: the wallet app does that.

Every builder returns a dict:
    to, value_wei, value_eth, data (0x hex), params (for Etherscan Write Contract)
Builders whose contract call carries a ledger record (Rec) also return `rec`:
    intended_to, payload_hash, make(signature_bytes, metadata) -> the same transaction with that
    signature inside. Without a signature the contract skips the ledger record.
"""
import json
import os
import re
from decimal import Decimal, InvalidOperation

import strings as S
from core import DSOS, LEDGER, enc, keccak256, selector

CREATE_SIG = "createOffer(uint8,address,uint256,bytes32,bytes,string)"
KIND_ID = {"B": 1, "T": 2, "P": 3}   # G (=0) goes through create_gated_tx
UNIT_WEI = 10**15
WEI_PER_ETH = 10**18


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
    """Attach the ledger-record info to a transaction builder `build(sig, meta)`."""
    def make(sig=b"", meta=""):
        t = build(bytes(sig), meta)
        t["rec"] = {"intended_to": intended_to.strip(), "payload_hash": ph, "make": make}
        return t
    return make()


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


# ---------------------------------------------------------------- create offer (B / T / P)
def create_offer_tx(kind, holder, slices, delay_blocks, payload_hash=None):
    """createOffer(kind, holder, delay, payloadHash, signature, metadata). Empty signature and
    metadata by default: the contract skips the ledger record and still creates the offer."""
    if kind not in KIND_ID:
        raise ValueError(S.ERR_ONLY_BTP)
    if not valid_address(holder):
        raise ValueError(S.ERR_HOLDER_ADDR)
    if slices < 1:
        raise ValueError(S.ERR_MIN_SLICE)
    if delay_blocks < 1:
        raise ValueError(S.ERR_MIN_WINDOW)
    ph = payload_hash if payload_hash is not None else os.urandom(32)
    to = holder.strip()
    value_wei = int(slices) * UNIT_WEI

    def build(sig, meta):
        sg, mt = enc_bytes(sig), enc_str(meta)
        head = [enc(KIND_ID[kind]), enc(to.lower()), enc(int(delay_blocks)), ph,
                enc(6 * 32), enc(6 * 32 + len(sg))]
        data = _hex(selector(CREATE_SIG) + b"".join(head) + sg + mt)
        return {"to": DSOS, "value_wei": value_wei, "value_eth": eth_text(value_wei), "data": data,
                "params": {"kind": str(KIND_ID[kind]), "to": to, "delayBlocks": str(int(delay_blocks)),
                           "payloadHash": _hex(ph), "signature": _hex(sig), "metadata": meta}}
    return _with_rec(build, to, ph)


# ---------------------------------------------------------------- create gated offer (G)
GATED_SIG = "createOfferGated(address,uint256,bytes32,bytes32,bytes,string)"
SWEEP_SIG = "sweepOffer(uint256)"
GATE_DELAY = 1


def _gated(holder, delay, pin_c, value_wei, ph, with_rec):
    to = holder.strip()

    def build(sig, meta):
        sg, mt = enc_bytes(sig), enc_str(meta)
        head = [enc(to.lower()), enc(int(delay)), pin_c, ph, enc(6 * 32), enc(6 * 32 + len(sg))]
        data = _hex(selector(GATED_SIG) + b"".join(head) + sg + mt)
        return {"to": DSOS, "value_wei": int(value_wei), "value_eth": eth_text(value_wei),
                "data": data,
                "params": {"to": to, "delayBlocks": str(int(delay)), "pinCommitment_": _hex(pin_c),
                           "payloadHash": _hex(ph), "signature": _hex(sig), "metadata": meta}}
    return _with_rec(build, to, ph) if with_rec else build(b"", "")


def create_gated_tx(donor, holder, slices, delay_blocks, pin_text):
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
    pin_c = pin_commitment(to_pin(pin_text), donor, holder)
    return _gated(holder, delay_blocks, pin_c, int(slices) * UNIT_WEI, os.urandom(32), True)


def stake_tx(holder, need_wei):
    """createOfferGated(holder, 1, randomCommitment, randomHash, 0x, ""). The PIN commitment is
    random and the PIN is never kept, so nobody can redeem the offer: it can only be swept into
    the pool, which is what stakes the donor. `need_wei` = stakeRequirement()."""
    if not valid_address(holder):
        raise ValueError(S.ERR_HOLDER_ADDR)
    if need_wei < UNIT_WEI or need_wei % UNIT_WEI:
        raise ValueError(S.ERR_STAKE_VALUE)
    pin_c = os.urandom(32)
    while pin_c == bytes(32):
        pin_c = os.urandom(32)
    return _gated(holder, GATE_DELAY, pin_c, need_wei, os.urandom(32), False)


# ---------------------------------------------------------------- send (ERC-20 style transfer)
TRANSFER_SIG = "transfer(address,uint256)"
MIN_SEND_WINDOW = 7200
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


def is_sendable(o, window=MIN_SEND_WINDOW):
    """Same rule as the contract: not a G offer and more than `window` blocks left."""
    return o["kind"] != "G" and o["left"] > window


def sendable_total(offers, window=MIN_SEND_WINDOW):
    return sum(o["count"] for o in offers if is_sendable(o, window))


def plan_send(offers, n, window=MIN_SEND_WINDOW):
    """Mirror of dSOS.transfer(): walk the holder's offer list from the newest entry
    (highest `pos`) to the oldest, skipping G and short-window offers, splitting the
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


def blocked_summary(offers, window=MIN_SEND_WINDOW):
    """Slices that wallet send cannot move: (gated, short window, expired), each (offers, slices)."""
    g = [o for o in offers if o["kind"] == "G" and o["left"] > 0]
    s = [o for o in offers if o["kind"] != "G" and 0 < o["left"] <= window]
    e = [o for o in offers if o["left"] <= 0]
    tot = lambda xs: (len(xs), sum(o["count"] for o in xs))  # noqa: E731
    return tot(g), tot(s), tot(e)


# ---------------------------------------------------------------- credits
SYNC_SIG = "syncCredits()"
REDEEM_CREDIT_SIG = "redeemCredit(uint256,(bytes32,bytes,string))"
CHAIN_ID = 1


def sync_credits_tx():
    """syncCredits(): no arguments, no ETH."""
    return {"to": DSOS, "value_wei": 0, "value_eth": "0",
            "data": _hex(selector(SYNC_SIG)), "params": {}}


def redeem_hash(user, amount_wei, nonce):
    """Same as dSOS._redeemHash(user, 0, amount): keccak256(abi.encode(user, kind=0,
    amount, nonce, dSOS contract, chainid))."""
    return keccak256(enc(user.strip().lower()) + enc(0) + enc(int(amount_wei)) +
                     enc(int(nonce)) + enc(DSOS) + enc(CHAIN_ID))


def redeem_credit_tx(user, credits, nonce):
    """redeemCredit(credits, (payloadHash, signature, metadata)). The payloadHash must equal the
    contract's redeem hash; the signature may stay empty (then no ledger record is written)."""
    if not valid_address(user):
        raise ValueError(S.ERR_USER_ADDR)
    if credits < 1:
        raise ValueError(S.ERR_MIN_CREDIT)
    ph = redeem_hash(user, int(credits) * UNIT_WEI, nonce)
    wei = int(credits) * UNIT_WEI

    def build(sig, meta):
        data = _hex(selector(REDEEM_CREDIT_SIG) + enc(int(credits)) + enc(2 * 32) +
                    rec_tuple(ph, sig, meta))
        ph_hex = _hex(ph)
        return {"to": DSOS, "value_wei": 0, "value_eth": "0", "data": data,
                "params": {"creditsToSpend": str(int(credits)), "payloadHash": ph_hex,
                           "r": json.dumps([ph_hex, _hex(sig), meta], separators=(",", ":"))},
                "payout_eth": eth_text(wei)}
    # the ledger record of a credit redeem is addressed to the ledger contract itself
    return _with_rec(build, LEDGER, ph)


# ---------------------------------------------------------------- sweep
def sweep_offer_tx(offer_id):
    """sweepOffer(id): anyone may call it once the offer has expired."""
    if offer_id < 1:
        raise ValueError(S.ERR_OFFER_ID)
    return {"to": DSOS, "value_wei": 0, "value_eth": "0",
            "data": _hex(selector(SWEEP_SIG) + enc(int(offer_id))),
            "params": {"id": str(int(offer_id))}}


# ---------------------------------------------------------------- redeem slices of an offer
REDEEM_SLICES_SIG = "redeemSlices(uint256,uint256,bytes32,(bytes32,bytes,string))"


def redeem_slices_tx(offer_id, slices, pin=None, donor=None):
    """redeemSlices(id, slices, pin, (payloadHash, signature, metadata)).
    `pin` = 32 raw bytes for a gated offer (zeros for B/T/P). `donor` (the offer's donor) lets the
    wallet sign a ledger record addressed to the donor; without it no record is offered."""
    if offer_id < 1:
        raise ValueError(S.ERR_OFFER_ID)
    if slices < 1:
        raise ValueError(S.ERR_SLICES)
    pin = bytes(pin) if pin is not None else bytes(32)
    if len(pin) != 32:
        raise ValueError(S.ERR_PIN_BYTES)
    ph = os.urandom(32)
    wei = int(slices) * UNIT_WEI

    def build(sig, meta):
        data = _hex(selector(REDEEM_SLICES_SIG) + enc(int(offer_id)) + enc(int(slices)) + pin +
                    enc(4 * 32) + rec_tuple(ph, sig, meta))
        ph_hex = _hex(ph)
        return {"to": DSOS, "value_wei": 0, "value_eth": "0", "data": data,
                "params": {"id": str(int(offer_id)), "slices": str(int(slices)), "pin": _hex(pin),
                           "payloadHash": ph_hex,
                           "r": json.dumps([ph_hex, _hex(sig), meta], separators=(",", ":"))},
                "payout_eth": eth_text(wei)}
    if donor and valid_address(donor):
        return _with_rec(build, donor, ph)
    return build(b"", "")


# ---------------------------------------------------------------- transfer slices of an offer
TRANSFER_SLICES_SIG = "transferSlices(uint256,uint256,address,(bytes32,bytes,string))"


def transfer_slices_tx(offer_id, slices, to):
    """transferSlices(id, slices, to, (payloadHash, signature, metadata)): send part or all of one
    B/T/P offer by id. Not limited by the 7,200-block wallet-send window."""
    if offer_id < 1:
        raise ValueError(S.ERR_OFFER_ID)
    if slices < 1:
        raise ValueError(S.ERR_SLICES)
    if not valid_address(to):
        raise ValueError(S.ERR_RECIPIENT_ADDR)
    ph = os.urandom(32)

    def build(sig, meta):
        data = _hex(selector(TRANSFER_SLICES_SIG) + enc(int(offer_id)) + enc(int(slices)) +
                    enc(to.strip().lower()) + enc(4 * 32) + rec_tuple(ph, sig, meta))
        ph_hex = _hex(ph)
        return {"to": DSOS, "value_wei": 0, "value_eth": "0", "data": data,
                "params": {"id": str(int(offer_id)), "slices": str(int(slices)), "to": to.strip(),
                           "payloadHash": ph_hex,
                           "r": json.dumps([ph_hex, _hex(sig), meta], separators=(",", ":"))}}
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
