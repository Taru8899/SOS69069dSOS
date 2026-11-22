"""Selling SOS records to an A / B offer: read the escrow, see which of your records are already on
the SOS ledger, and prepare the transactions. Nothing here signs or sends. Blocking network calls:
run them from a worker thread.

Flow for a seller (the creator of the offer is the receiver of the records):
  1. record_hashes()      payload hash of your next records, from dSOS.recordPayloadHash(id, you, index)
  2. you sign each record (eth_signTypedData_v4) and tx.ledger_batch_tx(...) writes them to the ledger
  3. tx.sync_records_tx() asks dSOS to confirm them; every confirmed record moves its slices into
     your own offer (same expiry). Redeem them in the Offers tab before expiry.
"""
from concurrent.futures import ThreadPoolExecutor

import core
import tx
from core import DSOS, LEDGER, u

SCAN_MAX = 20          # records checked on the ledger per refresh
OPEN_SCAN = 60         # newest offer ids looked at when listing open A / B offers
OPEN_LIMIT = 15        # open offers shown


def _addr(w):
    return "0x" + w[12:].hex()


def load_sale(chain, sale_id):
    """dSOS.sales(id) as a dict, or None when that id is not an A / B escrow."""
    w = chain.call(DSOS, "sales(uint256)", [int(sale_id)])
    donor = _addr(w[0])
    if int(donor, 16) == 0:
        return None
    return {"id": int(sale_id), "donor": donor, "target": _addr(w[1]), "kind": core.KIND.get(u(w[2]), "?"),
            "active": u(w[3]) != 0, "slices_left": u(w[4]), "per_record": u(w[5]),
            "records_left": u(w[6]), "created_at": u(w[7]), "sweepable_at": u(w[8]),
            "salt": "0x" + w[9].hex()}


def open_sales(chain, block, limit=OPEN_LIMIT, scan=OPEN_SCAN):
    """The newest open escrows (A and B) that can still take records. Newest first."""
    nxt = u(chain.call(DSOS, "nextOfferId()")[0])
    ids = list(range(nxt - 1, max(0, nxt - 1 - scan), -1))

    def one(i):
        try:
            return load_sale(chain, i)
        except Exception:  # noqa: BLE001
            return None
    with ThreadPoolExecutor(max_workers=6) as ex:
        found = list(ex.map(one, ids))
    live = [s for s in found if s and s["active"] and s["sweepable_at"] > block and s["records_left"] > 0]
    return live[:limit]


def payload_hash(chain, sale_id, seller, index):
    """dSOS.recordPayloadHash(id, seller, index) as 32 raw bytes."""
    return chain.call(DSOS, tx.PAYLOAD_SIG, [int(sale_id), seller, int(index)])[0]


def record_hashes(chain, sale_id, seller, start, count):
    """Payload hashes of records start .. start+count-1 (read in parallel)."""
    with ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(lambda i: payload_hash(chain, sale_id, seller, i), range(start, start + count)))


def on_ledger(chain, signer, intended_to, ph):
    """True when that exact record (empty metadata) is already on the SOS ledger."""
    sh = tx.ledger_struct_hash(signer, intended_to, ph, "")
    return u(chain.call(LEDGER, tx.USED_SIG, ["0x" + sh.hex()])[0]) != 0


def seller_state(chain, sale, me):
    """What `me` has done on this escrow:
       next      index of the next record dSOS will count for you
       ready     how many of your next records are already on the ledger (not yet confirmed)
       earned    id of the offer that holds your earned slices (0 = none yet)"""
    sid = sale["id"]
    nxt = u(chain.call(DSOS, "nextRecord(uint256,address)", [sid, me])[0])
    earned = u(chain.call(DSOS, "earnedOffer(uint256,address)", [sid, me])[0])
    look = min(sale["records_left"], SCAN_MAX)
    ready = 0
    if look > 0:
        phs = record_hashes(chain, sid, me, nxt, look)
        with ThreadPoolExecutor(max_workers=6) as ex:
            used = list(ex.map(lambda p: on_ledger(chain, me, sale["donor"], p), phs))
        while ready < len(used) and used[ready]:
            ready += 1
    return {"next": nxt, "ready": ready, "earned": earned, "scanned": look}


def can_sell(sale, me, block):
    """(ok, reason key) - reasons are looked up in strings (SELL_WHY_*)."""
    if not sale["active"] or sale["records_left"] <= 0:
        return False, "full"
    if sale["sweepable_at"] <= block:
        return False, "expired"
    if sale["kind"] == "B" and me.lower() != sale["target"].lower():
        return False, "named"
    return True, ""
