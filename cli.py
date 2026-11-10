#!/usr/bin/env python3
"""dSOS read-only CLI.  Examples:
    python cli.py summary 0x08E5aaCaFAeFEf90d048AE4f97Cd4A8690E85fEE
    python cli.py offers  0x08E5aaCaFAeFEf90d048AE4f97Cd4A8690E85fEE
    python cli.py pool
    python cli.py stake   0x08E5aaCaFAeFEf90d048AE4f97Cd4A8690E85fEE
    python cli.py summary  0x08E5aaCaFAeFEf90d048AE4f97Cd4A8690E85fEE-json
"""
import argparse
import dataclasses
import json
import sys

from dsos import config
from dsos.service import fmt_blocks, load_summary, wei_to_eth


def _addr(args):
    a = args.address or config.DEFAULT_WALLET
    if not a:
        sys.exit("Give a wallet address or set WALLET_ADDRESS in .env")
    return a


def cmd_summary(args):
    s = load_summary(_addr(args))
    if args.json:
        print(json.dumps(dataclasses.asdict(s), indent=2, default=str))
        return
    print(f"Wallet   {s.address}   (block {s.block:,} via {s.source})")
    print(f"Balance  {s.balance} dSOS  = {wei_to_eth(s.value_wei)} ETH redeemable")
    print(f"Sendable {s.sendable}   Expiring<1d {s.expiring}   Expired-unswept {s.expired}")
    if s.next_expiry_block:
        left = s.next_expiry_block - s.block
        print(f"Next expiry: block {s.next_expiry_block:,} (~{fmt_blocks(left)})")
    print(f"Staked   {s.staked}   can redeem credits: {s.can_redeem}")
    print(f"Credits  {s.credits} held + {s.formable} formable")


def cmd_offers(args):
    s = load_summary(_addr(args))
    if not s.offers:
        print("No active offers.")
    for o in s.offers:
        print(f"#{o.id:<6} {o.kind}  {o.count:>6} dSOS  {wei_to_eth(o.principal_wei):>10} ETH  "
              f"{fmt_blocks(o.blocks_left):>8}  {o.status:<10} sendable={o.sendable}  donor={o.donor}")


def cmd_pool(args):
    s = load_summary(_addr(args) if (args.address or config.DEFAULT_WALLET) else config.DSOS_ADDRESS)
    print(f"Pool balance    {wei_to_eth(s.pool_balance_wei)} ETH")
    print(f"Earmarked       {wei_to_eth(s.pool_earmarked_wei)} ETH")
    print(f"Unallocated     {wei_to_eth(s.pool_unallocated_wei)} ETH")
    print(f"Active dSOS     {s.pool_supply:,}")
    print(f"Stake needs     {wei_to_eth(s.stake_requirement_wei)} ETH (G offer, delay 1)")


def cmd_stake(args):
    s = load_summary(_addr(args))
    print(f"Staked: {s.staked}   since block {s.staked_at:,}")
    if s.staked and s.cooldown_blocks_left:
        print(f"Cooldown left: {fmt_blocks(s.cooldown_blocks_left)}")
    print(f"Stake requirement now: {wei_to_eth(s.stake_requirement_wei)} ETH")
    print(f"Ledger: push {s.ledger_push}  trust {s.ledger_trust}  effective {s.ledger_effective}")


def main():
    p = argparse.ArgumentParser(description="dSOS read-only tool")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in [("summary", cmd_summary), ("offers", cmd_offers),
                     ("pool", cmd_pool), ("stake", cmd_stake)]:
        sp = sub.add_parser(name)
        sp.add_argument("address", nargs="?")
        sp.add_argument("--json", action="store_true")
        sp.set_defaults(fn=fn)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
