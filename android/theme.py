"""Constants and small helpers shared by all pages. Colours, sizes and fonts live in design.py
(re-exported here, so `from theme import BLUE` keeps working)."""
import os
import tempfile

import core
import design
from design import *  # noqa: F401,F403  (colours, sizes, fonts: edit them in design.py)
import strings as S

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "logo.png")
HAS_LOGO = os.path.exists(LOGO)
FIELD = os.path.join(HERE, "field.png")              # shipped pictures = fallback
FIELD_FOCUS = os.path.join(HERE, "field_focus.png")
for _folder in (HERE, tempfile.gettempdir()):        # the pictures are drawn from design.py colours
    _gen = design.ensure_fields(_folder)
    if _gen:
        FIELD, FIELD_FOCUS = _gen
        break
HAS_FIELD = os.path.exists(FIELD) and os.path.exists(FIELD_FOCUS)
START = os.path.join(HERE, "start.jpg")            # big start image (flat green + logo)
HAS_START = os.path.exists(START)
WORDMARK = os.path.join(HERE, "wordmark.png")
HAS_WORDMARK = os.path.exists(WORDMARK)

APP_VERSION = "v9.7"
try:                                   # build_info.py is written by the CI workflow
    import build_info
    if build_info.NUMBER == "dev":
        raise ImportError("not built by CI")
    BUILD = f"{APP_VERSION} \u00b7 build {build_info.NUMBER} \u00b7 {build_info.SHA}"
except Exception:  # noqa: BLE001
    BUILD = f"{APP_VERSION} \u00b7 dev build"

DSOS_ADDR = "0x7Bd7c427b3c69e2a09603573ac875987c61ECAB8"
LEDGER_ADDR = "0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A"
ETHERSCAN_ADDR = "https://etherscan.io/address/"
GITHUB_URL = "https://github.com/Taru8899/SOS69069dSOS"
ETHERSCAN_WRITE = "https://etherscan.io/address/" + DSOS_ADDR + "#writeContract"
DAPP_URL = "https://taru8899.github.io/SOS69069dSOS/dsos-dapp-v29.html"
ETHERSCAN_TX = "https://etherscan.io/tx/"
WINDOWS = {"1 day": 7200, "2 days": 14400, "7 days": 50400}

# WalletConnect (the wallet link). The project id is public: it only names this app to the relay.
WC_PROJECT_ID = "fc829de5747f7a577fcee0c2ddbad0f8"
WC_ORIGIN = "https://taru8899.github.io"                  # page origin shown to the relay / wallet
WC_APP_URL = "https://taru8899.github.io/SOS69069dSOS/"
WC_RPC = "https://ethereum-rpc.publicnode.com"


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
