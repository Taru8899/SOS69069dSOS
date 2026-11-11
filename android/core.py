import time

import requests
from Crypto.Hash import keccak

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


def selector(sig):
    k = keccak.new(digest_bits=256)
    k.update(sig.encode())
    return k.digest()[:4]


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


def eth(wei):
    t = f"{wei / 1e18:.6f}".rstrip("0").rstrip(".")
    return t or "0"


def dur(blocks):
    if blocks <= 0:
        return "expired"
    sec = blocks * BLOCK_TIME
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    return f"{d}d {h}h" if d else (f"{h}h {m}m" if h else f"{m}m")


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
        raise RuntimeError(f"All RPCs failed: {last}")

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
            raise RuntimeError(f"Empty result for {sig}")
        return ws

    def load(self, address):
        a = address.strip().lower()
        if not (a.startswith("0x") and len(a) == 42):
            raise ValueError("Enter a valid 0x wallet address (42 characters)")
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
                "id": oid, "pos": pos, "kind": kind, "count": u(w[8]), "active": u(w[3]) != 0,
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
            "push": u(st[0]), "trust": u(st[1]), "effective": s(st[2]),
        }
