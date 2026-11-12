"""Colors, constants and small helpers shared by all pages."""
import os

import core
import strings as S

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "logo.png")
HAS_LOGO = os.path.exists(LOGO)

GREEN = (4 / 255, 168 / 255, 53 / 255, 1)   # same green as the logo background
BLUE = (0, 0.2, 1, 1)
BLACK = (0.04, 0.04, 0.04, 1)
WHITE = (1, 1, 1, 1)
RED = (0.69, 0, 0.13, 1)
GRAY = (0.78, 0.8, 0.8, 1)
LIGHT = (0.94, 0.95, 0.95, 1)
LIGHT_BLUE = (0.87, 0.9, 1, 1)
LIGHT_GREEN = (0.88, 0.94, 0.89, 1)
PILL_BG = (0.9, 0.97, 0.92, 1)
CREAM = (1, 0.96, 0.85, 1)
BROWN = (0.45, 0.3, 0, 1)
DARK_GREEN = (0.04, 0.48, 0.17, 1)
DARK_GREEN_HEX = "0a7a2a"

SPLASH_SECONDS = 1.8
DSOS_ADDR = "0x7Bd7c427b3c69e2a09603573ac875987c61ECAB8"
ETHERSCAN_WRITE = "https://etherscan.io/address/" + DSOS_ADDR + "#writeContract"
DAPP_URL = "https://taru8899.github.io/SOS69069dSOS/dsos-dapp-v29.html"
WINDOWS = {"1 day": 7200, "2 days": 14400, "7 days": 50400}


def short(addr):
    a = (addr or "").strip()
    return f"{a[:6]}...{a[-4:]}" if len(a) > 12 else a


def left_text(left):
    return S.EXPIRED if left <= 0 else S.LEFT.format(time=core.dur(left))


def set_visible(w, show):
    """Show/hide a widget without removing it (keeps text fields stable)."""
    if not hasattr(w, "_h"):
        w._h = w.height
    w.height = w._h if show else 0
    w.opacity = 1 if show else 0
    w.disabled = not show
