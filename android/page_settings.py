"""Settings page: the two contract addresses and the app version / build."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.utils import escape_markup

import strings as S
import util
from theme import BLACK, BLUE, BUILD, DSOS_ADDR, ETHERSCAN_ADDR, LEDGER_ADDR, WHITE, short
from widgets import Card, Overlay, Panel, PullScroll, RoundBtn, label


class SettingsScreen(Overlay):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        col = BoxLayout(orientation="vertical")
        head = BoxLayout(size_hint_y=None, height=dp(64), padding=[dp(14), dp(6)], spacing=dp(14))
        back = RoundBtn(text=S.ICON_BACK, font_size="26sp", bold=True, bg=WHITE, color=BLACK,
                        size_hint=(None, 1), width=dp(56))
        back.bind(on_release=lambda *_: app.close_top())
        head.add_widget(back)
        head.add_widget(label(S.SETTINGS_TITLE, font_size="24sp"))
        col.add_widget(head)
        self.status = label("", size_hint_y=None, height=dp(22), font_size="13sp",
                            padding=(dp(14), 0))
        col.add_widget(self.status)

        sv = PullScroll()
        box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None,
                        padding=[dp(14), 0, dp(14), dp(20)])
        box.bind(minimum_height=box.setter("height"))
        box.add_widget(Card(S.SETTINGS_INTRO))
        box.add_widget(self.address_row(S.SETTINGS_DSOS, DSOS_ADDR))
        box.add_widget(self.address_row(S.SETTINGS_LEDGER, LEDGER_ADDR))
        box.add_widget(Card(S.SETTINGS_VERSION.format(build=escape_markup(BUILD))))
        box.add_widget(self.layout_row())
        sv.add_widget(box)
        col.add_widget(sv)
        self.add_widget(col)

    def address_row(self, title, addr):
        p = Panel(orientation="vertical", size_hint_y=None, height=dp(124), spacing=dp(6))
        p.add_widget(label(f"[b]{title}[/b]\n[size=12sp]{short(addr)}[/size]",
                           size_hint_y=None, height=dp(44)))
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        for text, fn in ((S.BTN_COPY, lambda: self.copy(title, addr)),
                         (S.BTN_OPEN, lambda: self.open(ETHERSCAN_ADDR + addr))):
            b = Button(text=text, background_normal="", background_down="",
                       background_color=BLUE, color=WHITE, bold=True)
            b.bind(on_release=lambda *_, f=fn: f())
            btns.add_widget(b)
        p.add_widget(btns)
        return p

    def layout_row(self):
        p = Panel(orientation="vertical", size_hint_y=None, height=dp(112), spacing=dp(6))
        p.add_widget(label(S.SETTINGS_LAYOUT, size_hint_y=None, height=dp(44), font_size="13sp"))
        b = Button(text=S.SETTINGS_LAYOUT_COPY, size_hint_y=None, height=dp(44),
                   background_normal="", background_down="", background_color=BLUE,
                   color=WHITE, bold=True)
        b.bind(on_release=lambda *_: self.copy(S.SETTINGS_LAYOUT_COPY, self.app.layout_report()))
        p.add_widget(b)
        return p

    def copy(self, title, value):
        ok = util.copy_text(value)
        self.status.text = S.SETTINGS_COPIED.format(title=title) if ok else S.TX_COPY_FAILED

    def open(self, url):
        if not util.open_url(url):
            self.status.text = S.SETTINGS_OPEN_FAILED
