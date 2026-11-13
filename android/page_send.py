"""Send dSOS page (wallet transfer): builds the transaction data, sends nothing."""
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

import core
import strings as S
import tx
import util
from page_tx import TxScreen
from theme import BLACK, BLUE, DSOS_ADDR, LIGHT, WHITE, left_text, short
from widgets import PullScroll, Card, Choice, Overlay, Panel, RoundBtn, label, make_input


class SendScreen(Overlay):
    """Send dSOS page (wallet transfer). Builds the transaction data; it does not send anything."""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        d = app.data
        self.offers = d["offers"] if d else []
        self.held = d["balance"] if d else 0
        self.avail = tx.sendable_total(self.offers)
        self.amount = min(3, self.avail) if self.avail else 0

        col = BoxLayout(orientation="vertical")

        head = BoxLayout(size_hint_y=None, height=dp(72), padding=[dp(14), dp(10)], spacing=dp(14))
        back = RoundBtn(text=S.ICON_BACK, font_size="26sp", bold=True, bg=WHITE, color=BLACK,
                        size_hint=(None, 1), width=dp(56))
        back.bind(on_release=lambda *_: app.close_top())
        head.add_widget(back)
        head.add_widget(label(S.SEND_TITLE, font_size="24sp"))
        col.add_widget(head)

        sv = PullScroll()
        form = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None,
                         padding=[dp(14), 0, dp(14), dp(14)])
        form.bind(minimum_height=form.setter("height"))

        # available
        av = Panel(size_hint_y=None, height=dp(84))
        av.add_widget(label(S.SEND_AVAILABLE.format(avail=self.avail)))
        av.add_widget(label(S.SEND_OF_HELD.format(held=self.held, eth=core.eth(self.avail * core.UNIT)),
                            halign="right", size_hint_x=0.6))
        form.add_widget(av)

        # recipient
        form.add_widget(label(S.SEND_TO, size_hint_y=None, height=dp(26)))
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.to_in = make_input(S.HINT_RECIPIENT)
        self.to_in.bind(text=lambda *_: self.refresh())
        pb = Button(text=S.BTN_PASTE, size_hint=(None, 1), width=dp(72), background_normal="",
                    background_color=BLUE, color=WHITE, bold=True)
        pb.bind(on_release=lambda *_: self.paste_to())
        row.add_widget(self.to_in)
        row.add_widget(pb)
        form.add_widget(row)

        # amount
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
        chips = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.chips = {}
        values = [v for v in (1, 3, 5) if v < self.avail]
        if self.avail:
            values.append(self.avail)
        for v in values:
            text = S.SEND_MAX.format(n=v) if v == self.avail else str(v)
            ch = Choice(base=LIGHT, text=text)
            ch.bind(on_release=lambda _w, x=v: self.set_amount(x))
            self.chips[v] = ch
            chips.add_widget(ch)
        am.add_widget(chips)
        form.add_widget(am)

        # where the slices come from + warning (rebuilt on every change)
        self.dyn = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.dyn.bind(minimum_height=self.dyn.setter("height"))
        form.add_widget(self.dyn)

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
        self.btn.bind(on_release=lambda *_: self.on_send())
        foot.add_widget(self.btn)
        self.note = Label(text="", color=(0.8, 0.82, 0.82, 1), font_size="13sp",
                          halign="center", valign="middle")
        self.note.bind(size=lambda i, s: setattr(i, "text_size", s))
        foot.add_widget(self.note)
        col.add_widget(foot)

        self.add_widget(col)
        self.refresh()

    def paste_to(self):
        t = util.paste_text()
        if t:
            self.to_in.text = t
        else:
            self.note.text = S.MSG_CLIPBOARD_EMPTY_DOT

    def set_amount(self, n):
        if self.avail:
            self.amount = max(1, min(self.avail, n))
        self.refresh()

    def problem(self):
        if not self.app.data:
            return S.SEND_ERR_NO_WALLET
        if self.avail < 1:
            return S.SEND_ERR_NOTHING
        a = self.to_in.text.strip()
        if not tx.valid_address(a):
            return S.SEND_ERR_ADDRESS
        low = a.lower()
        if low == self.app.addr.text.strip().lower():
            return S.SEND_ERR_SELF
        if low == core.DSOS:
            return S.SEND_ERR_CONTRACT
        if low == tx.ZERO_ADDR:
            return S.SEND_ERR_ZERO
        if not 1 <= self.amount <= self.avail:
            return S.SEND_ERR_AMOUNT
        return ""

    def refresh(self):
        n = self.amount
        self.num.text = S.SEND_AMOUNT.format(n=n, eth=core.eth(n * core.UNIT))
        for v, ch in self.chips.items():
            ch.set_selected(v == n)

        self.dyn.clear_widgets()
        if n:
            picks, _rest = tx.plan_send(self.offers, n)
            self.dyn.add_widget(label(S.SEND_TAKEN_FROM,
                                      size_hint_y=None, height=dp(30)))
            badge = {"B": "0033ff", "T": "0b0b0b", "P": "00a82d"}
            for o, take in picks:
                r = Panel(size_hint_y=None, height=dp(62), spacing=dp(8))
                r.add_widget(label(f"[color={badge.get(o['kind'], '0b0b0b')}][b]{o['kind']}[/b][/color]",
                                   size_hint_x=None, width=dp(26), font_size="20sp"))
                split = S.SEND_ROW_SPLIT if take < o["count"] else ""
                r.add_widget(label(S.SEND_ROW_ID.format(id=o["id"], left=left_text(o["left"]), split=split)))
                r.add_widget(label(S.SEND_ROW_AMOUNT.format(take=take), halign="right", size_hint_x=None, width=dp(80)))
                self.dyn.add_widget(r)
        (g_o, g_s), (s_o, s_s), (e_o, e_s) = tx.blocked_summary(self.offers)
        stuck = g_s + s_s + e_s
        if stuck:
            parts = []
            if g_o:
                parts.append(S.SEND_BLOCKED_GATED.format(n=g_o, s="s" if g_o > 1 else ""))
            if s_o:
                parts.append(S.SEND_BLOCKED_SHORT.format(n=s_o))
            if e_o:
                parts.append(S.SEND_BLOCKED_EXPIRED.format(n=e_o))
            self.dyn.add_widget(Card(
                S.SEND_BLOCKED.format(stuck=stuck, parts=S.SEND_BLOCKED_JOIN.join(parts)),
                bg=BLACK, fg=WHITE))

        p = self.problem()
        self.btn.text = S.SEND_BUTTON.format(n=n) if n else S.SEND_BUTTON_EMPTY
        self.btn.set_enabled(not p)
        self.note.text = p or S.SEND_NOTE

    def on_send(self):
        if self.problem():
            return
        to = self.to_in.text.strip()
        try:
            t = tx.transfer_tx(to, self.amount)
        except Exception as e:  # noqa: BLE001
            self.note.text = str(e)
            return
        summary = S.SEND_SUMMARY.format(n=self.amount,
                                        eth=core.eth(self.amount * core.UNIT), to=short(to))
        rows = [(S.SEND_ROWS["to"], to, short(to)),
                (S.SEND_ROWS["n"], str(self.amount), str(self.amount))]
        tip = S.SEND_TIP.format(token=short(DSOS_ADDR), n=self.amount)
        self.app.open_overlay(TxScreen(self.app, t, summary, S.SEND_FN, rows, tip, S.SEND_WARN))
