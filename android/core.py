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

    # ---------------------------------------------------------------- Activity (read-only)
    ACTIVITY_WINDOW = 50000       # bounded look-back; avoids provider range limits
    ACTIVITY_CHUNK = 5000
    ACTIVITY_EVENTS = {
        "OfferCreated": ("OfferCreated(uint256,address,uint8,address,address,uint256)", [2, 3]),
        "OfferTransferred": ("OfferTransferred(uint256,address,address)", [2, 3]),
        "OfferSplit": ("OfferSplit(uint256,uint256,uint256)", []),
        "OfferRedeemed": ("OfferRedeemed(uint256,address,address,uint256)", [2, 3]),
        "OfferSwept": ("OfferSwept(uint256,address,address,uint256)", [2, 3]),
        "Donation": ("Donation(address,uint256)", [1]),
        "CreditsFormed": ("CreditsFormed(address,uint256,uint256)", [1]),
        "CreditRedeemed": ("CreditRedeemed(address,uint256,uint256)", [1]),
        "LedgerRecordSkipped": ("LedgerRecordSkipped(address,address,bytes32,bytes)", [1, 2]),
        "GateFlagged": ("GateFlagged(uint256,bool)", []),
        "Staked": ("Staked(address,uint64)", [1]),
        "Transfer": ("Transfer(address,address,uint256)", [1, 2]),
        "SignatureRecorded": ("SignatureRecorded(address,address,bytes32,bytes,address,uint256,string)", [1, 2, 3]),
        "PushOverflow": ("PushOverflow(address,uint256)", [1]),
        "TrustOverflow": ("TrustOverflow(address,uint256)", [1]),
        "PhaseOverflow": ("PhaseOverflow(uint256)", []),
    }

    def _es_action(self, module, action, **kw):
        q = {"chainid": 1, "module": module, "action": action, "apikey": self.api_key, **kw}
        wait = 0.25 - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()
        j = self.s.get(ES_URL, params=q, timeout=20).json()
        status = str(j.get("status", "1"))
        result = j.get("result")
        if status == "0":
            if isinstance(result, list) and not result:
                return []
            if "no records" in str(result).lower():
                return []
            raise RuntimeError(str(j.get("message") or result or "Etherscan request failed"))
        return result if isinstance(result, list) else []

    def _es_logs(self, address, topics, from_block, to_block):
        """Etherscan V2 logs API. topics is a list of topic strings / None values."""
        kw = {"address": address, "fromBlock": int(from_block), "toBlock": int(to_block),
              "page": 1, "offset": 1000, "sort": "asc"}
        for i, topic in enumerate(topics[:4]):
            if topic:
                kw["topic" + str(i)] = topic
        out = []
        while True:
            rows = self._es_action("logs", "getLogs", **kw)
            out.extend(rows)
            if len(rows) < 1000:
                break
            kw["page"] += 1
            if kw["page"] > 20:
                break
        return out

    def _es_transactions(self, address, start_block=0, end_block=99999999):
        """Paginated normal transaction history. Used to identify failed Mine transactions."""
        if not self.api_key:
            return []
        out = []
        page = 1
        while page <= 10:
            rows = self._es_action("account", "txlist", address=address,
                                   startblock=int(start_block), endblock=int(end_block),
                                   page=page, offset=1000, sort="asc")
            out.extend(rows)
            if len(rows) < 1000:
                break
            page += 1
        return out

    @staticmethod
    def _topic_addr(topic):
        if not topic or len(topic) < 42:
            return ""
        return "0x" + topic[-40:].lower()

    @staticmethod
    def _log_words(data):
        raw = (data or "0x")[2:]
        return [raw[i:i + 64].rjust(64, "0") for i in range(0, len(raw), 64)]

    def _decode_activity_log(self, log, contract_kind):
        topics = log.get("topics") or []
        if not topics:
            return None
        topic0 = topics[0].lower()
        event = None
        for name, (sig, _) in self.ACTIVITY_EVENTS.items():
            if "0x" + keccak256(sig.encode()).hex() == topic0:
                event = name
                break
        if event is None:
            return None
        words_ = self._log_words(log.get("data", "0x"))
        indexed = topics[1:]
        def ix(n):
            return int(indexed[n - 1], 16) if len(indexed) >= n else 0
        def word(n):
            return int(words_[n], 16) if len(words_) > n else 0
        def addr_topic(n):
            return self._topic_addr(indexed[n - 1]) if len(indexed) >= n else ""
        item = {"event": event, "contract": contract_kind,
                "tx_hash": log.get("transactionHash", ""),
                "log_index": int(log.get("logIndex", "0x0"), 16),
                "block": int(log.get("blockNumber", "0x0"), 16),
                "addresses": [], "offer_id": None, "amount_wei": 0}
        if event == "OfferCreated":
            item.update(offer_id=ix(1), kind=word(1), donor=addr_topic(2),
                        to=addr_topic(3), amount_wei=word(2), owner="0x" + words_[0][-40:] if words_ else "")
            item["addresses"] = [item["donor"], item["to"], item["owner"]]
        elif event == "OfferTransferred":
            item.update(offer_id=ix(1), sender=addr_topic(2), to=addr_topic(3))
            item["addresses"] = [item["sender"], item["to"]]
        elif event == "OfferSplit":
            item.update(offer_id=ix(1), new_offer_id=ix(2), slices=word(0))
        elif event in ("OfferRedeemed", "OfferSwept"):
            item.update(offer_id=ix(1), donor=addr_topic(2), holder=addr_topic(3), amount_wei=word(0))
            item["addresses"] = [item["donor"], item["holder"]]
        elif event == "Donation":
            item.update(sender=addr_topic(1), amount_wei=word(0)); item["addresses"] = [item["sender"]]
        elif event == "CreditsFormed":
            item.update(user=addr_topic(1), formed=word(0), credits=word(1)); item["addresses"] = [item["user"]]
        elif event == "CreditRedeemed":
            item.update(user=addr_topic(1), credits=word(0), amount_wei=word(1)); item["addresses"] = [item["user"]]
        elif event == "LedgerRecordSkipped":
            item.update(signer=addr_topic(1), intended_to=addr_topic(2)); item["addresses"] = [item["signer"], item["intended_to"]]
        elif event == "GateFlagged":
            item.update(offer_id=ix(1), flagged=bool(word(0)))
        elif event == "Staked":
            item.update(user=addr_topic(1), at_block=word(0)); item["addresses"] = [item["user"]]
        elif event == "Transfer":
            item.update(sender=addr_topic(1), to=addr_topic(2), value=word(0)); item["addresses"] = [item["sender"], item["to"]]
            if contract_kind == "ledger":
                item["amount_wei"] = 0
        elif event == "SignatureRecorded":
            item.update(signer=addr_topic(1), intended_to=addr_topic(2), submitter=addr_topic(3),
                        payload_hash=(words_[0] if words_ else ""), timestamp=word(2))
            item["addresses"] = [item["signer"], item["intended_to"], item["submitter"]]
        elif event == "PushOverflow":
            item.update(signer=addr_topic(1), previous_count=word(0)); item["addresses"] = [item["signer"]]
        elif event == "TrustOverflow":
            item.update(intended_to=addr_topic(1), previous_count=word(0)); item["addresses"] = [item["intended_to"]]
        elif event == "PhaseOverflow":
            item.update(previous_total=word(0))
        return item

    def _get_logs(self, address, topics, from_block, to_block):
        """Bounded Etherscan-first / multi-RPC fallback. Topics is one exact topic filter."""
        if self.api_key:
            try:
                rows = self._es_logs(address, topics, from_block, to_block)
                self.source = "etherscan"
                return rows
            except Exception:
                pass
        out = []
        for start in range(int(from_block), int(to_block) + 1, self.ACTIVITY_CHUNK):
            end = min(int(to_block), start + self.ACTIVITY_CHUNK - 1)
            flt = {"address": address, "fromBlock": hex(start), "toBlock": hex(end)}
            if topics:
                flt["topics"] = topics
            out.extend(self._pub("eth_getLogs", [flt]))
        return out

    def _activity_logs(self, mine_address=None, from_block=None, to_block=None):
        latest = self.block()
        end = latest if to_block is None else min(int(to_block), latest)
        start = max(0, end - self.ACTIVITY_WINDOW) if from_block is None else max(0, int(from_block))
        contracts = ((DSOS, "dsos"), (LEDGER, "ledger"))
        all_logs = []
        successful_queries = 0
        mine = (mine_address or "").lower()
        for address, kind in contracts:
            names = ([n for n in self.ACTIVITY_EVENTS
                      if n not in ("SignatureRecorded", "PushOverflow", "TrustOverflow", "PhaseOverflow")]
                     if kind == "dsos" else
                     ["Transfer", "SignatureRecorded", "PushOverflow", "TrustOverflow", "PhaseOverflow"])
            topic_by_name = {n: "0x" + keccak256(self.ACTIVITY_EVENTS[n][0].encode()).hex() for n in names}
            if mine:
                if self.api_key:
                    # Etherscan: query each indexed wallet role using topic0 + the relevant topicN.
                    for name in names:
                        topic0 = topic_by_name[name]
                        for pos in self.ACTIVITY_EVENTS[name][1]:
                            topics = [topic0] + [None] * pos
                            topics[pos] = "0x" + mine[2:].rjust(64, "0")
                            try:
                                all_logs.extend(self._get_logs(address, topics, start, end))
                                successful_queries += 1
                            except Exception:
                                continue
                else:
                    # Public RPC: batch event signatures with the same indexed address position
                    # into OR-topic filters, reducing requests while preserving indexed-role search.
                    roles = {}
                    for name in names:
                        for pos in self.ACTIVITY_EVENTS[name][1]:
                            roles.setdefault(pos, []).append(topic_by_name[name])
                    wallet_topic = "0x" + mine[2:].rjust(64, "0")
                    for pos, topic0s in roles.items():
                        topics = [topic0s] + [None] * pos
                        topics[pos] = wallet_topic
                        try:
                            all_logs.extend(self._get_logs(address, topics, start, end))
                            successful_queries += 1
                        except Exception:
                            continue
                # Id-only/global events are added after matching transactions are known.
                unindexed = [n for n in names if not self.ACTIVITY_EVENTS[n][1]]
                for name in unindexed:
                    try:
                        all_logs.extend(self._get_logs(address, [topic_by_name[name]], start, end))
                        successful_queries += 1
                    except Exception:
                        continue
            else:
                if self.api_key:
                    for topic0 in topic_by_name.values():
                        try:
                            all_logs.extend(self._get_logs(address, [topic0], start, end))
                            successful_queries += 1
                        except Exception:
                            continue
                else:
                    try:
                        all_logs.extend(self._get_logs(address, [list(topic_by_name.values())], start, end))
                        successful_queries += 1
                    except Exception:
                        for topic0 in topic_by_name.values():
                            try:
                                all_logs.extend(self._get_logs(address, [topic0], start, end))
                                successful_queries += 1
                            except Exception:
                                continue
        if successful_queries == 0:
            raise RuntimeError("Unable to retrieve Activity logs from Etherscan or public RPC providers")
        decoded = {}
        for raw in all_logs:
            addr = (raw.get("address") or "").lower()
            kind = "ledger" if addr == LEDGER else "dsos"
            item = self._decode_activity_log(raw, kind)
            if item:
                key = (item["tx_hash"].lower(), item["log_index"])
                decoded[key] = item
        events = list(decoded.values())
        if mine:
            matching = {e["tx_hash"].lower() for e in events
                        if any(a.lower() == mine for a in e.get("addresses", []))}
            events = [e for e in events if e["tx_hash"].lower() in matching]
        return events, start, end

    def _block_timestamp(self, block_number, cache):
        if block_number not in cache:
            try:
                h = self._pub("eth_getBlockByNumber", [hex(int(block_number)), False])
                cache[block_number] = int(h.get("timestamp", "0x0"), 16) if h else 0
            except Exception:
                cache[block_number] = 0
        return cache[block_number]

    @staticmethod
    def _activity_title(events, failed=False):
        if failed:
            return "Failed transaction"
        names = {e["event"] for e in events}
        mapping = [("OfferCreated", "Created offer"), ("OfferTransferred", "Transferred offer"),
                   ("OfferSplit", "Split offer"), ("OfferRedeemed", "Redeemed offer"),
                   ("OfferSwept", "Swept offer"), ("Donation", "Donation"),
                   ("CreditsFormed", "Credits formed"), ("CreditRedeemed", "Redeemed credits"),
                   ("Staked", "Staked"), ("Transfer", "SOS ledger record")]
        for n, title in mapping:
            if n in names:
                return title
        return "Contract activity"

    def _group_activity(self, logs, address, timestamps, failed_txs=None):
        groups = {}
        for ev in logs:
            h = ev.get("tx_hash", "")
            if not h:
                continue
            groups.setdefault(h.lower(), []).append(ev)
        rows = []
        for h, events in groups.items():
            events.sort(key=lambda x: x.get("log_index", 0))
            block = events[0].get("block", 0)
            addresses = [a for e in events for a in e.get("addresses", []) if a]
            typ = events[0]["event"]
            amount = next((e.get("amount_wei", 0) for e in events if e.get("amount_wei", 0)), 0)
            offer_id = next((e.get("offer_id") for e in events if e.get("offer_id") is not None), None)
            mine = (address or "").lower()
            incoming = any((e.get("to") or e.get("holder") or e.get("intended_to") or "").lower() == mine
                           for e in events) if mine else False
            outgoing = any((e.get("sender") or e.get("donor") or e.get("signer") or "").lower() == mine
                           for e in events) if mine else False
            direction = "self" if incoming and outgoing else ("in" if incoming else ("out" if outgoing else "contract"))
            rows.append({"hash": h, "block": block, "timestamp": self._block_timestamp(block, timestamps),
                         "from": next((e.get("sender") or e.get("donor") or e.get("signer") for e in events if e.get("sender") or e.get("donor") or e.get("signer")), ""),
                         "to": next((e.get("to") or e.get("holder") or e.get("intended_to") for e in events if e.get("to") or e.get("holder") or e.get("intended_to")), ""),
                         "type": typ.lower(), "title": self._activity_title(events),
                         "contract": events[0].get("contract", "dsos"),
                         "amount_wei": amount, "direction": direction, "offer_id": offer_id,
                         "events": events, "failed": False})
        for txr in failed_txs or []:
            h = txr.get("hash", "").lower()
            if not h or h in groups or str(txr.get("isError", "0")) != "1":
                continue
            block = int(txr.get("blockNumber", 0) or 0)
            rows.append({"hash": h, "block": block, "timestamp": int(txr.get("timeStamp", 0) or 0),
                         "from": txr.get("from", ""), "to": txr.get("to", ""),
                         "type": "failed", "title": "Failed transaction", "amount_wei": int(txr.get("value", 0) or 0),
                         "direction": "out", "offer_id": None, "events": [], "failed": True})
        rows.sort(key=lambda x: (x["block"], x["timestamp"]), reverse=True)
        return rows

    def _decode_tx_input(self, data):
        """Decode selectors and the leading static arguments used by the existing tx.py."""
        if not isinstance(data, str) or len(data) < 10 or not data.startswith("0x"):
            return {"function": "Unknown", "args": {}}
        signatures = {
            "createOffer(uint8,address,uint256,bytes32,bytes,string)": "Create offer",
            "createOfferGated(address,uint256,bytes32,bytes32,bytes,string)": "Create gated offer",
            "sweepOffer(uint256)": "Sweep offer",
            "transfer(address,uint256)": "Transfer slices",
            "syncCredits()": "Sync credits",
            "redeemCredit(uint256,(bytes32,bytes,string))": "Redeem credits",
            "redeemSlices(uint256,uint256,bytes32,(bytes32,bytes,string))": "Redeem offer",
            "transferSlices(uint256,uint256,address,(bytes32,bytes,string))": "Transfer offer slices",
            "recordSignature(address,address,bytes32,bytes,string)": "Record SOS signature",
        }
        by_sel = {selector(sig).hex(): (sig, name) for sig, name in signatures.items()}
        sel = data[2:10].lower()
        if sel not in by_sel:
            return {"function": "Unknown (0x" + sel + ")", "args": {}}
        sig, name = by_sel[sel]
        ws = self._log_words("0x" + data[10:])
        def val(i): return int(ws[i], 16) if len(ws) > i else None
        def addr(i): return "0x" + ws[i][-40:].lower() if len(ws) > i else ""
        args = {}
        if sig.startswith("createOffer("):
            args = {"kind": val(0), "holder": addr(1), "delay": val(2)}
        elif sig.startswith("createOfferGated("):
            args = {"holder": addr(0), "slices": val(1)}
        elif sig.startswith("sweepOffer("):
            args = {"offer_id": val(0)}
        elif sig.startswith("transfer(address"):
            args = {"to": addr(0), "slices": val(1)}
        elif sig.startswith("redeemCredit("):
            args = {"credits": val(0)}
        elif sig.startswith("redeemSlices("):
            args = {"offer_id": val(0), "slices": val(1)}
        elif sig.startswith("transferSlices("):
            args = {"offer_id": val(0), "slices": val(1), "to": addr(2)}
        elif sig.startswith("recordSignature("):
            args = {"signer": addr(0), "intended_to": addr(1), "payload_hash": ws[2] if len(ws) > 2 else ""}
        return {"function": name, "args": args}

    def activity_mine(self, address, from_block=None, to_block=None):
        a = address.strip().lower()
        if not (a.startswith("0x") and len(a) == 42):
            raise ValueError(S.ERR_BAD_WALLET)
        logs, start, end = self._activity_logs(a, from_block, to_block)
        tx_records = []
        if self.api_key:
            try:
                tx_records = [r for r in self._es_transactions(a, start, end)
                              if r.get("to", "").lower() in (DSOS, LEDGER)]
            except Exception:
                tx_records = []
        failed = [r for r in tx_records if str(r.get("isError", "0")) == "1"]
        cache = {}
        rows = self._group_activity(logs, a, cache, failed)
        tx_map = {r.get("hash", "").lower(): r for r in tx_records if r.get("hash")}
        for row in rows:
            tr = tx_map.get(row["hash"].lower())
            if tr:
                decoded = self._decode_tx_input(tr.get("input", ""))
                row["function"] = decoded["function"]
                row["input_args"] = decoded["args"]
                row["gas_used"] = int(tr.get("gasUsed", 0) or 0)
                row["gas_price"] = int(tr.get("gasPrice", 0) or 0)
        return {"items": rows, "from_block": start, "to_block": end, "source": self.source,
                "failed_transactions_available": bool(self.api_key)}

    def activity_contract(self, from_block=None, to_block=None):
        logs, start, end = self._activity_logs(None, from_block, to_block)
        cache = {}
        rows = self._group_activity(logs, "", cache)
        return {"items": rows, "from_block": start, "to_block": end, "source": self.source,
                "failed_transactions_available": False}

