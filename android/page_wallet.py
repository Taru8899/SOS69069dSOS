"""Wallet tab (mockup layout): balance + chips, quick actions, next expiry, offers, pool."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout

import core
import strings as S
from theme import BLACK, BLUE, GRAY, LIGHT, RED, WHITE
from widgets import (Card, Choice, Dot, Icon, IconBtn, Panel, Ring, Tap, Tappable, label,
                     offer_row, title_row)


def chip(color, title, value, on_tap=None):
    """Small grey box that is a link: underlined title, then dot + bold value. Tap = open Offers
    with that filter."""
    p = Tappable(orientation="vertical", bg=LIGHT, padding=[dp(10), dp(8)], spacing=dp(2))
    p.add_widget(label(f"[u]{title}[/u]", font_size="12sp", size_hint_y=None, height=dp(22)))
    row = BoxLayout(spacing=dp(6))
    row.add_widget(Dot(bg=color, text="", size=(dp(10), dp(10)), pos_hint={"center_y": 0.5}))
    row.add_widget(label(S.WALLET_CHIP_VALUE.format(n=value), font_size="17sp"))
    p.add_widget(row)
    if on_tap:
        p.bind(on_release=lambda *_: on_tap())
    return p


class BalanceCard(Panel):
    def __init__(self, d, app=None, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(246), spacing=dp(8), **kw)
        total = max(d["balance"], 1)
        rest = max(0, d["balance"] - d["sendable"] - d["expiring"] - d["expired"])
        top = BoxLayout(size_hint_y=None, height=dp(130))
        left = BoxLayout(orientation="vertical")
        trow = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(6))
        trow.add_widget(label(S.WALLET_BAL_TITLE, font_size="14sp", size_hint_x=None, width=dp(92)))
        more = Tap(size_hint_x=None, width=dp(96))
        more.add_widget(label(S.BAL_SHOW_MORE, font_size="14sp", color=BLUE))
        more.bind(on_release=lambda *_: app.open_economics() if app is not None else None)
        trow.add_widget(more)
        left.add_widget(trow)
        left.add_widget(label(S.WALLET_BAL_BIG.format(n=d["balance"])))
        left.add_widget(label(S.WALLET_ETH.format(eth=core.eth(d["value_wei"])),
                              font_size="15sp", size_hint_y=None, height=dp(28)))
        top.add_widget(left)
        self.ring = Ring(size_hint=(None, 1), width=dp(112))
        self.ring.set_parts([(d["sendable"] / total, BLUE), (d["expiring"] / total, BLACK),
                             (d["expired"] / total, RED), (rest / total, GRAY)])
        top.add_widget(self.ring)
        self.add_widget(top)
        chips = BoxLayout(size_hint_y=None, height=dp(76), spacing=dp(10))
        def go(f):
            return (lambda: app.open_offers(f)) if app is not None else None
        chips.add_widget(chip(BLUE, S.WALLET_CHIP_SENDABLE, d["sendable"], go("sendable")))
        chips.add_widget(chip(BLACK, S.WALLET_CHIP_EXPIRING, d["expiring"], go("expiring")))
        if d["expired"]:
            chips.add_widget(chip(RED, S.WALLET_CHIP_EXPIRED, d["expired"], go("expired")))
        self.add_widget(chips)


def action_btn(icon, name, on_release, bg=WHITE, fg=BLACK):
    box = BoxLayout(orientation="vertical", spacing=dp(2))
    btn = IconBtn(icon=icon, bg=bg, color=fg, icon_size=28)
    btn.bind(on_release=lambda *_: on_release())
    box.add_widget(btn)
    box.add_widget(label(f"[b]{name}[/b]", halign="center", size_hint_y=None,
                         height=dp(22), font_size="14sp"))
    return box


def next_expiry_card(app, d):
    n = sum(o["count"] for o in d["offers"] if o["sweepable_at"] == d["next_expiry"])
    left = d["next_expiry"] - d["block"]
    c = Tappable(bg=BLACK, padding=[dp(16), dp(10)], spacing=dp(14), size_hint_y=None, height=dp(78))
    c.add_widget(Icon("clock", color=WHITE, size=(dp(30), dp(30)), pos_hint={"center_y": 0.5}))
    c.add_widget(label(S.WALLET_NEXT.format(n=n, time=core.dur(left), block=d["next_expiry"]),
                       color=WHITE, font_size="15sp"))
    c.add_widget(Icon("chevron", color=WHITE, size=(dp(24), dp(24)), pos_hint={"center_y": 0.5}))
    c.bind(on_release=lambda *_: app.set_page("offers"))
    return c


def build(app, b, d):
    b.add_widget(BalanceCard(d, app))
    acts = BoxLayout(size_hint_y=None, height=dp(104), spacing=dp(8))
    acts.add_widget(action_btn("send", S.ACTION_SEND, app.open_send, bg=BLUE, fg=WHITE))
    acts.add_widget(action_btn("plus", S.ACTION_CREATE, app.open_create))
    acts.add_widget(action_btn("recv", S.ACTION_REDEEM, app.open_redeem))
    acts.add_widget(action_btn("lock", S.ACTION_STAKE, lambda: app.set_page("stake")))
    b.add_widget(acts)
    if d["next_expiry"]:
        b.add_widget(next_expiry_card(app, d))
    b.add_widget(title_row(S.ACTIVE_OFFERS, S.LINK_SEE_ALL, lambda: app.set_page("offers")))
    if not d["offers"]:
        b.add_widget(Card(S.NO_ACTIVE_OFFERS))
    shown = sorted(d["offers"], key=lambda o: (o["left"] <= 0, o["sweepable_at"]))[:2]
    for o in shown:
        b.add_widget(offer_row(o, on_tap=lambda: app.set_page("offers")))
    pool = Panel(size_hint_y=None, height=dp(88), spacing=dp(10))
    pool.add_widget(label(S.SHARED_POOL.format(eth=core.eth(d.get("unalloc_wei", d["pool_wei"])),
                                      supply=d["supply"])))
    don = Choice(base=BLACK, fg=WHITE, text=S.BTN_DONATE, bold=True, size_hint=(None, None),
                 size=(dp(110), dp(52)), pos_hint={"center_y": 0.5})
    don.bind(on_release=lambda *_: app.open_donate())
    pool.add_widget(don)
    b.add_widget(pool)
