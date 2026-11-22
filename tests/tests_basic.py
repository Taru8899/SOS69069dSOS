from dsos.contracts import DSOS_SPEC, Contract
from dsos.service import fmt_blocks, wei_to_eth

ADDR = "0xbD08A73E02BA266f5cC8c4c6a08348d806e61f2C"


def test_balanceof_selector():
    c = Contract(None, ADDR, DSOS_SPEC)
    assert c.encode_call("balanceOf", ADDR)[:4].hex() == "70a08231"


def test_fmt():
    assert wei_to_eth(12 * 10**15) == "0.012"
    assert fmt_blocks(0) == "expired"
    assert fmt_blocks(1800) == "6h 0m"


def test_new_selectors():
    from eth_utils import function_signature_to_4byte_selector as sel
    assert sel("createOfferS(address,uint256,uint256)").hex()
    assert sel("redeemCredit(uint256,uint256)").hex()
