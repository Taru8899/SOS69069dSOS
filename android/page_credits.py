"""Credits tab: credits held, sync, staking status and redeem."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

import core
import strings as S
import tx
from page_tx import TxScreen
from theme import (BLACK, BLUE, DARK_GREEN, DARK_GREEN_HEX, LIGHT_BLUE, LIGHT_GREEN, PILL_BG,
                   RED, WHITE, short)
from widgets import Choice, Divider, Panel, Pill, RoundBtn, label


def word(n):
    return S.CREDITS_WORD_ONE if n == 1 else S.CREDITS_WORD_MANY


class CreditsPage:
    """Builds the Credits tab into box `b`. Keeps the redeem amount in self.amount."""

    def __init__(self, app, b, d):
        self.app = app
        self.d = d
        self.held = d["credits"]
        self.formable = d["formable"]
        self.maxc = self.held + self.formable          # redeemCredit forms pending ones first
        self.amount = min(1, self.maxc)
        left = d["staked_at"] + d["cooldown"] - d["block"]
        self.cool_left = left if d["staked"] else 0
        self.cool_ok = d["staked"] and left <= 0

        # ---- title + staked pill
        head = BoxLayout(size_hint_y=None, height=dp(48))
        head.add_widget(label(S.CREDITS_TITLE, font_size="30sp"))
        head.add_widget(Pill(
            text=S.CREDITS_PILL_STAKED if d["staked"] else S.CREDITS_PILL_NOT_STAKED,
            bg=PILL_BG, color=DARK_GREEN, bold=True, size_hint=(None, None),
            size=(dp(110), dp(34)), pos_hint={"center_y": 0.5}))
        b.add_widget(head)

        # ---- card 1: held + ready to form + sync
        c1 = Panel(orientation="vertical", size_hint_y=None, height=dp(214), spacing=dp(8))
        top = BoxLayout()
        top.add_widget(label(S.CREDITS_HELD_BOX.format(
            n=self.held, eth=core.eth(self.held * core.UNIT)), valign="top"))
        top.add_widget(label(S.CREDITS_READY_BOX.format(n=self.formable),
                             halign="right", valign="top"))
        c1.add_widget(top)
        sync = Choice(base=LIGHT_BLUE, text=S.CREDITS_SYNC, bold=True,
                      size_hint_y=None, height=dp(58))
        sync.set_enabled(bool(d["staked"] and self.formable > 0))
        sync.bind(on_release=lambda *_: self.on_sync())
        c1.add_widget(sync)
        b.add_widget(c1)

        # ---- card 2: staking facts
        c2 = Panel(orientation="vertical", size_hint_y=None, height=dp(4 * 52 + 3 + 28))
        self.pool_val = Label(markup=True, halign="right", valign="middle", color=BLACK)
        self.pool_val.bind(size=lambda i, s: setattr(i, "text_size", s))
        rows = [
            (S.CREDITS_ROW_STAKED_SINCE,
             f"{d['staked_at']:,}" if d["staked"] else S.CREDITS_DASH, None),
            (S.CREDITS_ROW_COOLDOWN.format(n=d["cooldown"]),
             (S.CREDITS_PASSED if self.cool_ok else
              (S.LEFT.format(time=core.dur(self.cool_left)) if d["staked"] else S.CREDITS_DASH)),
             DARK_GREEN_HEX if self.cool_ok else None),
            (S.CREDITS_ROW_POOL, None, None),
            (S.CREDITS_ROW_NONCE, f"{d['redeem_nonce']:,}", None),
        ]
        for i, (k, v, col) in enumerate(rows):
            r = BoxLayout(size_hint_y=None, height=dp(52))
            r.add_widget(label(k, font_size="16sp"))
            if k == S.CREDITS_ROW_POOL:
                r.add_widget(self.pool_val)
            else:
                txt = f"[b]{v}[/b]" if not col else f"[color={col}][b]{v}[/b][/color]"
                r.add_widget(label(txt, halign="right", font_size="16sp"))
            c2.add_widget(r)
            if i < len(rows) - 1:
                c2.add_widget(Divider())
        b.add_widget(c2)

        # ---- card 3: redeem
        c3 = Panel(orientation="vertical", size_hint_y=None, height=dp(272), spacing=dp(6))
        hd = BoxLayout(size_hint_y=None, height=dp(26))
        hd.add_widget(label(S.CREDITS_REDEEM_TITLE))
        hd.add_widget(label(S.CREDITS_RATE, halign="right"))
        c3.add_widget(hd)
        mid = BoxLayout(size_hint_y=None, height=dp(104))
        minus = RoundBtn(text=S.ICON_MINUS, font_size="34sp", bg=LIGHT_GREEN, color=BLACK,
                         size_hint=(None, 1), width=dp(70))
        minus.bind(on_release=lambda *_: self.set_amount(self.amount - 1))
        plus = RoundBtn(text=S.ICON_PLUS, font_size="30sp", bg=LIGHT_GREEN, color=BLACK,
                        size_hint=(None, 1), width=dp(70))
        plus.bind(on_release=lambda *_: self.set_amount(self.amount + 1))
        self.num = Label(markup=True, color=BLACK, halign="center", valign="middle")
        self.num.bind(size=lambda i, s: setattr(i, "text_size", s))
        mid.add_widget(minus)
        mid.add_widget(self.num)
        mid.add_widget(plus)
        c3.add_widget(mid)
        self.btn = Choice(base=BLUE, sel=BLUE, fg=WHITE, sel_fg=WHITE, bold=True,
                          font_size="18sp", size_hint_y=None, height=dp(58))
        self.btn.bind(on_release=lambda *_: self.on_redeem())
        c3.add_widget(self.btn)
        self.warn = Label(text="", markup=False, color=RED, font_size="13sp",
                          size_hint_y=None, height=dp(30), halign="center", valign="middle")
        self.warn.bind(size=lambda i, s: setattr(i, "text_size", s))
        c3.add_widget(self.warn)
        b.add_widget(c3)

        b.add_widget(label(S.CREDITS_FOOTNOTE, size_hint_y=None, height=dp(44),
                           halign="center", font_size="13sp"))
        self.refresh()

    # ---- state
    def set_amount(self, n):
        if self.maxc:
            self.amount = max(1, min(self.maxc, n))
        self.refresh()

    def pool_ok(self):
        d = self.d
        need = d["earmarked_wei"] + d["min_reserve_wei"] + max(self.amount, 1) * core.UNIT
        return d["pool_wei"] >= need

    def problem(self):
        d = self.d
        if not d["staked"]:
            return S.CREDITS_ERR_NOT_STAKED
        if not self.cool_ok:
            return S.CREDITS_ERR_COOLDOWN.format(time=core.dur(self.cool_left))
        if self.maxc < 1:
            return S.CREDITS_ERR_NONE
        if not self.pool_ok():
            return S.CREDITS_ERR_POOL
        return ""

    def refresh(self):
        n = self.amount
        self.num.text = S.CREDITS_AMOUNT.format(n=n, eth=core.eth(n * core.UNIT))
        ok = self.pool_ok()
        col = DARK_GREEN_HEX if ok else "b00021"
        self.pool_val.text = f"[color={col}][b]{S.YES if ok else S.NO}[/b][/color]"
        self.pool_val.font_size = "16sp"
        p = self.problem()
        self.btn.text = S.CREDITS_REDEEM_BTN.format(n=n, word=word(n))
        self.btn.set_enabled(not p)
        self.warn.text = p

    # ---- transactions (built, never sent)
    def on_sync(self):
        n = self.formable
        t = tx.sync_credits_tx()
        summary = S.SYNC_SUMMARY.format(n=n, word=word(n))
        self.app.safe_overlay(lambda: TxScreen(self.app, t, summary, S.SYNC_FN, [], S.SYNC_TIP,
                                       S.SYNC_WARN))

    def on_redeem(self):
        if self.problem():
            return
        d = self.d
        n = self.amount
        try:
            t = tx.redeem_credit_tx(d["address"], n, d["redeem_nonce"])
        except Exception as e:  # noqa: BLE001
            self.warn.text = str(e)
            return
        p = t["params"]
        summary = S.REDEEM_SUMMARY.format(n=n, word=word(n), eth=t["payout_eth"],
                                          nonce=d["redeem_nonce"])
        R = S.REDEEM_ROWS
        rows = [(R["n"], p["creditsToSpend"], p["creditsToSpend"]),
                (R["r"], p["r"], '["' + short(p["payloadHash"]) + '","0x",""]')]
        tip = S.REDEEM_TIP.format(nonce=d["redeem_nonce"], wallet=short(d["address"]))
        self.app.safe_overlay(lambda: TxScreen(self.app, t, summary, S.REDEEM_FN, rows, tip,
                                       S.REDEEM_WARN))


def build(app, b, d):
    CreditsPage(app, b, d)
