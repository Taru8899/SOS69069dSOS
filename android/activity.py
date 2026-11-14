"""Activity: dSOS events and failed transactions, read from the chain and grouped per transaction.

Nothing here touches the UI. All functions block (network): call them from a worker thread.

Sources
  * Etherscan (with an API key): getLogs for the full history of an address, txlist for failed
    transactions, timestamps come with the logs.
  * Public RPC (no key, or Etherscan failed): eth_getLogs in block windows (about 7 days at a
    time), timestamps by eth_getBlockByNumber for the newest rows (others are estimated).
"""
import time
from concurrent.futures import ThreadPoolExecutor

import core
import strings as S
from core import DSOS, LEDGER, UNIT, keccak256

WINDOW_BLOCKS = 50400            # about 7 days (Etherscan)
RPC_WINDOW = 14400               # about 2 days per step on the public nodes (800 blocks per call)
MAX_PAGES = 10                   # Etherscan: 10 pages x 1000 logs per query
MAX_BLOCK_LOOKUPS = 40           # exact timestamps for the newest blocks only (RPC path)
ZERO = "0x" + "0" * 40


def topic0(sig):
    return "0x" + keccak256(sig.encode()).hex()


T_CREATED = topic0("OfferCreated(uint256,uint8,address,address,uint256)")
T_TRANSFERRED = topic0("OfferTransferred(uint256,address,address)")
T_SPLIT = topic0("OfferSplit(uint256,uint256,uint256)")
T_REDEEMED = topic0("OfferRedeemed(uint256,address,address,uint256)")
T_SWEPT = topic0("OfferSwept(uint256,address,address,uint256)")
T_DONATION = topic0("Donation(address,uint256)")
T_FORMED = topic0("CreditsFormed(address,uint256,uint256)")
T_CREDIT_REDEEMED = topic0("CreditRedeemed(address,uint256,uint256)")
T_STAKED = topic0("Staked(address,uint64)")
T_TRANSFER = topic0("Transfer(address,address,uint256)")
T_SKIPPED = topic0("LedgerRecordSkipped(address,address,bytes32,bytes)")
T_FLAGGED = topic0("GateFlagged(uint256,bool)")
T_RECORDED = topic0("SignatureRecorded(address,address,bytes32,bytes,address,uint256,string)")

NAMES = {T_CREATED: "created", T_TRANSFERRED: "transferred", T_SPLIT: "split",
         T_REDEEMED: "redeemed", T_SWEPT: "swept", T_DONATION: "donation",
         T_FORMED: "formed", T_CREDIT_REDEEMED: "credit_redeemed", T_STAKED: "staked",
         T_TRANSFER: "transfer", T_SKIPPED: "skipped", T_FLAGGED: "flagged",
         T_RECORDED: "recorded"}

# filter key -> tag that a row must carry
FILTER_TAGS = {"created": "created", "received": "received", "sent": "sent",
               "redeemed": "redeemed", "swept": "swept", "stake": "stake",
               "donation": "donation", "ledger": "ledger", "failed": "failed"}


def pad_topic(addr):
    return "0x" + "0" * 24 + addr.lower().replace("0x", "")


def _addr(topic):
    return "0x" + topic[-40:].lower()


def _hex_int(v):
    if v is None:
        return 0
    if isinstance(v, int):
        return v
    v = str(v)
    if v in ("", "0x"):
        return 0
    return int(v, 16) if v.startswith("0x") else int(v)


def norm_log(raw):
    """Etherscan / RPC log dict -> {tx, block, ts, idx, topics, data, addr}."""
    return {
        "tx": raw.get("transactionHash", ""),
        "block": _hex_int(raw.get("blockNumber")),
        "ts": _hex_int(raw.get("timeStamp")),
        "idx": _hex_int(raw.get("logIndex")),
        "topics": [t.lower() for t in raw.get("topics", [])],
        "data": raw.get("data", "0x"),
        "addr": (raw.get("address") or "").lower(),
    }


def _data_words(data):
    h = (data or "0x")[2:]
    return [int(h[i:i + 64], 16) for i in range(0, len(h) - 63, 64)]


def decode(log):
    """-> dict with 'name' and the fields of that event, or None for an unknown event."""
    t = log["topics"]
    if not t:
        return None
    name = NAMES.get(t[0])
    if name is None:
        return None
    w = _data_words(log["data"])
    out = {"name": name, "addr": log["addr"]}
    try:
        if name == "created":
            out.update(id=int(t[1], 16), donor=_addr(t[2]), to=_addr(t[3]),
                       kind=w[0], principal=w[1])
        elif name == "transferred":
            out.update(id=int(t[1], 16), frm=_addr(t[2]), to=_addr(t[3]))
        elif name == "split":
            out.update(id=int(t[1], 16), new_id=int(t[2], 16), slices=w[0])
        elif name in ("redeemed", "swept"):
            out.update(id=int(t[1], 16), donor=_addr(t[2]), holder=_addr(t[3]), principal=w[0])
        elif name == "donation":
            out.update(frm=_addr(t[1]), amount=w[0])
        elif name == "formed":
            out.update(user=_addr(t[1]), formed=w[0], credits=w[1])
        elif name == "credit_redeemed":
            out.update(user=_addr(t[1]), spent=w[0], eth=w[1])
        elif name == "staked":
            out.update(user=_addr(t[1]), at=w[0])
        elif name == "transfer":
            out.update(frm=_addr(t[1]), to=_addr(t[2]), value=w[0])
        elif name == "recorded":
            out.update(signer=_addr(t[1]), intended=_addr(t[2]), submitter=_addr(t[3]))
        elif name in ("skipped",):
            out.update(signer=_addr(t[1]), intended=_addr(t[2]))
        elif name == "flagged":
            out.update(id=int(t[1], 16))
    except (IndexError, ValueError):
        return None
    return out


# ------------------------------------------------------------------ rows
def _eth(wei):
    return core.eth(wei)


def build_rows(logs, me, failed=()):
    """Group logs per transaction and describe each group. `me` is a lowercase address or ''
    (contract-wide view). `failed` = list of dicts from Etherscan txlist (isError == 1).
    Returns rows newest first."""
    groups = {}
    for lg in logs:
        groups.setdefault(lg["tx"], []).append(lg)
    rows = []
    for txh, lgs in groups.items():
        lgs.sort(key=lambda x: x["idx"])
        evs = [e for e in (decode(x) for x in lgs) if e]
        if not evs:
            continue
        row = _describe(txh, lgs, evs, me)
        if row:
            rows.append(row)
    for f in failed:
        rows.append(_failed_row(f, me))
    rows.sort(key=lambda r: (r["block"], r["order"]), reverse=True)
    return rows


def _first(evs, name):
    for e in evs:
        if e["name"] == name:
            return e
    return None


def _all(evs, name):
    return [e for e in evs if e["name"] == name]


def _describe(txh, lgs, evs, me):
    block = lgs[0]["block"]
    ts = max((x["ts"] for x in lgs), default=0)
    tags = set()
    row = {"tx": txh, "block": block, "ts": ts, "order": lgs[0]["idx"], "failed": False,
           "offer_id": None, "frm": "", "to": "", "eth": 0, "dsos": None, "tags": tags,
           "kind": "", "who": "", "note": "", "sign": 0}
    if _first(evs, "recorded") or _first(evs, "skipped"):
        tags.add("ledger")
    staked = _first(evs, "staked")
    created = _first(evs, "created")
    split = _first(evs, "split")
    trans = _all(evs, "transferred")
    redeemed = _first(evs, "redeemed")
    swept = _first(evs, "swept")
    formed = _first(evs, "formed")
    credit = _first(evs, "credit_redeemed")
    donation = _first(evs, "donation")
    plain = [e for e in _all(evs, "transfer") if e["frm"] != ZERO and e["to"] != ZERO]

    def mine(a):
        return bool(me) and a == me

    if created:
        row.update(kind="created", offer_id=created["id"], frm=created["donor"], to=created["to"],
                   eth=created["principal"], dsos=created["principal"] // UNIT)
        if mine(created["to"]) and not mine(created["donor"]):
            row.update(kind="received", sign=0)
            tags.add("received")
        else:
            tags.add("created")
            row["sign"] = -1 if mine(created["donor"]) else 0
    elif redeemed:
        row.update(kind="redeemed", offer_id=redeemed["id"], frm=redeemed["donor"],
                   to=redeemed["holder"], eth=redeemed["principal"],
                   dsos=redeemed["principal"] // UNIT)
        tags.add("redeemed")
        if mine(redeemed["holder"]):
            row["sign"] = 1
        elif mine(redeemed["donor"]):
            row["kind"] = "redeemed_by"
    elif swept:
        row.update(kind="swept", offer_id=swept["id"], frm=swept["donor"], to=swept["holder"],
                   eth=swept["principal"], dsos=swept["principal"] // UNIT)
        tags.add("swept")
        if staked:
            tags.add("stake")
            row["note"] = "staked"
            row["staked_user"] = staked["user"]
    elif trans or plain:
        if trans:
            t = trans[-1]
            row.update(offer_id=split["new_id"] if split else t["id"], frm=t["frm"], to=t["to"])
            n = split["slices"] if split else None
            if n is None and plain:
                n = plain[-1]["value"]
        else:
            t = plain[-1]
            row.update(frm=t["frm"], to=t["to"])
            n = t["value"]
        row["dsos"] = n
        row["eth"] = (n or 0) * UNIT
        if mine(row["frm"]):
            row["kind"] = "sent"
            tags.add("sent")
            row["sign"] = -1
        elif mine(row["to"]):
            row["kind"] = "received"
            tags.add("received")
            row["sign"] = 1
        else:
            row["kind"] = "sent"
            tags.add("sent")
    elif credit:
        row.update(kind="credit_redeemed", frm=credit["user"], eth=credit["eth"],
                   dsos=credit["spent"])
        tags.add("stake")
        row["sign"] = 1 if mine(credit["user"]) else 0
    elif formed:
        row.update(kind="formed", frm=formed["user"], dsos=formed["credits"])
        tags.add("stake")
    elif staked:
        row.update(kind="staked", frm=staked["user"])
        tags.add("stake")
    elif donation:
        row.update(kind="donation", frm=donation["frm"], eth=donation["amount"])
        tags.add("donation")
        row["sign"] = -1 if mine(donation["frm"]) else 0
    elif "ledger" in tags:
        rec = _first(evs, "recorded") or _first(evs, "skipped")
        row.update(kind="ledger", frm=rec.get("signer", ""), to=rec.get("intended", ""))
    else:
        return None
    # side notes
    if staked and row["kind"] not in ("swept", "staked") and mine(staked["user"]):
        tags.add("stake")
    if formed and "stake" not in tags:
        tags.add("stake")
    return row


def _failed_row(f, me):
    fn = (f.get("functionName") or "").split("(")[0] or (f.get("methodId") or "?")
    block = _hex_int(f.get("blockNumber"))
    return {"tx": f.get("hash", ""), "block": block, "ts": int(f.get("timeStamp") or 0),
            "order": int(f.get("transactionIndex") or 0), "failed": True, "offer_id": None,
            "frm": (f.get("from") or "").lower(), "to": (f.get("to") or "").lower(),
            "eth": 0, "dsos": None, "tags": {"failed"}, "kind": "failed", "who": fn,
            "note": "", "sign": 0}


def ago(ts, now=None):
    if not ts:
        return ""
    d = max(0, int((now or time.time()) - ts))
    if d < 90:
        return "just now"
    if d < 5400:
        return f"{d // 60}m ago"
    if d < 172800:
        return f"{d // 3600}h ago"
    return f"{d // 86400}d ago"


# ------------------------------------------------------------------ fetching
class Store:
    """Logs of one view (Mine or Contract) for one address, extended step by step."""

    def __init__(self, chain, me, scope):
        self.chain, self.me, self.scope = chain, (me or "").lower(), scope
        self.logs = {}
        self.failed = []
        self.latest = 0
        self.lo = None                 # lowest block covered so far
        self.complete = False          # history reached block 0
        self.truncated = False         # a query hit its size limit
        self.exact = bool(chain.api_key)
        self.use_es = bool(chain.api_key)
        self.note = ""
        self.times = {}                # block -> timestamp (RPC path)

    # -- helpers
    def _add(self, logs):
        for lg in logs:
            self.logs[(lg["tx"], lg["idx"])] = lg

    def _es_queries(self):
        """List of (address, topics) that make up this view on Etherscan. Every query carries
        topic0 (the event) as well as the address topic."""
        if self.scope == "contract":
            return [(DSOS, [])]
        me = pad_topic(self.me)
        q = []
        for t0 in (T_CREATED, T_TRANSFERRED, T_REDEEMED, T_SWEPT):      # id, donor/from, to/holder
            q.append((DSOS, [t0, None, me]))
            q.append((DSOS, [t0, None, None, me]))
        for t0 in (T_DONATION, T_FORMED, T_CREDIT_REDEEMED, T_STAKED):  # address at topic1
            q.append((DSOS, [t0, me]))
        for t0 in (T_TRANSFER, T_SKIPPED):                              # address at topic1 or 2
            q.append((DSOS, [t0, me]))
            q.append((DSOS, [t0, None, me]))
        q.append((LEDGER, [T_RECORDED, me]))
        q.append((LEDGER, [T_RECORDED, None, me]))
        return q

    def _fetch_es(self, frm, to):
        for addr, topics in self._es_queries():
            logs, trunc = self.chain.es_logs(addr, topics, frm, to)
            self._add(logs)
            self.truncated = self.truncated or trunc

    def _fetch_rpc(self, frm, to):
        """Public nodes cannot filter by 'any topic': Mine takes all dSOS logs (and the ledger's
        SignatureRecorded) and keeps the transactions that mention the address."""
        if self.scope == "contract":
            self._add(self.chain.rpc_logs(DSOS, [], frm, to))
            return
        got = self.chain.rpc_logs(DSOS, [], frm, to) + self.chain.rpc_logs(LEDGER, [T_RECORDED], frm, to)
        me = pad_topic(self.me)
        txs = {lg["tx"] for lg in got if me in lg["topics"][1:]}
        self._add([lg for lg in got if lg["tx"] in txs])

    def _load(self, hi):
        """Fetch the next piece of history ending at block `hi`; returns its first block."""
        if self.use_es:
            lo = 0 if self.scope == "mine" else max(0, hi - WINDOW_BLOCKS + 1)
            try:
                self._fetch_es(lo, hi)
                return lo
            except Exception as e:  # noqa: BLE001
                self.note = S.ACT_ES_FAILED.format(error=str(e) or type(e).__name__)
                self.use_es = False
                self.exact = False
        lo = max(0, hi - RPC_WINDOW + 1)
        self._fetch_rpc(lo, hi)
        return lo

    # -- public
    def refresh(self):
        """Newest data. With a key: Mine = whole history, Contract = last 7 days (Etherscan).
        Otherwise (or if Etherscan refuses): the last 2 days from the public nodes."""
        self.logs.clear()
        self.failed = []
        self.truncated = False
        self.note = ""
        self.latest = self.chain.block()
        self.use_es = bool(self.chain.api_key)
        self.exact = self.use_es
        self.lo = self._load(self.latest)
        self.complete = self.lo == 0
        if self.scope == "mine" and self.use_es:
            self._failed()
        self._times()

    def _failed(self):
        try:
            self.failed = [f for f in self.chain.failed_txs(self.me)
                           if self.lo is None or _hex_int(f.get("blockNumber")) >= self.lo]
        except Exception as e:  # noqa: BLE001
            self.failed = []
            self.note = str(e)

    def older(self):
        if self.complete or self.lo is None:
            return
        self.lo = self._load(self.lo - 1)
        self.complete = self.lo == 0
        if self.scope == "mine" and self.use_es:
            self._failed()
        self._times()

    def _times(self):
        """Fill in timestamps that the source did not give (RPC path)."""
        need = sorted({lg["block"] for lg in self.logs.values() if not lg["ts"]
                       and lg["block"] not in self.times}, reverse=True)[:MAX_BLOCK_LOOKUPS]
        if need:
            with ThreadPoolExecutor(max_workers=6) as ex:
                for b, t in zip(need, ex.map(self._one_time, need)):
                    if t:
                        self.times[b] = t

    def _one_time(self, b):
        try:
            return self.chain.block_time(b)
        except Exception:  # noqa: BLE001
            return 0

    def rows(self):
        now = time.time()
        logs = []
        for lg in self.logs.values():
            if not lg["ts"] and lg["block"] in self.times:
                lg = dict(lg, ts=self.times[lg["block"]])
            logs.append(lg)
        rows = build_rows(logs, self.me if self.scope == "mine" else "", self.failed)
        for r in rows:
            r["approx"] = False
            if not r["ts"] and self.latest:
                r["ts"] = int(now - max(0, self.latest - r["block"]) * core.BLOCK_TIME)
                r["approx"] = True
        return rows
