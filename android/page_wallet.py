"""Wallet tab: balance, quick actions, next expiry, latest offers, pool."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

import core
from theme import BLACK, BLUE, GRAY, RED, WHITE
from widgets import Card, Panel, Ring, RoundBtn, label, offer_card, title_row


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
            text=(f"dSOS balance\n"
                  f"[size=44sp][b]{d['balance']:,}[/b][/size] dSOS\n"
                  f"= {core.eth(d['value_wei'])} ETH redeemable\n\n"
                  f"[color=0033ff][b]Sendable {d['sendable']:,}[/b][/color]   "
                  f"[b]Expiring <1d {d['expiring']:,}[/b]\n"
                  f"[color=b00021][b]Expired, unswept {d['expired']:,}[/b][/color]"),
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
    acts.add_widget(action_btn(">", "Send", app.open_send, bg=BLUE, fg=WHITE))
    acts.add_widget(action_btn("+", "Create", app.open_create))
    acts.add_widget(action_btn("<", "Redeem", lambda: app.coming("Redeem")))
    acts.add_widget(action_btn("o", "Stake", lambda: app.set_page("stake")))
    b.add_widget(acts)
    if d["next_expiry"]:
        left = d["next_expiry"] - d["block"]
        b.add_widget(Card(
            f"[b]Next expiry in ~{core.dur(left)}[/b]\n"
            f"Redeem before block {d['next_expiry']:,}",
            bg=BLACK, fg=WHITE))
    b.add_widget(title_row("Active offers", "See all", lambda: app.set_page("offers")))
    if not d["offers"]:
        b.add_widget(Card("No active offers."))
    for o in d["offers"][:2]:
        b.add_widget(offer_card(o))
    b.add_widget(Card(
        f"Shared pool\n[b]{core.eth(d['pool_wei'])} ETH[/b] - {d['supply']:,} dSOS active"))
