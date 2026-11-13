import time

import requests
from Crypto.Hash import keccak

import strings as S

DSOS = "0x7Bd7c427b3c69e2a09603573ac875987c61ECAB8".lower()
LEDGER = "0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A".lower()
ES_URL = "https://api.etherscan.io/v2/api"
PUBLIC_RPCS = [
    "https://ethereum-rpc.publicnode.com",
    "https://eth.llamarpc.com",
    "https://rpc.ankr.com/eth",
    "https://cloudflare-eth.com",
]
UNIT = 10**15
BLOCK_TIME = 12
WINDOW = 7200
KIND = {0: "G", 1: "B", 2: "T", 3: "P"}
MAX_OFFERS = 40

# every custom error of dSOS and of the SOS ledger (names only; 4-byte selectors are derived)
REVERT_NAMES = (
    "BadDelay", "BadOfferPin", "BadRedeemHash", "InsufficientCredits", "InsufficientSlices",
    "InvalidValue", "NoCredit", "NotEnoughSendable", "NotHolder", "NotStaked", "NotTransferable",
    "OfferNotActive", "PoolTooThin", "Reentrant", "SelfTransfer", "TooEarly", "TooManyOffers",
    "TransferFailed", "WindowClosed", "ZeroAddress", "ZeroAmount",
    "BatchTooLarge", "DuplicatePayloadHash", "EmptyBatch", "InvalidSignature", "LengthMismatch",
    "MetadataTooLong", "NoETHAccepted",
)
_REVERT_BY_SELECTOR = {}


def keccak256(data):
    k = keccak.new(digest_bits=256)
    k.update(data)
    return k.digest()


def selector(sig):
    return keccak256(sig.encode())[:4]


def enc(x):
    if isinstance(x, int):
        return x.to_bytes(32, "big")
    return bytes.fromhex(x[2:]).rjust(32, b"\0")


def words(hexstr):
    b = bytes.fromhex(hexstr[2:])
    return [b[i:i + 32] for i in range(0, len(b), 32)]


def u(w):
    return int.from_bytes(w, "big")


def s(w):
    v = int.from_bytes(w, "big")
    return v - (1 << 256) if v >> 255 else v


def revert_reason(err):
    """Read a JSON-RPC error object. Returns (False, name_or_text) for a revert,
    (False, 'InsufficientFunds') when the sender lacks ETH, or (True, None) when the error
    says nothing about this transaction (caller should try another node)."""
    if not _REVERT_BY_SELECTOR:
        for n in REVERT_NAMES:
            _REVERT_BY_SELECTOR[selector(n + "()").hex()] = n
    data = err.get("data") if isinstance(err, dict) else None
    if isinstance(data, dict):
        data = data.get("data")
    if isinstance(data, str) and data.startswith("0x") and len(data) >= 10:
        sel = data[2:10].lower()
        return False, _REVERT_BY_SELECTOR.get(sel, "revert 0x" + sel)
    msg = str(err.get("message", "") if isinstance(err, dict) else err)
    low = msg.lower()
    if "insufficient funds" in low:
        return False, "InsufficientFunds"
    if "revert" in low:
        return False, "revert"
    return True, None


def eth(wei):
    t = f"{wei / 1e18:.6f}".rstrip("0").rstrip(".")
    return t or "0"


def dur(blocks):
    if blocks <= 0:
        return S.EXPIRED
    sec = blocks * BLOCK_TIME
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    return (S.DUR_DAYS.format(d=d, h=h) if d else
            (S.DUR_HOURS.format(h=h, m=m) if h else S.DUR_MINUTES.format(m=m)))


class NeedWindow(Exception):
    """A wide log query cannot be served without an Etherscan key: ask for a block window."""


class Chain:
    def __init__(self, api_key=""):
        self.api_key = (api_key or "").strip()
        self.s = requests.Session()
        self.source = "?"
        self._last = 0.0

    def _es(self, action, **kw):
        q = {"chainid": 1, "module": "proxy", "action": action,
             "apikey": self.api_key, **kw}
        wait = 0.25 - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()
        j = self.s.get(ES_URL, params=q, timeout=15).json()
        r = j.get("result")
        if not isinstance(r, str) or not r.startswith("0x"):
            raise RuntimeError(str(j.get("message") or r))
        return r

    def _pub(self, method, params):
        last = None
        for url in PUBLIC_RPCS:
            try:
                r = self.s.post(url, json={"jsonrpc": "2.0", "id": 1,
                                           "method": method, "params": params},
                                timeout=15)
                j = r.json()
                if "error" in j:
                    last = j["error"]
                    continue
                self.source = url.split("//")[1].split("/")[0]
                return j["result"]
            except Exception as e:  # noqa: BLE001
                last = e
        raise RuntimeError(S.ERR_ALL_RPC.format(error=last))

    # ------------------------------------------------------------ logs (Activity)
    def _es_api(self, module, action, **kw):
        """Etherscan call that returns a list (logs, txlist). [] when there is nothing."""
        q = {"chainid": 1, "module": module, "action": action, "apikey": self.api_key, **kw}
        wait = 0.25 - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()
        j = self.s.get(ES_URL, params=q, timeout=25).json()
        r = j.get("result")
        if isinstance(r, list):
            return r
        msg = str(j.get("message") or "")
        if "no records" in msg.lower() or "no transactions" in msg.lower():
            return []
        raise RuntimeError(str(r or msg))

    def get_logs(self, address, topics, frm, to):
        """Logs of `address` between two blocks. topics: [] or a list of None / 0x-hash.
        Returns (list of normalised logs, truncated). Etherscan first (with a key), then the
        public RPC (block windows only: a wide range raises NeedWindow)."""
        from activity import MAX_PAGES, norm_log
        topics = list(topics)
        while topics and topics[-1] is None:
            topics.pop()
        if self.api_key:
            try:
                q = {"address": address, "fromBlock": frm, "toBlock": to,
                     "offset": 1000}
                given = [i for i, t in enumerate(topics) if t]
                for i in given:
                    q["topic%d" % i] = topics[i]
                for a, b in zip(given, given[1:]):
                    q["topic%d_%d_opr" % (a, b)] = "and"
                for a in given:
                    for b in given:
                        if a < b and "topic%d_%d_opr" % (a, b) not in q:
                            q["topic%d_%d_opr" % (a, b)] = "and"
                out = []
                for page in range(1, MAX_PAGES + 1):
                    rows = self._es_api("logs", "getLogs", page=page, **q)
                    out.extend(norm_log(r) for r in rows)
                    if len(rows) < 1000:
                        return out, False
                return out, True
            except Exception:  # noqa: BLE001
                pass
        if to - frm > 2 * 50400:
            raise NeedWindow()
        return self._logs_rpc(address, topics, frm, to), False

    def _logs_rpc(self, address, topics, frm, to, depth=0):
        from activity import norm_log
        flt = {"address": address, "fromBlock": hex(frm), "toBlock": hex(to),
               "topics": [t for t in topics]}
        try:
            res = self._pub("eth_getLogs", [flt])
        except RuntimeError:
            if depth >= 4 or to - frm < 2:
                raise
            mid = (frm + to) // 2          # node refused: ask for two smaller windows
            return (self._logs_rpc(address, topics, frm, mid, depth + 1)
                    + self._logs_rpc(address, topics, mid + 1, to, depth + 1))
        return [norm_log(r) for r in res]

    def failed_txs(self, address):
        """The address's failed transactions to the dSOS contract (needs an Etherscan key)."""
        rows = self._es_api("account", "txlist", address=address, startblock=0,
                            endblock=99999999, page=1, offset=1000, sort="desc")
        return [r for r in rows if r.get("isError") == "1"
                and (r.get("to") or "").lower() == DSOS]

    def block_time(self, number):
        r = self._pub("eth_getBlockByNumber", [hex(number), False])
        return int(r["timestamp"], 16) if r else 0

    def block(self):
        if self.api_key:
            try:
                r = self._es("eth_blockNumber")
                self.source = "etherscan"
                return int(r, 16)
            except Exception:  # noqa: BLE001
                pass
        return int(self._pub("eth_blockNumber", []), 16)

    def call(self, to, sig, args=()):
        data = "0x" + (selector(sig) + b"".join(enc(a) for a in args)).hex()
        res = None
        if self.api_key:
            try:
                res = self._es("eth_call", to=to, data=data, tag="latest")
                self.source = "etherscan"
            except Exception:  # noqa: BLE001
                res = None
        if res is None:
            res = self._pub("eth_call", [{"to": to, "data": data}, "latest"])
        ws = words(res)
        if not ws:
            raise RuntimeError(S.ERR_EMPTY_RESULT.format(sig=sig))
        return ws

    def simulate(self, frm, to, data, value_wei=0):
        """Dry-run a transaction with eth_call as `frm`. Returns (ok, reason). `reason` is the
        name of the contract error (e.g. 'NotStaked') or a short node message. Raises
        RuntimeError only when no node answered at all."""
        call = {"from": frm, "to": to, "data": data}
        if value_wei:
            call["value"] = hex(int(value_wei))
        last = None
        for url in PUBLIC_RPCS:
            try:
                r = self.s.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                                           "params": [call, "latest"]}, timeout=15)
                j = r.json()
            except Exception as e:  # noqa: BLE001
                last = e
                continue
            if "error" not in j:
                self.source = url.split("//")[1].split("/")[0]
                return True, ""
            ok, reason = revert_reason(j["error"])
            if reason is not None:
                self.source = url.split("//")[1].split("/")[0]
                return ok, reason
            last = j["error"]          # node-side trouble: try the next RPC
        raise RuntimeError(S.ERR_ALL_RPC.format(error=last))

    def pin_commitment(self, offer_id):
        """offerPinCommitment(id) as 32 raw bytes."""
        return self.call(DSOS, "offerPinCommitment(uint256)", [offer_id])[0]

    def load(self, address):
        a = address.strip().lower()
        if not (a.startswith("0x") and len(a) == 42):
            raise ValueError(S.ERR_BAD_WALLET)
        blk = self.block()
        c = self.call
        bal = u(c(DSOS, "balanceOf(address)", [a])[0])
        ws = c(DSOS, "offerIdsOf(address)", [a])
        ids = [u(x) for x in ws[2:2 + u(ws[1])]][-MAX_OFFERS:]

        offers = []
        for pos, oid in enumerate(ids):   # pos = place in the holder's list (newest = highest)
            w = c(DSOS, "offers(uint256)", [oid])
            kind = KIND.get(u(w[4]), "?")
            sweep = u(w[7])
            left = sweep - blk
            status = "expired" if left <= 0 else ("expiring" if left <= WINDOW else "redeemable")
            offers.append({
                "id": oid, "pos": pos, "kind": kind, "donor": "0x" + w[0][12:].hex(), "created_at": u(w[6]), "count": u(w[8]), "active": u(w[3]) != 0,
                "sweepable_at": sweep, "left": left, "status": status,
                "sendable": kind != "G" and left > WINDOW,
            })
        offers.sort(key=lambda o: o["sweepable_at"])
        live = [o for o in offers if o["left"] > 0]

        staked = u(c(DSOS, "staked(address)", [a])[0]) != 0
        can = u(c(DSOS, "canRedeem(address)", [a])[0]) != 0
        credits = u(c(DSOS, "redemptionCredits(address)", [a])[0])
        formable = u(c(DSOS, "formableCredits(address)", [a])[0])
        pool = u(c(DSOS, "poolBalance()")[0])
        supply = u(c(DSOS, "totalSupply()")[0])
        need = u(c(DSOS, "stakeRequirement()")[0])
        st = c(LEDGER, "statsOf(address)", [a])
        sw = c(DSOS, "sweepableOffers(address)", [a])
        sweepable_ids = [u(x) for x in sw[2:2 + u(sw[1])]]
        staked_at = u(c(DSOS, "stakedAt(address)", [a])[0])
        nonce = u(c(DSOS, "redeemNonce(address)", [a])[0])
        earmarked = u(c(DSOS, "totalEarmarked()")[0])
        reserve = u(c(DSOS, "MIN_RESERVE()")[0])
        cooldown = u(c(DSOS, "STAKE_COOLDOWN()")[0])

        return {
            "address": address.strip(), "block": blk, "source": self.source,
            "balance": bal, "value_wei": bal * UNIT,
            "sendable": sum(o["count"] for o in offers if o["sendable"]),
            "expiring": sum(o["count"] for o in offers if o["status"] == "expiring"),
            "expired": sum(o["count"] for o in offers if o["status"] == "expired"),
            "next_expiry": min((o["sweepable_at"] for o in live), default=None),
            "offers": offers, "staked": staked, "can_redeem": can,
            "credits": credits, "formable": formable,
            "pool_wei": pool, "supply": supply, "stake_need_wei": need,
            "sweepable_ids": sweepable_ids, "staked_at": staked_at, "redeem_nonce": nonce, "earmarked_wei": earmarked,
            "min_reserve_wei": reserve, "cooldown": cooldown,
            "push": u(st[0]), "trust": u(st[1]), "effective": s(st[2]),
        }
