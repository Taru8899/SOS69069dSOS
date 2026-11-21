from dsos.contracts import DSOS_SPEC, Contract
from dsos.service import fmt_blocks, wei_to_eth

ADDR = "0x7Bd7c427b3c69e2a09603573ac875987c61ECAB8"


def test_balanceof_selector():
    c = Contract(None, ADDR, DSOS_SPEC)
    assert c.encode_call("balanceOf", ADDR)[:4].hex() == "70a08231"


def test_fmt():
    assert wei_to_eth(12 * 10**15) == "0.012"
    assert fmt_blocks(0) == "expired"
    assert fmt_blocks(1800) == "6h 0m"
