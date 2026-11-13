"""Ethereum links: a grid of round tiles that open Etherscan, the dApp and GitHub."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout

import strings as S
import util
from theme import (BLACK, DAPP_URL, DSOS_ADDR, ETHERSCAN_ADDR, GITHUB_URL, LEDGER_ADDR, WHITE)
from widgets import Overlay, Panel, RoundBtn, Tile, label


def link_url(key, address):
    """URL for a tile, or '' when it cannot be built yet (no wallet address)."""
    if key == "wallet":
        a = (address or "").strip()
        return ETHERSCAN_ADDR + a if a.startswith("0x") and len(a) == 42 else ""
    return {"read": ETHERSCAN_ADDR + DSOS_ADDR + "#readContract",
            "write": ETHERSCAN_ADDR + DSOS_ADDR + "#writeContract",
            "ledger": ETHERSCAN_ADDR + LEDGER_ADDR,
            "dapp": DAPP_URL, "github": GITHUB_URL}[key]


class LinksScreen(Overlay):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        col = BoxLayout(orientation="vertical")
        head = BoxLayout(size_hint_y=None, height=dp(64), padding=[dp(14), dp(6)], spacing=dp(14))
        back = RoundBtn(text=S.ICON_BACK, font_size="26sp", bold=True, bg=WHITE, color=BLACK,
                        size_hint=(None, 1), width=dp(56))
        back.bind(on_release=lambda *_: app.close_top())
        head.add_widget(back)
        head.add_widget(label(S.LINKS_TITLE, font_size="24sp"))
        col.add_widget(head)
        self.status = label("", size_hint_y=None, height=dp(22), font_size="13sp",
                            padding=(dp(14), 0))
        col.add_widget(self.status)

        panel = Panel(orientation="vertical", size_hint_y=None, height=dp(2 * 128 + 40),
                      padding=dp(14))
        grid = GridLayout(cols=3, spacing=dp(10))
        addr = app.data["address"] if app.data else app.addr.text
        self.tiles = {}
        for key, cap, glyph, color in S.LINK_TILES:
            url = link_url(key, addr)
            t = Tile(glyph, cap, color, enabled=bool(url))
            t.bind(on_release=lambda _w, k=key, u=url: self.go(k, u))
            self.tiles[key] = t
            grid.add_widget(t)
        panel.add_widget(grid)
        wrap = BoxLayout(orientation="vertical", padding=[dp(14), dp(4)])
        wrap.add_widget(panel)
        wrap.add_widget(BoxLayout())
        col.add_widget(wrap)
        self.add_widget(col)

    def go(self, key, url):
        if not url:
            self.status.text = S.LINKS_NEED_ADDRESS
            return
        if not util.open_url(url):
            self.status.text = S.SETTINGS_OPEN_FAILED
