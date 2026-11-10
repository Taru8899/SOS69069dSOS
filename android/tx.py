"""Build the data for a dSOS createOffer transaction (no signing, no sending)."""
import os

from core import DSOS, enc, selector

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
        raise ValueError("Only B, T and P offers are supported here")
    if not valid_address(holder):
        raise ValueError("Holder must be a 0x address (42 characters)")
    if slices < 1:
        raise ValueError("At least 1 slice")
    if delay_blocks < 1:
        raise ValueError("Window must be at least 1 block")
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
