"""Economics page: the numbers of the contract and of the wallet at the block that was read."""
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout

import re

from kivy.uix.label import Label

import core
import strings as S
from design import (ECON_ROW_MIN_H, FONT_ECON_ETH, FONT_ECON_ROW, FONT_ECON_TITLE,
                    FONT_ECON_VALUE, FONT_TITLE)
from theme import BLACK, WHITE
from widgets import Divider, IconBtn, Overlay, Panel, PullScroll, label

DAY_BLOCKS = 7200
_ETH_PART = re.compile(r"(\d[\d.,]* ETH)")


def style_value(v):
    """Bold markup for a value: ETH amounts big, the rest (dSOS count, reasons) smaller."""
    out = []
    for part in _ETH_PART.split(v):
        if not part:
            continue
        size = FONT_ECON_ETH if _ETH_PART.fullmatch(part) else FONT_ECON_VALUE
        out.append("[size=%s]%s[/size]" % (size, part))
    return "[b]%s[/b]" % "".join(out)


def wrap_label(text, font_size, halign, size_hint_x):
    """A label that wraps to its width and reports its real height."""
    lab = Label(text=text, markup=True, color=BLACK, font_size=font_size, halign=halign, valign="middle",
                size_hint=(size_hint_x, None))
    lab.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
    lab.bind(texture_size=lambda i, ts: setattr(i, "height", ts[1]))
    return lab


def _eth(wei):
    return S.ECON_ETH.format(eth=core.eth(wei))


def _dsos(n):
    return S.ECON_ETH_DSOS.format(eth=core.eth(n * core.UNIT), n=n)


def payout_units(d):
    """How many credits' worth of ETH the pool can pay now (balance - earmarked - reserve)."""
    free = d["pool_wei"] - d["earmarked_wei"] - d["min_reserve_wei"]
    return max(0, free // core.UNIT)


def redeem_now(d):
    """(credits you can redeem now, why not or '')."""
    if not d["staked"]:
        return 0, S.ECON_WHY_NOT_STAKED
    end = d["staked_at"] + d["cooldown"]
    if d["block"] < end:
        return 0, S.ECON_WHY_COOLDOWN.format(block=end)
    if d["credits"] <= 0:
        return 0, S.ECON_WHY_NO_CREDITS
    n = min(d["credits"], payout_units(d))
    return n, (S.ECON_WHY_POOL if n < d["credits"] else "")


def groups(d):
    """[(group title, [(label, value), ...]), ...] built from the loaded data only."""
    unalloc = d.get("unalloc_wei", max(0, d["pool_wei"] - d["earmarked_wei"]))
    n_red, why = redeem_now(d)
    redeem = _dsos(n_red) + ((" (" + why + ")") if why else "")
    nxt = d["next_expiry"]
    contract = [
        (S.ECON_HELD, _eth(d["pool_wei"])),
        (S.ECON_PAYOUT, _dsos(payout_units(d))),
        (S.ECON_STAKE_NEED, _eth(d["stake_need_wei"])),
        (S.ECON_POOL, _eth(unalloc)),
        (S.ECON_OFFERS, _eth(d["earmarked_wei"]) + " · %s dSOS" % format(d["supply"], ",")),
    ]
    you = [
        (S.ECON_BALANCE, _dsos(d["balance"])),
        (S.ECON_SENDABLE, _dsos(d["sendable"])),
        (S.ECON_EXPIRING, _dsos(d["expiring"])),
        (S.ECON_EXPIRED, _dsos(d["expired"])),
        (S.ECON_CREDITS, _dsos(d["credits"])),
        (S.ECON_FORMABLE, _dsos(d["formable"])),
        (S.ECON_REDEEM_NOW, redeem),
        (S.ECON_STAKED, S.ECON_YES if d["staked"] else S.ECON_NO),
    ]
    if d["staked"]:
        you.append((S.ECON_COOLDOWN_END, "block {:,}".format(d["staked_at"] + d["cooldown"])))
    you.append((S.ECON_NEXT_EXPIRY, S.ECON_IN.format(block=nxt, time=core.dur(nxt - d["block"]))
                if nxt else S.ECON_NONE))
    you.append((S.ECON_TRUST, "%s / %s / %s" % (d["trust"], d["effective"], d["push"])))
    you.append((S.ECON_NONCE, str(d["redeem_nonce"])))
    you.append((S.ECON_PRODUCED, _dsos(d.get("produced", 0))))
    you.append((S.ECON_REDEEMED_AB, _dsos(d.get("redeemed", 0))))
    you.append((S.ECON_ALLOWANCE, _dsos(d.get("allowance", 0))))
    rules = [
        (S.ECON_UNIT, _eth(core.UNIT)),
        (S.ECON_RESERVE, _eth(d["min_reserve_wei"])),
        (S.ECON_COOLDOWN, S.ECON_BLOCKS_DAYS.format(n=d["cooldown"], days=round(d["cooldown"] / DAY_BLOCKS, 1))),
        (S.ECON_BLOCK, "{:,}".format(d["block"])),
    ]
    return [(S.ECON_G_CONTRACT, contract), (S.ECON_G_YOU, you), (S.ECON_G_RULES, rules)]


class EconomicsScreen(Overlay):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        col = BoxLayout(orientation="vertical")
        head = BoxLayout(size_hint_y=None, height=dp(64), padding=[dp(14), dp(4), dp(14), dp(6)],
                         spacing=dp(14))
        back = IconBtn(icon="back", bg=WHITE, color=BLACK, size_hint=(None, 1), width=dp(52))
        back.bind(on_release=lambda *_: app.close_top())
        head.add_widget(back)
        head.add_widget(label(S.ECON_TITLE, font_size=FONT_TITLE))
        col.add_widget(head)
        sv = PullScroll()
        box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None,
                        padding=[dp(14), 0, dp(14), dp(20)])
        box.bind(minimum_height=box.setter("height"))
        for title, rows in groups(app.data):
            p = Panel(orientation="vertical", size_hint_y=None, spacing=dp(0))
            p.bind(minimum_height=p.setter("height"))
            p.add_widget(label(title, size_hint_y=None, height=dp(34), font_size=FONT_ECON_TITLE))
            for i, (k, v) in enumerate(rows):
                r = BoxLayout(size_hint_y=None, height=dp(ECON_ROW_MIN_H), spacing=dp(8))
                name = wrap_label(k, FONT_ECON_ROW, "left", 1)
                val = wrap_label(style_value(v), FONT_ECON_VALUE, "right", 1)
                for w, anchor in ((name, "left"), (val, "right")):
                    cell = AnchorLayout(anchor_x=anchor, anchor_y="center", size_hint_x=0.5)
                    cell.add_widget(w)
                    r.add_widget(cell)
                    # the row grows with the taller of the two texts, both stay centred
                    w.bind(height=lambda *_, r=r, a=name, b=val:
                           setattr(r, "height", max(dp(ECON_ROW_MIN_H), a.height + dp(16), b.height + dp(16))))
                p.add_widget(r)
                if i < len(rows) - 1:
                    p.add_widget(Divider())
            box.add_widget(p)
        sv.add_widget(box)
        col.add_widget(sv)
        self.add_widget(col)
