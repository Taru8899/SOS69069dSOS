"""High-level read-only queries and display helpers."""
from dataclasses import dataclass, field
from decimal import Decimal

from . import config
from .contracts import DSOS_SPEC, LEDGER_SPEC, Contract, batch, checksum
from .rpc import RpcClient, RpcError

KIND = {0: "G", 1: "B", 2: "T", 3: "P"}


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
    record_hash: str
    created_at: int
    sweepable_at: int
    count: int
    blocks_left: int
    status: str      # "redeemable" | "expiring" | "expired"
    sendable: bool   # non-G and more than MIN_SEND_WINDOW blocks left


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
        donor, holder, principal, active, kind, rhash, created, sweepable, count = o
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
            record_hash="0x" + rhash.hex(), created_at=created, sweepable_at=sweepable,
            count=count, blocks_left=left, status=status,
            sendable=(KIND.get(kind) != "G" and left > window),
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
        pool_balance_wei=_z(r[8]), pool_supply=_z(r[9]),
        pool_earmarked_wei=_z(r[10]), pool_unallocated_wei=_z(r[11]),
    )
