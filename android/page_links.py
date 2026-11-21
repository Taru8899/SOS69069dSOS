"""Ethereum links: a grid of round tiles that open Etherscan, the dApp and GitHub."""
from kivy.metrics import dp
from kivy.uix.gridlayout import GridLayout

import strings as S
import util
from theme import DAPP_URL, DSOS_ADDR, ETHERSCAN_ADDR, GITHUB_URL, LEDGER_ADDR
from widgets import Panel, Tile


def link_url(key, address):
    """URL for a tile, or '' when it cannot be built yet (no wallet address)."""
    if key == "wallet":
        a = (address or "").strip()
        return ETHERSCAN_ADDR + a if a.startswith("0x") and len(a) == 42 else ""
    return {"read": ETHERSCAN_ADDR + DSOS_ADDR + "#readContract",
            "write": ETHERSCAN_ADDR + DSOS_ADDR + "#writeContract",
            "ledger": ETHERSCAN_ADDR + LEDGER_ADDR,
            "dapp": DAPP_URL, "github": GITHUB_URL}[key]


def build_grid(app, on_status):
    """The round link tiles as one white panel (placed at the top of the Ethereum page)."""
    panel = Panel(orientation="vertical", size_hint_y=None, height=dp(2 * 128 + 40), padding=dp(14))
    grid = GridLayout(cols=3, spacing=dp(10))
    addr = app.data["address"] if app.data else app.addr.text

    def go(key, url):
        if not url:
            on_status(S.LINKS_NEED_ADDRESS)
        elif not util.open_url(url):
            on_status(S.SETTINGS_OPEN_FAILED)

    for key, cap, glyph, color in S.LINK_TILES:
        url = link_url(key, addr)
        t = Tile(glyph, cap, color, enabled=bool(url))
        t.bind(on_release=lambda _w, k=key, u=url: go(k, u))
        grid.add_widget(t)
    panel.add_widget(grid)
    return panel
