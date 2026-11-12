"""Wallet tab: balance, quick actions, next expiry, latest offers, pool."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

import core
import strings as S
from theme import BLACK, BLUE, GRAY, RED, WHITE
from widgets import Card, Choice, Panel, Ring, RoundBtn, label, offer_card, title_row


class BalanceCard(Panel):
    def __init__(self, d, **kw):
        super().__init__(size_hint_y=None, height=dp(176), **kw)
        total = max(d["balance"], 1)
        self.ring = Ring(size_hint=(None, 1), width=dp(112))
        rest = max(0, d["balance"] - d["sendable"] - d["expiring"] - d["expired"])
        self.ring.set_parts([
            (d["sendable"] / total, BLUE),
            (d["expiring"] / total, BLACK),
            (d["expired"] / total, RED),
            (rest / total, GRAY),
        ])
        lbl = Label(
            text=S.WALLET_BALANCE.format(
                balance=d["balance"], eth=core.eth(d["value_wei"]), sendable=d["sendable"],
                expiring=d["expiring"], expired=d["expired"]),
            markup=True, color=BLACK, halign="left", valign="top")
        lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
        self.add_widget(lbl)
        self.add_widget(self.ring)


def action_btn(icon, name, on_release, bg=WHITE, fg=BLACK):
    box = BoxLayout(orientation="vertical", spacing=dp(2))
    btn = RoundBtn(text=icon, font_size="26sp", bold=True, bg=bg, color=fg)
    btn.bind(on_release=lambda *_: on_release())
    box.add_widget(btn)
    box.add_widget(label(f"[b]{name}[/b]", halign="center", size_hint_y=None,
                         height=dp(20), font_size="14sp"))
    return box


def build(app, b, d):
    b.add_widget(BalanceCard(d))
    acts = BoxLayout(size_hint_y=None, height=dp(96), spacing=dp(8))
    acts.add_widget(action_btn(S.ICON_SEND, S.ACTION_SEND, app.open_send, bg=BLUE, fg=WHITE))
    acts.add_widget(action_btn(S.ICON_CREATE, S.ACTION_CREATE, app.open_create))
    acts.add_widget(action_btn(S.ICON_REDEEM, S.ACTION_REDEEM, app.open_redeem))
    acts.add_widget(action_btn(S.ICON_STAKE, S.ACTION_STAKE, lambda: app.set_page("stake")))
    b.add_widget(acts)
    if d["next_expiry"]:
        left = d["next_expiry"] - d["block"]
        b.add_widget(Card(
            S.NEXT_EXPIRY.format(time=core.dur(left), block=d["next_expiry"]),
            bg=BLACK, fg=WHITE))
    b.add_widget(title_row(S.ACTIVE_OFFERS, S.LINK_SEE_ALL, lambda: app.set_page("offers")))
    if not d["offers"]:
        b.add_widget(Card(S.NO_ACTIVE_OFFERS))
    for o in d["offers"][:2]:
        b.add_widget(offer_card(o))
    pool = Panel(size_hint_y=None, height=dp(88), spacing=dp(10))
    pool.add_widget(label(S.SHARED_POOL.format(eth=core.eth(d["pool_wei"]), supply=d["supply"])))
    don = Choice(base=BLACK, fg=WHITE, text=S.BTN_DONATE, bold=True, size_hint=(None, None),
                 size=(dp(110), dp(52)), pos_hint={"center_y": 0.5})
    don.bind(on_release=lambda *_: app.open_donate())
    pool.add_widget(don)
    b.add_widget(pool)
