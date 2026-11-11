"""Credits tab: credits, formable credits and the SOS ledger."""

import core
from theme import BLACK, WHITE
from widgets import Card


def build(app, b, d):
    b.add_widget(Card(
        f"Credits held\n[size=44sp][b]{d['credits']:,}[/b][/size]\n"
        f"+ {d['formable']:,} formable from SOS trust records\n"
        f"Worth up to [b]{core.eth((d['credits'] + d['formable']) * core.UNIT)} ETH[/b]"))
    b.add_widget(Card(
        f"[b]SOS ledger[/b]\n"
        f"Push {d['push']:,}   Trust {d['trust']:,}\n"
        f"Effective {d['effective']:,}"))
    b.add_widget(Card(
        "1 credit = 0.001 ETH. Credits come 1:1 from trust records, "
        "need a staked wallet, and cannot be transferred.",
        bg=BLACK, fg=WHITE))
    if not d["staked"]:
        b.add_widget(Card("This wallet is not staked, so it cannot form or redeem credits."))
