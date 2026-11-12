"""Build the data for a dSOS createOffer transaction (no signing, no sending)."""
import os

import strings as S
from core import DSOS, enc, keccak256, selector

CREATE_SIG = "createOffer(uint8,address,uint256,bytes32,bytes,string)"
KIND_ID = {"B": 1, "T": 2, "P": 3}   # G (=0) needs a PIN and is not built here
UNIT_WEI = 10**15


def valid_address(a):
    a = (a or "").strip()
    if len(a) != 42 or not a.startswith("0x"):
        return False
    try:
        int(a[2:], 16)
    except ValueError:
        return False
    return True


def create_offer_tx(kind, holder, slices, delay_blocks, payload_hash=None):
    """Return dict(to, value_wei, value_eth, data, params). Empty signature and
    metadata: the contract skips the ledger record and still creates the offer."""
    if kind not in KIND_ID:
        raise ValueError(S.ERR_ONLY_BTP)
    if not valid_address(holder):
        raise ValueError(S.ERR_HOLDER_ADDR)
    if slices < 1:
        raise ValueError(S.ERR_MIN_SLICE)
    if delay_blocks < 1:
        raise ValueError(S.ERR_MIN_WINDOW)
    ph = payload_hash if payload_hash is not None else os.urandom(32)
    head = [
        enc(KIND_ID[kind]),
        enc(holder.strip().lower()),
        enc(int(delay_blocks)),
        ph,
        enc(6 * 32),        # offset of `signature` (bytes)
        enc(7 * 32),        # offset of `metadata` (string)
    ]
    tail = [enc(0), enc(0)]  # signature = 0x, metadata = ""
    data = "0x" + (selector(CREATE_SIG) + b"".join(head + tail)).hex()
    value_wei = int(slices) * UNIT_WEI
    return {
        "to": DSOS,
        "value_wei": value_wei,
        "value_eth": f"{value_wei / 1e18:.6f}".rstrip("0").rstrip("."),
        "data": data,
        "params": {
            "kind": str(KIND_ID[kind]),
            "to": holder.strip(),
            "delayBlocks": str(int(delay_blocks)),
            "payloadHash": "0x" + ph.hex(),
            "signature": "0x",
            "metadata": "",
        },
    }


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
    data = "0x" + (selector(TRANSFER_SIG) + enc(to.strip().lower()) + enc(int(n))).hex()
    return {
        "to": DSOS,
        "value_wei": 0,
        "value_eth": "0",
        "data": data,
        "params": {"to": to.strip(), "n": str(int(n))},
    }


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
            "data": "0x" + selector(SYNC_SIG).hex(), "params": {}}


def redeem_hash(user, amount_wei, nonce):
    """Same as dSOS._redeemHash(user, 0, amount): keccak256(abi.encode(user, kind=0,
    amount, nonce, dSOS contract, chainid))."""
    return keccak256(enc(user.strip().lower()) + enc(0) + enc(int(amount_wei)) +
                     enc(int(nonce)) + enc(DSOS) + enc(CHAIN_ID))


def redeem_credit_tx(user, credits, nonce):
    """redeemCredit(credits, (payloadHash, 0x, "")): empty signature, so the contract
    skips the ledger record and still pays out."""
    if not valid_address(user):
        raise ValueError(S.ERR_USER_ADDR)
    if credits < 1:
        raise ValueError(S.ERR_MIN_CREDIT)
    ph = redeem_hash(user, int(credits) * UNIT_WEI, nonce)
    data = selector(REDEEM_CREDIT_SIG) + b"".join([
        enc(int(credits)),
        enc(2 * 32),        # offset of the tuple r
        ph,                 # r.payloadHash
        enc(3 * 32),        # r.signature offset (inside the tuple)
        enc(4 * 32),        # r.metadata offset (inside the tuple)
        enc(0),             # signature = 0x
        enc(0),             # metadata = ""
    ])
    ph_hex = "0x" + ph.hex()
    value_wei = int(credits) * UNIT_WEI
    return {"to": DSOS, "value_wei": 0, "value_eth": "0", "data": "0x" + data.hex(),
            "params": {"creditsToSpend": str(int(credits)), "payloadHash": ph_hex,
                       "r": '["' + ph_hex + '","0x",""]'},
            "payout_eth": f"{value_wei / 1e18:.6f}".rstrip("0").rstrip(".")}


# ---------------------------------------------------------------- stake / sweep
GATED_SIG = "createOfferGated(address,uint256,bytes32,bytes32,bytes,string)"
SWEEP_SIG = "sweepOffer(uint256)"
GATE_DELAY = 1


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
    ph = os.urandom(32)
    head = [enc(holder.strip().lower()), enc(GATE_DELAY), pin_c, ph, enc(6 * 32), enc(7 * 32)]
    tail = [enc(0), enc(0)]
    data = "0x" + (selector(GATED_SIG) + b"".join(head + tail)).hex()
    return {
        "to": DSOS,
        "value_wei": int(need_wei),
        "value_eth": f"{need_wei / 1e18:.6f}".rstrip("0").rstrip("."),
        "data": data,
        "params": {"to": holder.strip(), "delayBlocks": str(GATE_DELAY),
                   "pinCommitment_": "0x" + pin_c.hex(), "payloadHash": "0x" + ph.hex(),
                   "signature": "0x", "metadata": ""},
    }


def sweep_offer_tx(offer_id):
    """sweepOffer(id): anyone may call it once the offer has expired."""
    if offer_id < 1:
        raise ValueError(S.ERR_OFFER_ID)
    return {"to": DSOS, "value_wei": 0, "value_eth": "0",
            "data": "0x" + (selector(SWEEP_SIG) + enc(int(offer_id))).hex(),
            "params": {"id": str(int(offer_id))}}
