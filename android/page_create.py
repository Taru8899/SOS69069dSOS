"""Create offer page: builds the transaction data, sends nothing."""
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

import threading

from kivy.clock import Clock

import core
import strings as S
import tx
import util
from page_tx import TxScreen
from design import NOTE_GRAY
from theme import BLACK, BLUE, DSOS_ADDR, LIGHT, RED, WHITE, WINDOWS, short, set_visible
from widgets import (Icon, IconRow, Card, Choice, DashedBox, Overlay, Panel, PullScroll, IconBtn, TypeCard,
                     label, make_input, page_head, text_label)


class CreateScreen(Overlay):
    """Create offer page. Builds the transaction data; it does not send anything."""

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.kind = "S"
        self.slices = 5
        self.window = "2 days"
        self.holder_mode = "me"

        col = BoxLayout(orientation="vertical")

        col.add_widget(page_head(app, S.CREATE_TITLE))

        # scrolling form
        sv = PullScroll(on_pull=lambda: None)      # no reload on this page
        self.sv = sv
        form = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None,
                         padding=[dp(14), 0, dp(14), dp(14)])
        form.bind(minimum_height=form.setter("height"))
        self.form = form
        self._order = []          # every block of the form, in order; hidden ones are taken out

        def add(w, group=False):
            """group=True: a 6dp extra gap above this block (12dp between groups)."""
            if group:
                gap = Widget(size_hint_y=None, height=dp(6))
                gap._for = w
                self._order.append(gap)
            w._on = True
            self._order.append(w)

        # red error card (empty and 0 high until there is something to say)
        self.err_box = BoxLayout(orientation="vertical", size_hint_y=None, height=0)
        add(self.err_box)
        self.err_box._on = False

        add(label(S.CREATE_TYPE, size_hint_y=None, height=dp(24)), True)
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(2 * 64 + 10))
        self.type_cards = {}
        for code, title, sub, hx in S.CREATE_TYPES:
            c = TypeCard(code, title, sub, hx)
            c.bind(on_release=lambda _w, k=code: self.pick_kind(k))
            self.type_cards[code] = c
            grid.add_widget(c)
        add(grid)

        # slices
        sl = Panel(orientation="vertical", size_hint_y=None, height=dp(196), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(24))
        top.add_widget(label(S.CREATE_SLICES))
        top.add_widget(label(S.CREATE_EACH, halign="right"))
        sl.add_widget(top)
        mid = BoxLayout(size_hint_y=None, height=dp(84))
        minus = IconBtn(icon="minus", bg=BLACK, color=WHITE,
                         size_hint=(None, 1), width=dp(72))
        minus.bind(on_release=lambda *_: self.set_slices(self.slices - 1))
        plus = IconBtn(icon="plus", bg=BLACK, color=WHITE,
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
        add(sl, True)

        # slices paid per SOS record (A and B offers only)
        self.per_title = label(S.CREATE_PER_RECORD, size_hint_y=None, height=dp(24))
        add(self.per_title, True)
        self.per_in = make_input(S.HINT_PER_RECORD, "1", filt="int")
        self.per_in.bind(text=lambda *_: self.refresh())
        add(self.per_in)
        self.per_note = text_label("", font_size="13sp")
        add(self.per_note)

        # redeem window
        add(label(S.CREATE_WINDOW, size_hint_y=None, height=dp(24)), True)
        wrow = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        self.win_chips = {}
        for key in (*WINDOWS, S.WINDOW_CUSTOM):
            ch = Choice(text=key)
            ch.bind(on_release=lambda _w, k=key: self.pick_window(k))
            self.win_chips[key] = ch
            wrow.add_widget(ch)
        add(wrow)
        self.custom_in = make_input(S.HINT_CUSTOM_BLOCKS, filt="int")
        add(self.custom_in)
        self.custom_in.bind(text=lambda *_: self.refresh())
        self.win_note = text_label("", font_size="13sp")
        add(self.win_note)

        # PIN (gated offers only)
        self.pin_in = make_input(S.CREATE_PIN_HINT, password=True)
        self.pin_in.bind(text=lambda *_: self.refresh())
        self.pin_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.pin_row.add_widget(self.pin_in)
        self.pin_eye = Choice(base=BLUE, fg=WHITE, text=S.PIN_SHOW, bold=True,
                              size_hint=(None, 1), width=dp(72))
        self.pin_eye.bind(on_release=lambda *_: self.toggle_pin())
        self.pin_row.add_widget(self.pin_eye)
        add(self.pin_row, True)
        self.pin_note = text_label(S.CREATE_PIN_NOTE, font_size="13sp")
        add(self.pin_note)

        # holder
        self.holder_title = label(S.CREATE_HOLDER, size_hint_y=None, height=dp(24))
        add(self.holder_title, True)
        hold = Panel(orientation="vertical", size_hint_y=None, height=dp(150), spacing=dp(6))
        self.holder_btn = IconRow("user", size_hint_y=None, height=dp(56))
        self.holder_btn.bind(on_release=lambda *_: self.toggle_holder())
        hold.add_widget(self.holder_btn)
        self.other_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.other_in = make_input(S.HINT_HOLDER)
        self.other_in.bind(text=lambda *_: self.refresh())
        pb = Choice(base=BLUE, fg=WHITE, text=S.BTN_PASTE, bold=True, size_hint=(None, 1),
                    width=dp(72))
        pb.bind(on_release=lambda *_: self.paste_other())
        self.other_row.add_widget(self.other_in)
        self.other_row.add_widget(pb)
        hold.add_widget(self.other_row)
        self.hold_panel = hold
        add(hold)

        # ledger
        dash = DashedBox(size_hint_y=None, height=dp(56), padding=[dp(16), 0])
        dash.add_widget(Icon("list", color=BLACK, size=(dp(24), dp(24)), pos_hint={"center_y": 0.5}))
        dash.add_widget(label(S.CREATE_LEDGER))
        dash.add_widget(label(S.CREATE_LEDGER_SKIPPED, halign="right", size_hint_x=None, width=dp(70)))
        add(dash, True)

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
        self.note = Label(text="", color=NOTE_GRAY, font_size="13sp",
                          halign="center", valign="middle")
        self.note.bind(size=lambda i, s: setattr(i, "text_size", s))
        foot.add_widget(self.note)
        col.add_widget(foot)

        self.add_widget(col)
        self.refresh()

    # ---- layout: hidden blocks are removed, so they leave no gap behind
    def _on(self, w, show):
        w._on = bool(show)

    def _layout(self):
        want = []
        for w in self._order:
            target = getattr(w, "_for", w)
            if target._on:
                want.append(w)
        if list(reversed(self.form.children)) != want:
            self.form.clear_widgets()
            for w in want:
                self.form.add_widget(w)

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

    def per(self):
        t = self.per_in.text.strip()
        return int(t) if t.isdigit() else 0

    def per_ok(self):
        p = self.per()
        return p >= 1 and p <= self.slices and self.slices % p == 0

    def holder_addr(self):
        if self.holder_mode == "me":
            return self.app.addr.text.strip()
        return self.other_in.text.strip()

    def problem(self):
        if self.blocks() < 1:
            return S.CREATE_ERR_WINDOW
        if self.kind in ("A", "B") and not self.per_ok():
            return S.CREATE_ERR_PER
        if self.kind != "A" and not tx.valid_address(self.holder_addr()):
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
        self._on(self.custom_in, self.window == S.WINDOW_CUSTOM)

        b = self.blocks()
        data = self.app.data
        gated = self.kind == "G"
        sale = self.kind in ("A", "B")
        note = S.WIN_NOTE.format(
            blocks=b,
            expires=S.WIN_EXPIRES.format(block=data["block"] + b) if data else "",
            rule=(S.WIN_RULE_GATED if gated else
                  S.WIN_RULE_AB if sale else
                  S.WIN_RULE_OK if b > core.WINDOW else S.WIN_RULE_SHORT))
        note += "\n" + S.CREATE_DELAY_NOTE
        gate_risk = (gated and b == 1 and data is not None
                     and self.slices * core.UNIT >= data["stake_need_wei"])
        if gate_risk:
            note += "\n" + S.CREATE_GATE_WARN.format(eth=core.eth(data["stake_need_wei"]))
        self.win_note.text = note
        self._on(self.per_title, sale)
        self._on(self.per_in, sale)
        p_ = self.per()
        self.per_note.text = ((S.CREATE_PER_NOTE.format(slices=self.slices, per=p_, records=self.slices // p_)
                               if self.per_ok() else S.CREATE_PER_BAD) + "\n" + S.CREATE_AB_NOTE) if sale else ""
        self._on(self.per_note, sale)
        self._on(self.pin_row, gated)
        self._on(self.pin_note, gated)

        me = self.holder_mode == "me"
        mine = self.app.addr.text.strip()
        has_holder = self.kind != "A"                  # A is open: the contract itself is the receiver
        self.holder_title.text = S.HOLDER_SELLER if self.kind == "B" else S.CREATE_HOLDER
        self._on(self.holder_title, has_holder)
        self.holder_btn.text = (S.HOLDER_ME.format(addr=short(mine) or S.HOLDER_ME_EMPTY)
                                if me else S.HOLDER_OTHER)
        set_visible(self.other_row, not me)
        self.hold_panel.height = dp(84) if me else dp(150)
        self._on(self.hold_panel, has_holder)
        self._layout()

        p = self.problem()
        self.btn.text = S.CREATE_BUTTON.format(eth=eth)
        self.btn.set_enabled(True)      # stays tappable: a tap shows the reason in red
        self.note.text = p or S.CREATE_NOTE

    def toggle_pin(self):
        self.pin_in.password = not self.pin_in.password
        self.pin_eye.text = S.PIN_SHOW if self.pin_in.password else S.PIN_HIDE

    def show_error(self, text):
        """Red card at the top of the form, scrolled into view. '' clears it."""
        self.err_box.clear_widgets()
        self._on(self.err_box, bool(text))
        self._layout()
        if not text:
            self.err_box.height = 0
            return
        c = Card(S.CREATE_ERR_TEXT.format(text=text), bg=RED, fg=WHITE)
        self.err_box.add_widget(c)
        self.err_box.height = dp(80)
        c.bind(height=lambda i, h: setattr(self.err_box, "height", h))
        self.note.text = text
        Clock.schedule_once(lambda dt: setattr(self.sv, "scroll_y", 1), 0)

    def on_create(self):
        self.show_error("")
        p = self.problem()
        if p:
            self.show_error(p)
            return
        data_ = self.app.data
        if not data_:
            self.show_error(S.ERR_NONCE)
            return
        nonce = data_["redeem_nonce"]
        try:
            if self.kind == "G":
                donor = self.app.addr.text.strip()
                t = tx.create_gated_tx(donor, self.holder_addr(), self.slices, self.blocks(),
                                       self.pin_in.text, nonce=nonce)
                summary = S.CREATE_GATED_SUMMARY.format(
                    slices=self.slices, eth=t["value_eth"], blocks=self.blocks(),
                    holder=short(self.holder_addr()))
                pp, R = t["params"], S.CREATE_GATED_ROWS
                rows = [(R["payable"], t["value_eth"], t["value_eth"]),
                        (R["to"], pp["to"], short(pp["to"])),
                        (R["delay"], pp["delayBlocks"], pp["delayBlocks"]),
                        (R["pin"], pp["pinCommitment_"], short(pp["pinCommitment_"])),
                        (R["nonce"], pp["expectedNonce"], pp["expectedNonce"])]
                shown = (summary, S.CREATE_GATED_FN, rows, S.CREATE_GATED_TIP)
            elif self.kind == "A":
                per = self.per()
                t = tx.create_a_tx(self.slices, per, self.blocks(), nonce)
                summary = S.CREATE_A_SUMMARY.format(
                    slices=self.slices, eth=t["value_eth"], per=per, records=self.slices // per,
                    blocks=self.blocks())
                pp, R = t["params"], S.CREATE_A_ROWS
                rows = [(R["payable"], t["value_eth"], t["value_eth"]),
                        (R["delay"], pp["delayBlocks"], pp["delayBlocks"]),
                        (R["per"], pp["slicesPerRecord"], pp["slicesPerRecord"]),
                        (R["nonce"], pp["expectedNonce"], pp["expectedNonce"])]
                shown = (summary, S.CREATE_A_FN, rows, S.CREATE_A_TIP)
            elif self.kind == "B":
                per = self.per()
                t = tx.create_b_tx(self.holder_addr(), self.slices, per, self.blocks(), nonce)
                summary = S.CREATE_B_SUMMARY.format(
                    slices=self.slices, eth=t["value_eth"], per=per, records=self.slices // per,
                    seller=short(self.holder_addr()), blocks=self.blocks())
                pp, R = t["params"], S.CREATE_B_ROWS
                rows = [(R["payable"], t["value_eth"], t["value_eth"]),
                        (R["to"], pp["to"], short(pp["to"])),
                        (R["delay"], pp["delayBlocks"], pp["delayBlocks"]),
                        (R["per"], pp["slicesPerRecord"], pp["slicesPerRecord"]),
                        (R["nonce"], pp["expectedNonce"], pp["expectedNonce"])]
                shown = (summary, S.CREATE_B_FN, rows, S.CREATE_B_TIP)
            else:
                t = tx.create_offer_tx(self.kind, self.holder_addr(), self.slices, self.blocks(), nonce=nonce)
                summary = S.CREATE_SUMMARY.format(
                    kind=self.kind, slices=self.slices, eth=t["value_eth"],
                    blocks=self.blocks(), holder=short(self.holder_addr()))
                pp, R = t["params"], S.CREATE_ROWS
                rows = [(R["payable"], t["value_eth"], t["value_eth"]),
                        (R["to"], pp["to"], short(pp["to"])),
                        (R["delay"], pp["delayBlocks"], pp["delayBlocks"]),
                        (R["nonce"], pp["expectedNonce"], pp["expectedNonce"])]
                shown = (summary, S.CREATE_FN, rows, S.CREATE_TIP)
        except Exception as e:  # noqa: BLE001
            self.show_error(str(e) or e.__class__.__name__)
            return
        # ask the chain first: a refusal is shown here, in red, with its reason
        self.btn.set_enabled(False)
        self.note.text = S.CREATE_CHECKING
        frm, key = self.app.addr.text.strip(), self.app.key.text
        threading.Thread(target=self._dry, args=(t, shown, frm, key), daemon=True).start()

    def _dry(self, t, shown, frm, key):
        ok, reason, err = True, "", ""
        try:
            ok, reason = core.Chain(key).simulate(frm, DSOS_ADDR, t["data"], t["value_wei"])
        except Exception as e:  # noqa: BLE001
            err = str(e)                 # no node answered: go on, the wallet checks again

        def done(dt):
            self.btn.set_enabled(True)
            self.refresh()
            if not ok:
                self.show_error(S.CREATE_ERR_DRY.format(reason=reason))
                return
            if err:
                self.note.text = err
            summary, fn, rows, tip = shown
            self.app.open_overlay(TxScreen(self.app, t, summary, fn, rows, tip))
        Clock.schedule_once(done, 0)
