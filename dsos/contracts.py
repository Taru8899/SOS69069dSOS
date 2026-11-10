"""Tiny ABI layer (view functions only) + Multicall3 batching."""
from eth_abi import decode, encode
from eth_utils import function_signature_to_4byte_selector, to_checksum_address

from . import config
from .rpc import RpcError, RpcClient

# name -> (input types, output types)
DSOS_SPEC = {
    "name": ([], ["string"]),
    "symbol": ([], ["string"]),
    "decimals": ([], ["uint8"]),
    "totalSupply": ([], ["uint256"]),
    "balanceOf": (["address"], ["uint256"]),
    "poolBalance": ([], ["uint256"]),
    "totalEarmarked": ([], ["uint256"]),
    "unallocatedBalance": ([], ["uint256"]),
    "stakeRequirement": ([], ["uint256"]),
    "gateRequirement": ([], ["uint256"]),
    "nextOfferId": ([], ["uint64"]),
    "MIN_SEND_WINDOW": ([], ["uint256"]),
    "STAKE_COOLDOWN": ([], ["uint256"]),
    "UNIT": ([], ["uint256"]),
    "offerIdsOf": (["address"], ["uint256[]"]),
    "offerCountOf": (["address"], ["uint256"]),
    "sweepableOffers": (["address"], ["uint256[]"]),
    # donor, holder, principal, active, kind, recordHash, createdAt, sweepableAt, count
    "offers": (["uint256"], ["address", "address", "uint256", "bool", "uint8",
                             "bytes32", "uint64", "uint64", "uint256"]),
    "staked": (["address"], ["bool"]),
    "stakedAt": (["address"], ["uint64"]),
    "canRedeem": (["address"], ["bool"]),
    "redemptionCredits": (["address"], ["uint256"]),
    "formableCredits": (["address"], ["uint256"]),
    "pendingCredits": (["address"], ["uint256"]),
    "lastTrust": (["address"], ["uint256"]),
    "redeemNonce": (["address"], ["uint256"]),
}

LEDGER_SPEC = {
    "name": ([], ["string"]),
    "symbol": ([], ["string"]),
    "totalRecorded": ([], ["uint256"]),
    "trustCountOf": (["address"], ["uint256"]),
    "pushCountOf": (["address"], ["uint256"]),
    "effectiveOf": (["address"], ["int256"]),
    "statsOf": (["address"], ["uint256", "uint256", "int256"]),
}


def checksum(addr: str) -> str:
    return to_checksum_address(addr.lower())


class Contract:
    def __init__(self, rpc: RpcClient, address: str, spec: dict):
        self.rpc = rpc
        self.address = checksum(address)
        self.spec = spec

    def encode_call(self, name, *args) -> bytes:
        ins, _ = self.spec[name]
        sel = function_signature_to_4byte_selector(f"{name}({','.join(ins)})")
        return sel + encode(ins, list(args))

    def decode_result(self, name, raw: bytes):
        _, outs = self.spec[name]
        if not raw:
            raise RpcError(f"{name}: empty result (wrong address or network?)")
        vals = decode(outs, raw)
        return vals[0] if len(vals) == 1 else tuple(vals)

    def call(self, name, *args):
        data = "0x" + self.encode_call(name, *args).hex()
        res = self.rpc.eth_call(self.address, data)
        return self.decode_result(name, bytes.fromhex(res[2:]))


_AGG3_SELECTOR = function_signature_to_4byte_selector("aggregate3((address,bool,bytes)[])")


def multicall(rpc: RpcClient, calls, chunk_size=40):
    """calls: list of (Contract, fn_name, args_tuple). Returns list of results (None on failure)."""
    out = []
    for i in range(0, len(calls), chunk_size):
        chunk = calls[i:i + chunk_size]
        payload = [(c.address, True, c.encode_call(n, *a)) for c, n, a in chunk]
        data = "0x" + (_AGG3_SELECTOR + encode(["(address,bool,bytes)[]"], [payload])).hex()
        raw = bytes.fromhex(rpc.eth_call(config.MULTICALL3, data)[2:])
        (results,) = decode(["(bool,bytes)[]"], raw)
        for (ok, ret), (c, n, _a) in zip(results, chunk):
            try:
                out.append(c.decode_result(n, ret) if ok else None)
            except Exception:
                out.append(None)
    return out


def batch(rpc: RpcClient, calls):
    """Multicall3 if possible, otherwise sequential calls."""
    try:
        return multicall(rpc, calls)
    except Exception:
        res = []
        for c, n, a in calls:
            try:
                res.append(c.call(n, *a))
            except Exception:
                res.append(None)
        return res
