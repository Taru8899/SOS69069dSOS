"""THE ONE FILE FOR THE LOOK OF THE APP: colours, sizes, fonts, input-field style, welcome screen.

Edit values here and rebuild. Nothing else in the app contains a colour or a main size:
  - texts (wording)            -> strings.py
  - colours / sizes / fonts    -> this file
A colour is (red, green, blue, alpha), each 0..1.   dp = Android density-independent pixels.
This file imports nothing from the app, so every other file may import it.
"""
import os
import struct
import zlib

# ============================================================== PALETTE
GREEN = (4 / 255, 168 / 255, 53 / 255, 1)      # app background; same green as the logo
BLUE = (0, 0.2, 1, 1)                          # main accent: buttons, links, outlines
BLACK = (0.04, 0.04, 0.04, 1)                  # text and dark buttons
WHITE = (1, 1, 1, 1)
RED = (0.69, 0, 0.13, 1)                       # errors, expired
GRAY = (0.78, 0.8, 0.8, 1)                     # ring remainder, track
LIGHT = (0.94, 0.95, 0.95, 1)                  # light grey boxes
LIGHT_BLUE = (0.87, 0.9, 1, 1)
LIGHT_GREEN = (0.88, 0.94, 0.89, 1)            # success card background
PILL_BG = (0.9, 0.97, 0.92, 1)
CREAM = (1, 0.96, 0.85, 1)
BROWN = (0.45, 0.3, 0, 1)
DARK_GREEN = (0.04, 0.48, 0.17, 1)             # success card text
DARK_GREEN_HEX = "0a7a2a"                      # the same colour as hex for [color=..] markup
TRANSPARENT = (0, 0, 0, 0)

# ---- more shades used by single widgets
NOTE_GRAY = (0.8, 0.82, 0.82, 1)               # small grey note under the header / forms
HINT_GRAY = (0.45, 0.47, 0.47, 1)              # placeholder text in input fields
NAV_GRAY = (0.6, 0.62, 0.62, 1)                # inactive bottom-nav icon and label
TILE_CAP_OFF = (0.5, 0.52, 0.52, 1)            # caption of a disabled link tile
BTN_OFF_DARK = (0.35, 0.4, 0.4, 1)             # text of a disabled light button
BTN_OFF_LIGHT = (1, 1, 1, 0.8)                 # text of a disabled dark button
SELECTION = (0, 0.2, 1, 0.3)                   # selected text in an input field
WHITE_85 = (1, 1, 1, 0.85)
WHITE_70 = (1, 1, 1, 0.7)
PANEL_GRAY = (0.93, 0.94, 0.94, 1)
TRACK_GRAY = (0.9, 0.91, 0.91, 1)
RED_BG = (1, 0.9, 0.9, 1)                      # expired badge background
OK_BG = (0.88, 0.97, 0.90, 1)                  # redeemable badge background

# ---- link tiles and activity icons
ICON_GREEN = (0.02, 0.66, 0.21, 1)
ICON_ORANGE = (0.9, 0.55, 0.0, 1)
ICON_PURPLE = (0.45, 0.2, 0.85, 1)
ICON_SLATE = (0.35, 0.37, 0.4, 1)

# ============================================================== SIZES (dp unless noted)
HEADER_H = 76              # header bar height
HEADER_LINE_H = 26         # height of each of the two header text lines ("Main wallet" / address)
LOGO_W = 72                # logo column width (the logo fills it)
NAV_H = 66                 # bottom navigation bar height
RING_SIZE = 56             # the small donut on the Wallet card
BAL_CARD_H = 196           # Wallet balance card height
BAL_TOP_H = 56             # its top row (number + ring)
BAL_CHIP_H = 68            # the three small grey boxes under it
PLUS_D = 60                # diameter of the blue "+" button in the bottom bar
PLUS_OUT = 0.10            # share of the "+" button that sticks out above the bar
BAL_LINE_H = 28            # the line "≈ … ETH redeemable" + held amount
FIELD_H = 48               # input-field height
BUTTON_H = 58              # big action button
RADIUS = 16                # standard corner radius
RADIUS_PANEL = 18          # white panels

# ============================================================== FONTS (sp)
FONT_TITLE = "24sp"        # page titles (bold)
FONT_SECTION = "18sp"      # section headings inside a page (bold)
FONT_ROW = "17sp"          # title line of a list row / card (bold)
FONT_HELPER = "14sp"       # helper text: notes, sub-lines, footers, status lines (always bold, never smaller)
FONT_BIG = "18sp"          # big buttons
FONT_BODY = "17sp"         # header address, main text
FONT_SMALL = "13sp"        # notes
FONT_RING = "16sp"         # "%" in the ring
FONT_ETH_LINE = "15sp"     # "≈ 0.004 ETH redeemable"
FONT_BAL_BIG = "40sp"      # big dSOS number on the Wallet card
FONT_ECON_TITLE = "18.5sp" # Economics group titles
FONT_ECON_ROW = "16sp"     # Economics row names
FONT_ECON_ROW_BIG = "18.75sp"   # names of "Your dSOS" / "Your credits": 25% bigger
FONT_ECON_ETH = "18sp"     # ETH amounts on the Economics page
FONT_ECON_VALUE = "14sp"   # the rest of a value ("· 4 dSOS", "(pool too thin)")
ECON_ROW_MIN_H = 52        # minimum row height (grows when a text wraps)
FONT_HELD = "18.75sp"      # held-by-contract amount (bold): 25% bigger than the redeemable line

# ============================================================== INPUT FIELD LOOK
FIELD_BG = WHITE
FIELD_OUTLINE = BLUE
FIELD_OUTLINE_FOCUS = BLUE
FIELD_OUTLINE_PX = 2           # outline thickness in the generated picture (pixels)
FIELD_OUTLINE_FOCUS_PX = 3
FIELD_RADIUS_PX = 18           # corner radius in the generated picture (pixels)
FIELD_PNG_SIZE = 96            # generated picture size (pixels); stretched with border=24

# ============================================================== WELCOME SCREEN
SPLASH_SECONDS = 1.8
WELCOME_MIN = 3.0              # seconds the welcome screen stays at least (saved wallet)
WELCOME_NO_WALLET = 3.0        # no saved wallet: nothing to wait for
WELCOME_MAX = 8.0              # ... and at most
WELCOME_SPINNER = (RED, BLUE, BLACK)   # the three turning arcs
SPLASH_COLOR_HEX = "04A835"    # Android splash background (CI copies it into buildozer.spec)


# ============================================================== field pictures (pure Python PNG)
def _png(width, height, rows):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def field_png(bg, outline, outline_px, radius_px, size=FIELD_PNG_SIZE):
    """A rounded rectangle `bg` with an `outline` ring, anti-aliased, as PNG bytes (RGBA)."""
    s, r, half = size, float(radius_px), size / 2.0
    q8 = lambda v: int(round(max(0.0, min(1.0, v)) * 255))   # noqa: E731
    bgc, olc = [q8(v) for v in bg], [q8(v) for v in outline]
    rows = []
    for y in range(s):
        row = []
        for x in range(s):
            qx = abs(x + 0.5 - half) - (half - r)
            qy = abs(y + 0.5 - half) - (half - r)
            dist = (max(qx, 0) ** 2 + max(qy, 0) ** 2) ** 0.5 + min(max(qx, qy), 0) - r
            depth = -dist                                        # > 0 inside the shape
            cover = max(0.0, min(1.0, depth + 0.5))              # anti-aliased outer edge
            t = max(0.0, min(1.0, depth - outline_px + 0.5))     # 0 = outline colour, 1 = fill
            row += [int(round(olc[i] * (1 - t) + bgc[i] * t)) for i in range(3)]
            row.append(int(round(cover * (olc[3] * (1 - t) + bgc[3] * t))))
        rows.append(row)
    return _png(s, s, rows)


def ensure_fields(folder):
    """Write field.png / field_focus.png into `folder` from the colours above. Returns the two
    paths, or None when generation is impossible (the shipped pictures stay as the fallback)."""
    try:
        a, b = os.path.join(folder, "field.png"), os.path.join(folder, "field_focus.png")
        with open(a, "wb") as f:
            f.write(field_png(FIELD_BG, FIELD_OUTLINE, FIELD_OUTLINE_PX, FIELD_RADIUS_PX))
        with open(b, "wb") as f:
            f.write(field_png(FIELD_BG, FIELD_OUTLINE_FOCUS, FIELD_OUTLINE_FOCUS_PX, FIELD_RADIUS_PX))
        return a, b
    except Exception:  # noqa: BLE001
        return None
