"""Redeem page: redeem slices of your offers, and sweep expired ones. Builds data, sends nothing."""
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

import core
import strings as S
import tx
from page_tx import TxScreen
from theme import BLACK, BLUE, LIGHT, WHITE, left_text, short
from widgets import Card, Choice, Overlay, Panel, RoundBtn, label


class RedeemScreen(Overlay):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        d = app.data
        self.d = d
        offers = d["offers"]
        # redeemable: still inside the window, and not gated (gated ones need a PIN)
        self.rows = [o for o in offers if o["left"] > 0 and o["kind"] != "G"]
        self.gated = [o for o in offers if o["left"] > 0 and o["kind"] == "G"]
        self.total = sum(o["count"] for o in self.rows)
        self.sel = self.rows[0] if self.rows else None   # list is sorted: soonest expiry first
        self.amount = 1 if self.sel else 0
        self.row_btns = {}

        col = BoxLayout(orientation="vertical")
        head = BoxLayout(size_hint_y=None, height=dp(72), padding=[dp(14), dp(10)], spacing=dp(14))
        back = RoundBtn(text=S.ICON_BACK, font_size="26sp", bold=True, bg=WHITE, color=BLACK,
                        size_hint=(None, 1), width=dp(56))
        back.bind(on_release=lambda *_: app.close_top())
        head.add_widget(back)
        head.add_widget(label(S.RO_TITLE, font_size="24sp"))
        col.add_widget(head)

        sv = ScrollView()
        form = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None,
                         padding=[dp(14), 0, dp(14), dp(14)])
        form.bind(minimum_height=form.setter("height"))

        av = Panel(size_hint_y=None, height=dp(84))
        av.add_widget(label(S.RO_AVAILABLE.format(n=self.total)))
        av.add_widget(label(S.RO_AVAILABLE_ETH.format(eth=core.eth(self.total * core.UNIT)),
                            halign="right", size_hint_x=0.6))
        form.add_widget(av)

        if self.rows:
            form.add_widget(label(S.RO_PICK, size_hint_y=None, height=dp(26)))
            for o in self.rows:
                btn = Choice(base=WHITE, text=S.RO_ROW.format(
                    kind=o["kind"], id=o["id"], left=left_text(o["left"]), count=o["count"]),
                    size_hint_y=None, height=dp(52), halign="left", padding_x=dp(16))
                btn.bind(size=lambda i, s: setattr(i, "text_size", (s[0] - dp(32), s[1])))
                btn.bind(on_release=lambda _w, x=o: self.pick(x))
                self.row_btns[o["id"]] = btn
                form.add_widget(btn)

            am = Panel(orientation="vertical", size_hint_y=None, height=dp(190), spacing=dp(6))
            mid = BoxLayout(size_hint_y=None, height=dp(94))
            minus = RoundBtn(text=S.ICON_MINUS, font_size="34sp", bg=BLACK, color=WHITE,
                             size_hint=(None, 1), width=dp(64))
            minus.bind(on_release=lambda *_: self.set_amount(self.amount - 1))
            plus = RoundBtn(text=S.ICON_PLUS, font_size="30sp", bg=BLACK, color=WHITE,
                            size_hint=(None, 1), width=dp(64))
            plus.bind(on_release=lambda *_: self.set_amount(self.amount + 1))
            self.num = Label(text="", markup=True, color=BLACK, halign="center", valign="middle")
            self.num.bind(size=lambda i, s: setattr(i, "text_size", s))
            mid.add_widget(minus)
            mid.add_widget(self.num)
            mid.add_widget(plus)
            am.add_widget(mid)
            self.chips_box = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
            am.add_widget(self.chips_box)
            form.add_widget(am)
        else:
            self.num = Label(text="")
            self.chips_box = BoxLayout()

        if self.gated:
            form.add_widget(Card(S.RO_GATED.format(
                n=len(self.gated), s="" if len(self.gated) == 1 else "s",
                slices=sum(o["count"] for o in self.gated)), bg=BLACK, fg=WHITE))

        # expired offers: sweep
        ids = d["sweepable_ids"]
        if ids:
            form.add_widget(label(S.RO_SWEEP_TITLE, size_hint_y=None, height=dp(30)))
            form.add_widget(label(S.RO_SWEEP_HELP, size_hint_y=None, height=dp(44),
                                  valign="top", font_size="13sp"))
            known = {o["id"]: o for o in offers}
            for i, oid in enumerate(ids[:10]):
                o = known.get(oid)
                r = Panel(size_hint_y=None, height=dp(62), spacing=dp(8))
                r.add_widget(label(
                    S.RO_SWEEP_ROW.format(id=oid, kind=o["kind"], count=o["count"]) if o
                    else S.RO_SWEEP_ROW_UNKNOWN.format(id=oid)))
                sb = Choice(base=LIGHT, text=S.RO_SWEEP_BTN, bold=True, size_hint=(None, 1),
                            width=dp(90))
                sb.bind(on_release=lambda _w, k=oid, n=i + 1: self.on_sweep(k, n, len(ids)))
                r.add_widget(sb)
                form.add_widget(r)

        sv.add_widget(form)
        col.add_widget(sv)

        foot = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(124),
                         padding=[dp(14), dp(12)], spacing=dp(8))
        with foot.canvas.before:
            Color(*BLACK)
            fbg = Rectangle()
        foot.bind(pos=lambda i, p: setattr(fbg, "pos", p),
                  size=lambda i, s: setattr(fbg, "size", s))
        self.btn = Choice(base=BLUE, sel=BLUE, fg=WHITE, sel_fg=WHITE, bold=True,
                          font_size="18sp", size_hint_y=None, height=dp(58))
        self.btn.bind(on_release=lambda *_: self.on_redeem())
        foot.add_widget(self.btn)
        self.note = Label(text="", color=(0.8, 0.82, 0.82, 1), font_size="13sp",
                          halign="center", valign="middle")
        self.note.bind(size=lambda i, s: setattr(i, "text_size", s))
        foot.add_widget(self.note)
        col.add_widget(foot)

        self.add_widget(col)
        self.refresh()

    # ---- state
    def pick(self, o):
        self.sel = o
        self.amount = min(max(self.amount, 1), o["count"])
        self.refresh()

    def set_amount(self, n):
        if self.sel:
            self.amount = max(1, min(self.sel["count"], n))
        self.refresh()

    def problem(self):
        if not self.sel:
            return S.RO_ERR_NONE
        if not 1 <= self.amount <= self.sel["count"]:
            return S.RO_ERR_AMOUNT
        return ""

    def refresh(self):
        for oid, btn in self.row_btns.items():
            btn.set_selected(bool(self.sel) and oid == self.sel["id"])
        n = self.amount
        self.num.text = S.RO_AMOUNT.format(n=n, eth=core.eth(n * core.UNIT)) if self.sel else ""
        # chips: 1 and Max for the selected offer
        self.chips_box.clear_widgets()
        if self.sel:
            top = self.sel["count"]
            values = [1] if top > 1 else []
            values.append(top)
            for v in values:
                ch = Choice(base=LIGHT, text=S.RO_MAX.format(n=v) if v == top else str(v))
                ch.set_selected(v == n)
                ch.bind(on_release=lambda _w, x=v: self.set_amount(x))
                self.chips_box.add_widget(ch)
        p = self.problem()
        self.btn.text = S.RO_BUTTON.format(n=n) if self.sel else S.RO_BUTTON_EMPTY
        self.btn.set_enabled(not p)
        self.note.text = p or S.RO_NOTE.format(block=self.sel["sweepable_at"])

    # ---- transactions (built, never sent)
    def on_redeem(self):
        if self.problem():
            return
        o, n = self.sel, self.amount
        try:
            t = tx.redeem_slices_tx(o["id"], n)
        except Exception as e:  # noqa: BLE001
            self.note.text = str(e)
            return
        p = t["params"]
        R = S.RO_ROWS
        rows = [(R["id"], p["id"], p["id"]), (R["slices"], p["slices"], p["slices"]),
                (R["pin"], p["pin"], short(p["pin"])),
                (R["r"], p["r"], '["' + short(p["payloadHash"]) + '","0x",""]')]
        summary = S.RO_SUMMARY.format(n=n, id=o["id"], kind=o["kind"], eth=t["payout_eth"])
        tip = S.RO_TIP.format(wallet=short(self.d["address"]), block=o["sweepable_at"])
        self.app.safe_overlay(lambda: TxScreen(self.app, t, summary, S.RO_FN, rows, tip, S.RO_WARN))

    def on_sweep(self, oid, pos, total):
        t = tx.sweep_offer_tx(oid)
        summary = S.SWEEP_SUMMARY.format(id=oid, pos=pos, total=total)
        rows = [(S.SWEEP_ROWS["id"], str(oid), str(oid))]
        self.app.safe_overlay(lambda: TxScreen(self.app, t, summary, S.SWEEP_FN, rows,
                                       S.SWEEP_TIP, S.SWEEP_WARN))
