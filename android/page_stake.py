"""Stake tab: status and how staking works."""

import core
from widgets import Card


def build(app, b, d):
    b.add_widget(Card(
        f"[size=22sp][b]{'Staked' if d['staked'] else 'Not staked'}[/b][/size]\n"
        f"{'You can redeem credits now.' if d['can_redeem'] else 'Credits cannot be redeemed yet.'}\n\n"
        f"Cheapest gate offer right now:\n[b]{core.eth(d['stake_need_wei'])} ETH[/b] "
        f"(type G, delay 1 block)"))
    b.add_widget(Card(
        "[b]How staking works[/b]\n"
        "1. Create a G offer with delay 1 and a value above the gate requirement.\n"
        "2. Let it expire and sweep it. The ETH stays in the pool for good.\n"
        "3. You are staked forever, then wait 14,400 blocks (about 2 days) "
        "before your first credit redemption.\n\n"
        "Redeeming any part of a gate offer removes its gate flag, so you do not get staked."))
