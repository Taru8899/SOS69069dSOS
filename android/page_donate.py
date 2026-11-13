"""Donate page: a plain ETH transfer to the dSOS contract (its receive() adds it to the pool)."""
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

import strings as S
import tx
from page_tx import TxScreen
from theme import BLACK, BLUE, LIGHT, WHITE
from widgets import Card, Choice, Overlay, RoundBtn, label, make_input


class DonateScreen(Overlay):
    """Builds the donation transaction. The wallet app signs and sends it."""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        col = BoxLayout(orientation="vertical")

        head = BoxLayout(size_hint_y=None, height=dp(72), padding=[dp(14), dp(10)], spacing=dp(14))
        back = RoundBtn(text=S.ICON_BACK, font_size="26sp", bold=True, bg=WHITE, color=BLACK,
                        size_hint=(None, 1), width=dp(56))
        back.bind(on_release=lambda *_: app.close_top())
        head.add_widget(back)
        head.add_widget(label(S.DONATE_TITLE, font_size="24sp"))
        col.add_widget(head)

        sv = ScrollView()
        form = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None,
                         padding=[dp(14), 0, dp(14), dp(14)])
        form.bind(minimum_height=form.setter("height"))
        form.add_widget(Card(S.DONATE_INTRO))

        self.amount_in = make_input(S.DONATE_HINT, "0.01")
        self.amount_in.bind(text=lambda *_: self.refresh())
        form.add_widget(self.amount_in)

        chips = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        for v in S.DONATE_AMOUNTS:
            ch = Choice(base=LIGHT, text=v)
            ch.bind(on_release=lambda _w, x=v: self.set_amount(x))
            chips.add_widget(ch)
        form.add_widget(chips)
        form.add_widget(Card(S.DONATE_NOTE))
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
        self.btn.bind(on_release=lambda *_: self.on_donate())
        foot.add_widget(self.btn)
        self.note = Label(text="", color=(0.8, 0.82, 0.82, 1), font_size="13sp",
                          halign="center", valign="middle")
        self.note.bind(size=lambda i, s: setattr(i, "text_size", s))
        foot.add_widget(self.note)
        col.add_widget(foot)

        self.add_widget(col)
        self.refresh()

    def set_amount(self, text):
        self.amount_in.text = text

    def problem(self):
        """'' when the amount is valid, else the text to show."""
        try:
            tx.parse_eth(self.amount_in.text)
        except ValueError as e:
            return str(e)
        return ""

    def refresh(self):
        err = self.problem()
        if err:
            self.btn.text = S.DONATE_BUTTON_EMPTY
            self.btn.set_enabled(False)
            self.note.text = err if self.amount_in.text.strip() else ""
        else:
            wei = tx.parse_eth(self.amount_in.text)
            self.btn.text = S.DONATE_BUTTON.format(eth=tx.eth_text(wei))
            self.btn.set_enabled(True)
            self.note.text = ""

    def on_donate(self):
        if self.problem():
            return
        try:
            t = tx.donate_tx(self.amount_in.text)
        except ValueError as e:
            self.note.text = str(e)
            return
        summary = S.DONATE_SUMMARY.format(eth=t["value_eth"])
        self.app.safe_overlay(lambda: TxScreen(self.app, t, summary, "", [], S.DONATE_TIP.format(
            eth=t["value_eth"]), S.DONATE_WARN))
