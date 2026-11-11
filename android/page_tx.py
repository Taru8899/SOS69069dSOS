"""Transaction ready page: shows the data to copy into a wallet or Etherscan."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.utils import escape_markup

import strings as S
import util
from theme import BLACK, BLUE, DAPP_URL, DSOS_ADDR, ETHERSCAN_WRITE, WHITE, short
from widgets import Card, Choice, Overlay, Panel, RoundBtn, label


class TxScreen(Overlay):
    """Shows the ready-to-send transaction with copy buttons."""

    def __init__(self, app, t, summary, fn_name, rows, tip="", warn="", **kw):
        super().__init__(**kw)
        self.app = app
        col = BoxLayout(orientation="vertical")
        head = BoxLayout(size_hint_y=None, height=dp(72), padding=[dp(14), dp(10)], spacing=dp(14))
        back = RoundBtn(text=S.ICON_BACK, font_size="26sp", bold=True, bg=WHITE, color=BLACK,
                        size_hint=(None, 1), width=dp(56))
        back.bind(on_release=lambda *_: app.close_top())
        head.add_widget(back)
        head.add_widget(label(S.TX_TITLE, font_size="24sp"))
        col.add_widget(head)

        self.status = label("", size_hint_y=None, height=dp(22), font_size="13sp",
                            padding=(dp(14), 0))
        col.add_widget(self.status)

        sv = ScrollView()
        box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None,
                        padding=[dp(14), 0, dp(14), dp(20)])
        box.bind(minimum_height=box.setter("height"))

        box.add_widget(Card(summary))
        box.add_widget(Card(S.TX_NOT_SENDER, bg=BLACK, fg=WHITE))

        data = t["data"]
        box.add_widget(self.copy_row(S.TX_TO, DSOS_ADDR, short(DSOS_ADDR)))
        if t["value_wei"]:
            box.add_widget(self.copy_row(S.TX_VALUE, t["value_eth"], S.TX_VALUE_SHOWN.format(eth=t["value_eth"])))
        box.add_widget(self.copy_row(S.TX_DATA, data, f"{data[:22]}...{data[-8:]}"))
        box.add_widget(label(S.TX_ETHERSCAN_HEAD.format(fn=fn_name),
                             size_hint_y=None, height=dp(30)))
        for title, value, shown in rows:
            box.add_widget(self.copy_row(title, value, shown))
        if tip:
            box.add_widget(Card(tip))

        b1 = Choice(base=BLUE, fg=WHITE, text=S.TX_BTN_ETHERSCAN,
                    size_hint_y=None, height=dp(52), bold=True)
        b1.bind(on_release=lambda *_: self.open(ETHERSCAN_WRITE))
        b2 = Choice(base=BLACK, fg=WHITE, text=S.TX_BTN_DAPP,
                    size_hint_y=None, height=dp(52), bold=True)
        b2.bind(on_release=lambda *_: self.open(DAPP_URL))
        box.add_widget(b1)
        box.add_widget(b2)
        box.add_widget(Card(warn or S.TX_DEFAULT_WARN))

        sv.add_widget(box)
        col.add_widget(sv)
        self.add_widget(col)

    def copy_row(self, title, value, shown):
        row = Panel(size_hint_y=None, height=dp(68), spacing=dp(8))
        row.add_widget(label(f"[size=12sp]{escape_markup(title)}[/size]\n[b]{escape_markup(shown)}[/b]"))
        btn = Button(text=S.BTN_COPY, size_hint=(None, None), size=(dp(72), dp(40)),
                     pos_hint={"center_y": 0.5}, background_normal="",
                     background_color=BLUE, color=WHITE, bold=True)
        btn.bind(on_release=lambda *_: self.copy(title, value))
        row.add_widget(btn)
        return row

    def copy(self, title, value):
        ok = util.copy_text(value)
        self.status.text = S.TX_COPIED.format(title=title) if ok else S.TX_COPY_FAILED

    def open(self, url):
        if not util.open_url(url):
            self.status.text = S.TX_OPEN_FAILED
