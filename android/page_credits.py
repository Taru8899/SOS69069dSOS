"""Credits tab: credits, formable credits and the SOS ledger."""

import core
import strings as S
from theme import BLACK, WHITE
from widgets import Card


def build(app, b, d):
    b.add_widget(Card(S.CREDITS_HELD.format(
        credits=d["credits"], formable=d["formable"],
        eth=core.eth((d["credits"] + d["formable"]) * core.UNIT))))
    b.add_widget(Card(S.CREDITS_LEDGER.format(
        push=d["push"], trust=d["trust"], effective=d["effective"])))
    b.add_widget(Card(S.CREDITS_RULES, bg=BLACK, fg=WHITE))
    if not d["staked"]:
        b.add_widget(Card(S.CREDITS_NOT_STAKED))
