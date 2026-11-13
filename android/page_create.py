"""Create offer page: builds the transaction data, sends nothing."""
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

import core
import strings as S
import tx
import util
from page_tx import TxScreen
from theme import BLACK, BLUE, LIGHT, WHITE, WINDOWS, short, set_visible
from widgets import (Choice, DashedBox, Overlay, Panel, RoundBtn, TypeCard, label,
                     make_input)


class CreateScreen(Overlay):
    """Create offer page. Builds the transaction data; it does not send anything."""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.kind = "B"
        self.slices = 5
        self.window = "2 days"
        self.holder_mode = "me"

        col = BoxLayout(orientation="vertical")

        # header
        head = BoxLayout(size_hint_y=None, height=dp(72), padding=[dp(14), dp(10)], spacing=dp(14))
        back = RoundBtn(text=S.ICON_BACK, font_size="26sp", bold=True, bg=WHITE, color=BLACK,
                        size_hint=(None, 1), width=dp(56))
        back.bind(on_release=lambda *_: app.close_top())
        head.add_widget(back)
        head.add_widget(label(S.CREATE_TITLE, font_size="24sp"))
        col.add_widget(head)

        # scrolling form
        sv = ScrollView()
        form = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None,
                         padding=[dp(14), 0, dp(14), dp(14)])
        form.bind(minimum_height=form.setter("height"))

        form.add_widget(label(S.CREATE_TYPE, size_hint_y=None, height=dp(26)))
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(2 * 64 + 10))
        self.type_cards = {}
        for code, title, sub, hx in S.CREATE_TYPES:
            c = TypeCard(code, title, sub, hx)
            c.bind(on_release=lambda _w, k=code: self.pick_kind(k))
            self.type_cards[code] = c
            grid.add_widget(c)
        form.add_widget(grid)

        # slices
        sl = Panel(orientation="vertical", size_hint_y=None, height=dp(196), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(24))
        top.add_widget(label(S.CREATE_SLICES))
        top.add_widget(label(S.CREATE_EACH, halign="right"))
        sl.add_widget(top)
        mid = BoxLayout(size_hint_y=None, height=dp(84))
        minus = RoundBtn(text=S.ICON_MINUS, font_size="34sp", bg=BLACK, color=WHITE,
                         size_hint=(None, 1), width=dp(72))
        minus.bind(on_release=lambda *_: self.set_slices(self.slices - 1))
        plus = RoundBtn(text=S.ICON_PLUS, font_size="30sp", bg=BLACK, color=WHITE,
                        size_hint=(None, 1), width=dp(72))
        plus.bind(on_release=lambda *_: self.set_slices(self.slices + 1))
        self.num = Label(text="", markup=True, color=BLACK, halign="center", valign="middle")
        self.num.bind(size=lambda i, s: setattr(i, "text_size", s))
        mid.add_widget(minus)
        mid.add_widget(self.num)
        mid.add_widget(plus)
        sl.add_widget(mid)
        chips = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.slice_chips = {}
        for n in (1, 5, 10, 50):
            ch = Choice(base=LIGHT, text=str(n))
            ch.bind(on_release=lambda _w, v=n: self.set_slices(v))
            self.slice_chips[n] = ch
            chips.add_widget(ch)
        sl.add_widget(chips)
        form.add_widget(sl)

        # redeem window
        form.add_widget(label(S.CREATE_WINDOW, size_hint_y=None, height=dp(26)))
        wrow = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        self.win_chips = {}
        for key in (*WINDOWS, S.WINDOW_CUSTOM):
            ch = Choice(text=key)
            ch.bind(on_release=lambda _w, k=key: self.pick_window(k))
            self.win_chips[key] = ch
            wrow.add_widget(ch)
        form.add_widget(wrow)
        self.custom_in = make_input(S.HINT_CUSTOM_BLOCKS, filt="int")
        form.add_widget(self.custom_in)
        self.custom_in.bind(text=lambda *_: self.refresh())
        self.win_note = label("", size_hint_y=None, height=dp(60), valign="top", font_size="13sp")
        form.add_widget(self.win_note)

        # PIN (gated offers only)
        self.pin_in = make_input(S.CREATE_PIN_HINT, password=True)
        self.pin_in.bind(text=lambda *_: self.refresh())
        form.add_widget(self.pin_in)
        self.pin_note = label(S.CREATE_PIN_NOTE, size_hint_y=None, height=dp(96), valign="top",
                              font_size="13sp")
        form.add_widget(self.pin_note)

        # holder
        form.add_widget(label(S.CREATE_HOLDER, size_hint_y=None, height=dp(26)))
        hold = Panel(orientation="vertical", size_hint_y=None, height=dp(150), spacing=dp(6))
        self.holder_btn = Button(text="", markup=True, halign="left", valign="middle",
                                 background_normal="", background_down="",
                                 background_color=(0, 0, 0, 0), color=BLACK,
                                 size_hint_y=None, height=dp(52))
        self.holder_btn.bind(size=lambda i, s: setattr(i, "text_size", (s[0], s[1])))
        self.holder_btn.bind(on_release=lambda *_: self.toggle_holder())
        hold.add_widget(self.holder_btn)
        self.other_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.other_in = make_input(S.HINT_HOLDER)
        self.other_in.bind(text=lambda *_: self.refresh())
        pb = Button(text=S.BTN_PASTE, size_hint=(None, 1), width=dp(72), background_normal="",
                    background_color=BLUE, color=WHITE, bold=True)
        pb.bind(on_release=lambda *_: self.paste_other())
        self.other_row.add_widget(self.other_in)
        self.other_row.add_widget(pb)
        hold.add_widget(self.other_row)
        self.hold_panel = hold
        form.add_widget(hold)

        # ledger
        dash = DashedBox(size_hint_y=None, height=dp(56), padding=[dp(16), 0])
        dash.add_widget(label(S.CREATE_LEDGER))
        dash.add_widget(label(S.CREATE_LEDGER_SKIPPED, halign="right", size_hint_x=None, width=dp(70)))
        form.add_widget(dash)

        sv.add_widget(form)
        col.add_widget(sv)

        # footer
        foot = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(124),
                         padding=[dp(14), dp(12)], spacing=dp(8))
        with foot.canvas.before:
            Color(*BLACK)
            fbg = Rectangle()
        foot.bind(pos=lambda i, p: setattr(fbg, "pos", p),
                  size=lambda i, s: setattr(fbg, "size", s))
        self.btn = Choice(base=BLUE, sel=BLUE, fg=WHITE, sel_fg=WHITE, bold=True,
                          font_size="18sp", size_hint_y=None, height=dp(58))
        self.btn.bind(on_release=lambda *_: self.on_create())
        foot.add_widget(self.btn)
        self.note = Label(text="", color=(0.8, 0.82, 0.82, 1), font_size="13sp",
                          halign="center", valign="middle")
        self.note.bind(size=lambda i, s: setattr(i, "text_size", s))
        foot.add_widget(self.note)
        col.add_widget(foot)

        self.add_widget(col)
        self.refresh()

    # ---- state
    def pick_kind(self, k):
        self.kind = k
        self.refresh()

    def set_slices(self, n):
        self.slices = max(1, min(100000, n))
        self.refresh()

    def pick_window(self, k):
        self.window = k
        self.refresh()

    def toggle_holder(self):
        self.holder_mode = "other" if self.holder_mode == "me" else "me"
        self.refresh()

    def paste_other(self):
        t = util.paste_text()
        if t:
            self.other_in.text = t
        else:
            self.note.text = S.MSG_CLIPBOARD_EMPTY_DOT

    def blocks(self):
        if self.window == S.WINDOW_CUSTOM:
            t = self.custom_in.text.strip()
            return int(t) if t.isdigit() else 0
        return WINDOWS[self.window]

    def holder_addr(self):
        if self.holder_mode == "me":
            return self.app.addr.text.strip()
        return self.other_in.text.strip()

    def problem(self):
        if self.blocks() < 1:
            return S.CREATE_ERR_WINDOW
        if not tx.valid_address(self.holder_addr()):
            if self.holder_mode == "me":
                return S.CREATE_ERR_OWN_ADDR
            return S.CREATE_ERR_HOLDER
        if self.kind == "G":
            if not tx.valid_address(self.app.addr.text.strip()):
                return S.CREATE_ERR_OWN_ADDR
            if not self.pin_in.text.strip():
                return S.CREATE_ERR_PIN
        return ""

    def refresh(self):
        eth = core.eth(self.slices * core.UNIT)
        self.num.text = S.CREATE_SLICES_VALUE.format(n=self.slices, eth=eth)
        for code, c in self.type_cards.items():
            c.set_selected(code == self.kind)
        for n, c in self.slice_chips.items():
            c.set_selected(n == self.slices)
        for k, c in self.win_chips.items():
            c.set_selected(k == self.window)
        set_visible(self.custom_in, self.window == S.WINDOW_CUSTOM)

        b = self.blocks()
        data = self.app.data
        gated = self.kind == "G"
        note = S.WIN_NOTE.format(
            blocks=b,
            expires=S.WIN_EXPIRES.format(block=data["block"] + b) if data else "",
            rule=(S.WIN_RULE_GATED if gated else
                  S.WIN_RULE_OK if b > core.WINDOW else S.WIN_RULE_SHORT))
        gate_risk = (gated and b == 1 and data is not None
                     and self.slices * core.UNIT >= data["stake_need_wei"])
        if gate_risk:
            note += "\n" + S.CREATE_GATE_WARN.format(eth=core.eth(data["stake_need_wei"]))
        self.win_note.text = note
        self.win_note.height = dp(150 if gate_risk else 60)
        set_visible(self.pin_in, gated)
        set_visible(self.pin_note, gated)

        me = self.holder_mode == "me"
        mine = self.app.addr.text.strip()
        self.holder_btn.text = (S.HOLDER_ME.format(addr=short(mine) or S.HOLDER_ME_EMPTY)
                                if me else S.HOLDER_OTHER)
        set_visible(self.other_row, not me)
        self.hold_panel.height = dp(84) if me else dp(150)

        p = self.problem()
        self.btn.text = S.CREATE_BUTTON.format(eth=eth)
        self.btn.set_enabled(not p)
        self.note.text = p or S.CREATE_NOTE

    def on_create(self):
        if self.problem():
            return
        if self.kind == "G":
            self.on_create_gated()
            return
        try:
            t = tx.create_offer_tx(self.kind, self.holder_addr(), self.slices, self.blocks())
        except Exception as e:  # noqa: BLE001
            self.note.text = str(e)
            return
        summary = S.CREATE_SUMMARY.format(kind=self.kind, slices=self.slices, eth=t["value_eth"],
                                          blocks=self.blocks(), holder=short(self.holder_addr()))
        p = t["params"]
        R = S.CREATE_ROWS
        rows = [(R["payable"], t["value_eth"], t["value_eth"]),
                (R["kind"], p["kind"], p["kind"]),
                (R["to"], p["to"], short(p["to"])),
                (R["delay"], p["delayBlocks"], p["delayBlocks"]),
                (R["hash"], p["payloadHash"], short(p["payloadHash"])),
                (R["sig"], "0x", "0x")]
        self.app.safe_overlay(lambda: TxScreen(self.app, t, summary, S.CREATE_FN, rows, S.CREATE_TIP))

    def on_create_gated(self):
        donor = self.app.addr.text.strip()
        try:
            t = tx.create_gated_tx(donor, self.holder_addr(), self.slices, self.blocks(),
                                   self.pin_in.text)
        except Exception as e:  # noqa: BLE001
            self.note.text = str(e)
            return
        summary = S.CREATE_GATED_SUMMARY.format(
            slices=self.slices, eth=t["value_eth"], blocks=self.blocks(),
            holder=short(self.holder_addr()))
        p = t["params"]
        R = S.CREATE_GATED_ROWS
        rows = [(R["payable"], t["value_eth"], t["value_eth"]),
                (R["to"], p["to"], short(p["to"])),
                (R["delay"], p["delayBlocks"], p["delayBlocks"]),
                (R["pin"], p["pinCommitment_"], short(p["pinCommitment_"])),
                (R["hash"], p["payloadHash"], short(p["payloadHash"])),
                (R["sig"], "0x", "0x")]
        self.app.safe_overlay(lambda: TxScreen(self.app, t, summary, S.CREATE_GATED_FN, rows,
                                       S.CREATE_GATED_TIP))
