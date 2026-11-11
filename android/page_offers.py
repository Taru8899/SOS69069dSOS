"""Offers tab: every offer you hold."""

import strings as S
from widgets import Card, offer_card, title_row


def build(app, b, d):
    b.add_widget(title_row(S.OFFERS_TITLE.format(n=len(d["offers"]))))
    if not d["offers"]:
        b.add_widget(Card(S.NO_ACTIVE_OFFERS))
    for o in d["offers"]:
        b.add_widget(offer_card(o))
    b.add_widget(Card(S.OFFERS_HELP))
