"""JSON-RPC transport: Etherscan proxy first, public RPCs as fallback."""
import time

import requests

from . import config


class RpcError(Exception):
    pass


class RpcClient:
    ETHERSCAN_METHODS = {"eth_call", "eth_blockNumber", "eth_getBalance"}

    def __init__(self, api_key=None, public_rpcs=None, timeout=15, min_interval=0.25):
        self.api_key = config.ETHERSCAN_API_KEY if api_key is None else api_key
        self.public_rpcs = list(public_rpcs or config.PUBLIC_RPCS)
        self.timeout = timeout
        self.min_interval = min_interval
        self.session = requests.Session()
        self._last_es = 0.0
        self.last_source = None  # "etherscan" or the RPC url used last

    # ---- Etherscan (proxy module) ----
    def _etherscan(self, method, params):
        q = {"chainid": config.CHAIN_ID, "module": "proxy", "apikey": self.api_key}
        if method == "eth_call":
            q.update(action="eth_call", to=params[0]["to"], data=params[0]["data"], tag=params[1])
        elif method == "eth_blockNumber":
            q.update(action="eth_blockNumber")
        elif method == "eth_getBalance":
            q.update(action="eth_getBalance", address=params[0], tag=params[1])
        else:
            raise RpcError(f"etherscan: unsupported method {method}")

        wait = self.min_interval - (time.time() - self._last_es)
        if wait > 0:
            time.sleep(wait)
        self._last_es = time.time()

        r = self.session.get(config.ETHERSCAN_URL, params=q, timeout=self.timeout)
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            raise RpcError(f"etherscan: {j['error']}")
        res = j.get("result")
        if j.get("status") == "0" or not isinstance(res, str) or not res.startswith("0x"):
            raise RpcError(f"etherscan: {j.get('message')} {res}")
        return res

    # ---- Public RPCs ----
    def _public(self, method, params):
        last = None
        for url in self.public_rpcs:
            try:
                r = self.session.post(
                    url,
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                    timeout=self.timeout,
                )
                r.raise_for_status()
                j = r.json()
                if "error" in j:
                    last = RpcError(f"{url}: {j['error']}")
                    continue
                self.last_source = url
                return j["result"]
            except (requests.RequestException, ValueError) as e:
                last = RpcError(f"{url}: {e}")
        raise RpcError(f"all public RPCs failed: {last}")

    def request(self, method, params):
        if self.api_key and method in self.ETHERSCAN_METHODS:
            try:
                res = self._etherscan(method, params)
                self.last_source = "etherscan"
                return res
            except (RpcError, requests.RequestException, ValueError):
                pass  # fall back below
        return self._public(method, params)

    def block_number(self):
        return int(self.request("eth_blockNumber", []), 16)

    def eth_call(self, to, data):
        return self.request("eth_call", [{"to": to, "data": data}, "latest"])
