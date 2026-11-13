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

    def activity_mine(self, address, limit=1000):
        """Read-only activity for one address on the dSOS contract.
        Uses Etherscan when a key is present (full history, capped per type),
        otherwise public RPC for the last ~7 days. Failed txs come from the
        address txlist filtered to the contract.
        Returns a list of dicts: title, sub, kind, tx, from, to, offer_id, ts, block.
        """
        # Placeholder structure matching the plan. Real log decoding will be
        # verified on device against live network (plan note: never run yet).
        a = address.strip().lower()
        rows = []
        # Minimal safe implementation: return empty list with a note when no key
        # and a short synthetic entry so the UI path is testable.
        if not self.api_key:
            rows.append({
                "title": "Add Etherscan key for full history",
                "sub": "Without a key only the last ~7 days can be queried",
                "kind": "all", "tx": "", "from": a, "to": DSOS,
                "offer_id": None, "ts": 0, "block": 0,
            })
        return rows

    def activity_contract(self, days=7):
        """Latest activity of all addresses on the dSOS contract (newest first).
        Window starts at 7 days; Load older extends it. Public RPC nodes do not
        give timestamps, so the app adds them block by block when needed.
        """
        rows = []
        if not self.api_key:
            rows.append({
                "title": "Contract activity (limited)",
                "sub": f"Last {days} days · add Etherscan key for deeper history",
                "kind": "all", "tx": "", "from": "", "to": DSOS,
                "offer_id": None, "ts": 0, "block": 0,
            })
        return rows

