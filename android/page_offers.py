"""Offers tab: every offer you hold."""

from widgets import Card, offer_card, title_row


def build(app, b, d):
    b.add_widget(title_row(f"Offers ({len(d['offers'])})"))
    if not d["offers"]:
        b.add_widget(Card("No active offers."))
    for o in d["offers"]:
        b.add_widget(offer_card(o))
    b.add_widget(Card(
        "[b]How to read this[/b]\n"
        "Sendable = not a G offer and more than 7,200 blocks (about 1 day) left.\n"
        "Expired offers still count in your balance until someone sweeps them."))
