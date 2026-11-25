"""Donate page: a plain ETH transfer to the dSOS contract (its receive() adds it to the pool)."""
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

import core
import strings as S
import tx
from page_tx import TxScreen
from design import NOTE_GRAY, FONT_HELPER
from design import FONT_TITLE
from theme import BLACK, BLUE, LIGHT, WHITE
from widgets import home_btn, PullScroll, Card, Choice, Overlay, Panel, IconBtn, label, make_input


class DonateScreen(Overlay):
    """Builds the donation transaction. The wallet app signs and sends it."""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        col = BoxLayout(orientation="vertical")

        head = BoxLayout(size_hint_y=None, height=dp(64), padding=[0, dp(8)], spacing=dp(6))
        back = IconBtn(icon="back", bg=WHITE, color=BLACK,
                        size_hint=(None, 1), width=dp(44))
        back.bind(on_release=lambda *_: app.close_top())
        head.add_widget(home_btn(app))
        head.add_widget(back)
        head.add_widget(label(S.DONATE_TITLE, font_size=FONT_TITLE))

        sv = PullScroll(on_pull=app.pull_overlay)
        form = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None,
                         padding=[dp(14), 0, dp(14), dp(14)])
        form.bind(minimum_height=form.setter("height"))
        form.add_widget(head)          # the title row scrolls with the page
        self.form = form
        form.add_widget(Card(S.DONATE_INTRO))

        self.slices = 10
        self.custom = False
        sl = Panel(orientation="vertical", size_hint_y=None, height=dp(196), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(24))
        top.add_widget(label(S.DONATE_SLICES))
        top.add_widget(label(S.CREATE_EACH, halign="right"))
        sl.add_widget(top)
        mid = BoxLayout(size_hint_y=None, height=dp(84))
        minus = IconBtn(icon="minus", bg=BLACK, color=WHITE, size_hint=(None, 1), width=dp(72))
        minus.bind(on_release=lambda *_: self.set_slices(self.slices - 1))
        plus = IconBtn(icon="plus", bg=BLACK, color=WHITE, size_hint=(None, 1), width=dp(72))
        plus.bind(on_release=lambda *_: self.set_slices(self.slices + 1))
        self.num = Label(text="", markup=True, color=BLACK, halign="center", valign="middle")
        self.num.bind(size=lambda i, s: setattr(i, "text_size", s))
        mid.add_widget(minus)
        mid.add_widget(self.num)
        mid.add_widget(plus)
        sl.add_widget(mid)
        chips = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.chips = {}
        for n in S.DONATE_AMOUNTS:
            ch = Choice(base=LIGHT, text=str(n))
            ch.bind(on_release=lambda _w, v=n: self.pick(v))
            self.chips[n] = ch
            chips.add_widget(ch)
        self.custom_chip = Choice(base=LIGHT, text=S.WINDOW_CUSTOM)
        self.custom_chip.bind(on_release=lambda *_: self.pick_custom())
        chips.add_widget(self.custom_chip)
        sl.add_widget(chips)
        form.add_widget(sl)
        self.custom_in = make_input(S.DONATE_HINT, "", filt="int")
        self.custom_in.bind(text=lambda *_: self.on_custom_text())
        form.add_widget(self.custom_in)
        self._place_custom()
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
        self.note = Label(text="", color=NOTE_GRAY, font_size=FONT_HELPER, bold=True,
                          halign="center", valign="middle")
        self.note.bind(size=lambda i, s: setattr(i, "text_size", s))
        foot.add_widget(self.note)
        col.add_widget(foot)

        self.add_widget(col)
        self.refresh()

    def _place_custom(self):
        """The custom input is only in the layout while 'Custom' is picked."""
        f = self.custom_in.parent
        if self.custom and f is None:
            self.form.add_widget(self.custom_in, index=1)   # right under the note card
        elif not self.custom and f is not None:
            f.remove_widget(self.custom_in)

    def set_slices(self, n):
        self.slices = max(1, min(100000, n))
        if self.custom and self.custom_in.text != str(self.slices):
            self.custom_in.text = str(self.slices)
        self.refresh()

    def pick(self, n):
        self.custom = False
        self._place_custom()
        self.set_slices(n)

    def pick_custom(self):
        self.custom = True
        self.custom_in.text = str(self.slices)
        self._place_custom()
        self.refresh()

    def on_custom_text(self):
        t = self.custom_in.text.strip()
        if t.isdigit() and int(t) >= 1:
            self.slices = min(100000, int(t))
        self.refresh()

    def problem(self):
        """'' when the amount is valid, else the text to show."""
        if self.custom:
            t = self.custom_in.text.strip()
            if not (t.isdigit() and int(t) >= 1):
                return S.DONATE_BAD
        return ""

    def amount_text(self):
        return core.eth(self.slices * core.UNIT)

    def refresh(self):
        err = self.problem()
        self.num.text = S.DONATE_VALUE.format(n=self.slices, eth=self.amount_text())
        for n, c in self.chips.items():
            c.set_selected(not self.custom and n == self.slices)
        self.custom_chip.set_selected(self.custom)
        if err:
            self.btn.text = S.DONATE_BUTTON_EMPTY
            self.btn.set_enabled(False)
            self.note.text = err if self.custom_in.text.strip() else ""
        else:
            self.btn.text = S.DONATE_BUTTON.format(eth=self.amount_text())
            self.btn.set_enabled(True)
            self.note.text = ""

    def on_donate(self):
        if self.problem():
            return
        try:
            t = tx.donate_tx(self.amount_text())
        except ValueError as e:
            self.note.text = str(e)
            return
        summary = S.DONATE_SUMMARY.format(eth=t["value_eth"])
        self.app.open_overlay(TxScreen(self.app, t, summary, "", [], S.DONATE_TIP.format(
            eth=t["value_eth"]), S.DONATE_WARN))
