import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import core


class ActivityDecoderTests(unittest.TestCase):
    def setUp(self):
        self.chain = core.Chain("")

    def test_offer_transferred_event_decoding(self):
        sig = self.chain.ACTIVITY_EVENTS["OfferTransferred"][0]
        topic0 = "0x" + core.keccak256(sig.encode()).hex()
        sender = "0x1111111111111111111111111111111111111111"
        recipient = "0x2222222222222222222222222222222222222222"
        log = {
            "topics": [topic0, "0x" + (77).to_bytes(32, "big").hex(),
                       "0x" + bytes.fromhex(sender[2:]).rjust(32, b"\0").hex(),
                       "0x" + bytes.fromhex(recipient[2:]).rjust(32, b"\0").hex()],
            "data": "0x", "transactionHash": "0xabc", "logIndex": "0x1",
            "blockNumber": "0x100", "address": core.DSOS,
        }
        decoded = self.chain._decode_activity_log(log, "dsos")
        self.assertEqual(decoded["event"], "OfferTransferred")
        self.assertEqual(decoded["offer_id"], 77)
        self.assertEqual(decoded["sender"], sender)
        self.assertEqual(decoded["to"], recipient)

    def test_grouping_one_row_per_transaction(self):
        event = {"tx_hash": "0xabc", "log_index": 0, "block": 100,
                 "event": "OfferRedeemed", "contract": "dsos", "addresses": [],
                 "amount_wei": 10**15, "offer_id": 5}
        self.chain._block_timestamp = lambda block, cache: 123
        rows = self.chain._group_activity([event, dict(event, log_index=1)], "0x111", {})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["offer_id"], 5)

    def test_keccak_selector_matches_ethereum(self):
        self.assertEqual(core.selector("transfer(address,uint256)").hex(), "a9059cbb")

    def test_known_transaction_selector(self):
        selector = core.selector("sweepOffer(uint256)").hex()
        payload = "0x" + selector + (482).to_bytes(32, "big").hex()
        decoded = self.chain._decode_tx_input(payload)
        self.assertEqual(decoded["function"], "Sweep offer")
        self.assertEqual(decoded["args"]["offer_id"], 482)

    def test_unknown_selector_is_not_misclassified(self):
        decoded = self.chain._decode_tx_input("0x12345678")
        self.assertTrue(decoded["function"].startswith("Unknown"))

    def test_mine_queries_wallet_in_each_indexed_role(self):
        wallet = "0x1111111111111111111111111111111111111111"
        wallet_topic = "0x" + wallet[2:].rjust(64, "0")
        self.chain.block = lambda: 100000
        seen = []
        self.chain._get_logs = lambda address, topics, start, end: seen.append((address, topics)) or []
        events, start, end = self.chain._activity_logs(wallet)
        self.assertEqual(end, 100000)
        self.assertTrue(any(a == core.DSOS and isinstance(t[0], list) and len(t) > 2 and t[2] == wallet_topic
                            for a, t in seen))
        self.assertTrue(any(a == core.LEDGER and isinstance(t[0], list) and len(t) > 3 and t[3] == wallet_topic
                            for a, t in seen))

    def test_block_timestamp_is_cached(self):
        calls = []
        self.chain._pub = lambda method, params: calls.append((method, params)) or {"timestamp": "0x64"}
        cache = {}
        self.assertEqual(self.chain._block_timestamp(100, cache), 100)
        self.assertEqual(self.chain._block_timestamp(100, cache), 100)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
