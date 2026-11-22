"""High-level read-only queries and display helpers."""
from dataclasses import dataclass, field
from decimal import Decimal

from . import config
from .contracts import DSOS_SPEC, LEDGER_SPEC, Contract, batch, checksum
from .rpc import RpcClient, RpcError

KIND = {0: "G", 1: "S", 2: "A", 3: "B"}   # gated, sendable (free redeem), open, named
CAPPED_KINDS = ("A", "B")                    # redeems of these are capped by your A/B allowance


# ---------- formatting ----------
def wei_to_eth(wei: int) -> str:
    s = f"{Decimal(wei) / Decimal(10**18):.6f}".rstrip("0").rstrip(".")
    return s or "0"


def fmt_blocks(blocks: int) -> str:
    if blocks <= 0:
        return "expired"
    secs = blocks * config.BLOCK_TIME_SECONDS
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


# ---------- models ----------
@dataclass
class Offer:
    id: int
    donor: str
    holder: str
    principal_wei: int
    active: bool
    kind: str
    created_at: int
    sweepable_at: int
    count: int
    blocks_left: int
    status: str      # "redeemable" | "expiring" | "expired"
    sendable: bool   # only S offers, and only with more than MIN_SEND_WINDOW blocks left
    capped: bool = False   # A / B: redeem is capped by the holder's A/B allowance


@dataclass
class Sale:
    """Escrow of an A (open) or B (named) offer: ETH waiting for sellers to confirm SOS records."""
    id: int
    donor: str            # creator, and the receiver of the sellers' ledger records
    target: str           # the dSOS contract itself for A, the one seller for B
    kind: str
    active: bool
    slices_left: int
    per_record: int       # slices paid for each confirmed record (at least 1)
    records_left: int
    created_at: int
    sweepable_at: int
    salt: str
    blocks_left: int = 0
    open: bool = False    # active and not expired


@dataclass
class Summary:
    address: str
    block: int
    source: str
    balance: int
    value_wei: int
    sendable: int
    expiring: int
    expired: int
    offers: list = field(default_factory=list)
    next_expiry_block: int | None = None
    # stake / credits
    staked: bool = False
    staked_at: int = 0
    can_redeem: bool = False
    cooldown_blocks_left: int = 0
    stake_requirement_wei: int = 0
    gate_requirement_wei: int = 0
    credits: int = 0
    formable: int = 0
    pending_credits: int = 0
    ledger_push: int = 0
    ledger_trust: int = 0
    ledger_effective: int = 0
    # A / B allowance and the nonce every value-moving call must carry
    produced: int = 0
    redeemed: int = 0
    allowance: int = 0
    nonce: int = 0
    offers_module: str = ""
    # pool
    pool_balance_wei: int = 0
    pool_supply: int = 0
    pool_earmarked_wei: int = 0
    pool_unallocated_wei: int = 0


def make_rpc() -> RpcClient:
    return RpcClient()


def _z(v, default=0):
    return default if v is None else v


def load_summary(address: str, rpc: RpcClient | None = None) -> Summary:
    rpc = rpc or make_rpc()
    addr = checksum(address)
    dsos = Contract(rpc, config.DSOS_ADDRESS, DSOS_SPEC)
    ledger = Contract(rpc, config.LEDGER_ADDRESS, LEDGER_SPEC)

    block = rpc.block_number()

    r = batch(rpc, [
        (dsos, "balanceOf", (addr,)),            # 0
        (dsos, "offerIdsOf", (addr,)),           # 1
        (dsos, "staked", (addr,)),               # 2
        (dsos, "stakedAt", (addr,)),             # 3
        (dsos, "canRedeem", (addr,)),            # 4
        (dsos, "redemptionCredits", (addr,)),    # 5
        (dsos, "formableCredits", (addr,)),      # 6
        (dsos, "pendingCredits", (addr,)),       # 7
        (dsos, "poolBalance", ()),               # 8
        (dsos, "totalSupply", ()),               # 9
        (dsos, "totalEarmarked", ()),            # 10
        (dsos, "unallocatedBalance", ()),        # 11
        (dsos, "stakeRequirement", ()),          # 12
        (dsos, "gateRequirement", ()),           # 13
        (dsos, "MIN_SEND_WINDOW", ()),           # 14
        (dsos, "STAKE_COOLDOWN", ()),            # 15
        (ledger, "statsOf", (addr,)),            # 16
        (dsos, "produced", (addr,)),             # 17
        (dsos, "redeemed", (addr,)),             # 18
        (dsos, "allowanceOf", (addr,)),          # 19
        (dsos, "redeemNonce", (addr,)),          # 20
        (dsos, "OFFERS_MODULE", ()),             # 21
    ])
    if r[0] is None or r[1] is None:
        raise RpcError("Could not read dSOS contract. Check network/addresses.")

    window = _z(r[14], config.DAY_BLOCKS)
    cooldown = _z(r[15], 14400)
    ids = list(r[1])

    raw_offers = batch(rpc, [(dsos, "offers", (i,)) for i in ids]) if ids else []

    offers: list[Offer] = []
    for oid, o in zip(ids, raw_offers):
        if o is None:
            continue
        donor, holder, principal, active, kind, created, sweepable, count = o
        left = sweepable - block
        if left <= 0:
            status = "expired"
        elif left <= window:
            status = "expiring"
        else:
            status = "redeemable"
        offers.append(Offer(
            id=oid, donor=checksum(donor), holder=checksum(holder),
            principal_wei=principal, active=active, kind=KIND.get(kind, "?"),
            created_at=created, sweepable_at=sweepable,
            count=count, blocks_left=left, status=status,
            sendable=(KIND.get(kind) == "S" and left > window),
            capped=(KIND.get(kind) in CAPPED_KINDS),
        ))
    offers.sort(key=lambda x: x.sweepable_at)

    live = [o for o in offers if o.blocks_left > 0]
    staked_at = _z(r[3])
    stats = r[16] if r[16] is not None else (0, 0, 0)

    return Summary(
        address=addr, block=block, source=rpc.last_source or "?",
        balance=_z(r[0]), value_wei=_z(r[0]) * config.UNIT_WEI,
        sendable=sum(o.count for o in offers if o.sendable),
        expiring=sum(o.count for o in offers if o.status == "expiring"),
        expired=sum(o.count for o in offers if o.status == "expired"),
        offers=offers,
        next_expiry_block=min((o.sweepable_at for o in live), default=None),
        staked=bool(_z(r[2], False)), staked_at=staked_at, can_redeem=bool(_z(r[4], False)),
        cooldown_blocks_left=max(0, staked_at + cooldown - block) if _z(r[2], False) else 0,
        stake_requirement_wei=_z(r[12]), gate_requirement_wei=_z(r[13]),
        credits=_z(r[5]), formable=_z(r[6]), pending_credits=_z(r[7]),
        ledger_push=stats[0], ledger_trust=stats[1], ledger_effective=stats[2],
        produced=_z(r[17]), redeemed=_z(r[18]), allowance=_z(r[19]), nonce=_z(r[20]),
        offers_module=checksum(r[21]) if r[21] else "",
        pool_balance_wei=_z(r[8]), pool_supply=_z(r[9]),
        pool_earmarked_wei=_z(r[10]), pool_unallocated_wei=_z(r[11]),
    )


def load_sale(sale_id: int, rpc: RpcClient | None = None) -> "Sale | None":
    """dSOS.sales(id): the escrow of an A / B offer, or None when that id is not an A / B offer."""
    rpc = rpc or make_rpc()
    dsos = Contract(rpc, config.DSOS_ADDRESS, DSOS_SPEC)
    block = rpc.block_number()
    w = dsos.call("sales", int(sale_id))
    donor, target, kind, active, left, per, recs, created, sweepable, salt = w
    if int(donor, 16) == 0:
        return None
    blocks_left = sweepable - block
    return Sale(id=int(sale_id), donor=checksum(donor), target=checksum(target),
                kind=KIND.get(kind, "?"), active=bool(active), slices_left=left, per_record=per,
                records_left=recs, created_at=created, sweepable_at=sweepable,
                salt="0x" + salt.hex(), blocks_left=blocks_left,
                open=bool(active) and blocks_left > 0)
