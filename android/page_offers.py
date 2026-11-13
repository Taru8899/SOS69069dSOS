"""Offers tab (My offers): list, details, redeem / transfer / sweep. Builds data, sends nothing."""
import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

import core
import strings as S
import tx
from page_tx import TxScreen
from theme import (BLACK, BLUE, BROWN, CREAM, DARK_GREEN, GREEN, LIGHT, PILL_BG,
                   RED, WHITE, left_text, set_visible, short)
from widgets import (Badge, Card, Choice, Panel, Pill, ProgressBar, RoundBtn, Tappable, label,
                     make_input)

RED_BG = (1, 0.9, 0.9, 1)
# status -> (pill background, pill text, progress bar color)
STATUS_STYLE = {"redeemable": (PILL_BG, DARK_GREEN, GREEN),
                "expiring": (CREAM, BROWN, BLACK),
                "expired": (RED_BG, RED, RED)}


class OffersPage:
    def __init__(self, app, b, d):
        self.app, self.b, self.d = app, b, d
        # newest first = the order the contract's wallet send uses
        raw_offers = d.get("offers", []) or []
        normalized = []
        for i, source in enumerate(raw_offers):
            o = dict(source or {})
            o.setdefault("id", i)
            o.setdefault("pos", i)
            o.setdefault("kind", "?")
            o.setdefault("donor", "")
            o.setdefault("created_at", 0)
            o.setdefault("count", 0)
            o.setdefault("sweepable_at", 0)
            o.setdefault("left", 0)
            o.setdefault("status", "expired" if int(o.get("left", 0) or 0) <= 0 else "redeemable")
            o.setdefault("sendable", o.get("kind") != "G" and int(o.get("left", 0) or 0) > core.WINDOW)
            for numeric in ("id", "pos", "created_at", "count", "sweepable_at", "left"):
                try:
                    o[numeric] = int(o.get(numeric, 0) or 0)
                except (TypeError, ValueError):
                    o[numeric] = 0
            o["kind"] = str(o.get("kind") or "?")
            o["donor"] = str(o.get("donor") or "")
            normalized.append(o)
        self.offers = sorted(normalized, key=lambda o: int(o.get("pos", 0) or 0), reverse=True)
        state = getattr(app, "offers_state", {}) or {}
        self.filter = state.get("filter", "all")
        default_id = self.offers[0]["id"] if self.offers else None
        self.sel_id = state.get("sel_id", default_id)
        if not any(o["id"] == self.sel_id for o in self.offers):
            self.sel_id = default_id
        selected = next((o for o in self.offers if o["id"] == self.sel_id), None)
        self.amount = max(1, min(int((selected or {}).get("count", 1) or 1), int(state.get("amount", (selected or {}).get("count", 1)) or 1))) if selected else 0
        self.transfer_mode = bool(state.get("transfer_mode", False))
        self.to_text = state.get("to_text", "")
        self.pin_text = state.get("pin_text", "")
        self.pin_msg = state.get("pin_msg", "")
        self.rebuild()

    def persist(self):
        self.app.offers_state = {"filter": self.filter, "sel_id": self.sel_id,
                                 "amount": self.amount, "transfer_mode": self.transfer_mode,
                                 "to_text": self.to_text, "pin_text": self.pin_text,
                                 "pin_msg": self.pin_msg}

    def switch_mode(self, mode):
        self.persist()
        self.app.offers_mode = mode
        self.app.render()

    # ---- helpers
    def visible(self):
        return [o for o in self.offers if self.filter == "all" or o["status"] == self.filter]

    def selected(self):
        for o in self.offers:
            if o["id"] == self.sel_id:
                return o
        return None

    def select(self, oid):
        self.sel_id = oid
        o = self.selected()
        self.amount = o["count"] if o else 0
        self.transfer_mode = False
        self.pin_text = ""
        self.pin_msg = ""
        self.persist()
        self.rebuild()

    def set_filter(self, key):
        self.filter = key
        vis = self.visible()
        if not any(o["id"] == self.sel_id for o in vis):
            self.sel_id = vis[0]["id"] if vis else None
            o = self.selected()
            self.amount = o["count"] if o else 0
            self.transfer_mode = False
            self.pin_text = ""
            self.pin_msg = ""
        self.persist()
        self.rebuild()

    # ---- layout
    def rebuild(self):
        self.persist()
        b = self.b
        b.clear_widgets()
        d = self.d
        mode_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        for mode, caption in (("offers", "Offers"), ("activity", "Activity")):
            tab = Choice(base=WHITE, text=caption, bold=True, font_size="14sp")
            tab.set_selected(mode == "offers")
            tab.bind(on_release=lambda _w, m=mode: self.switch_mode(m))
            mode_row.add_widget(tab)
        b.add_widget(mode_row)
        head = BoxLayout(size_hint_y=None, height=dp(48))
        head.add_widget(label(S.OFFERS_TITLE, font_size="30sp"))
        head.add_widget(label(S.OFFERS_SUMMARY.format(
            n=len(self.offers), slices=sum(o["count"] for o in self.offers)),
            halign="right", size_hint_x=0.7, font_size="14sp"))
        b.add_widget(head)

        chips = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        for key, text in S.OFFERS_FILTERS:
            ch = Choice(base=WHITE, text=text, font_size="13sp", bold=True)
            ch.set_selected(key == self.filter)
            ch.bind(on_release=lambda _w, k=key: self.set_filter(k))
            chips.add_widget(ch)
        b.add_widget(chips)

        vis = self.visible()
        if not vis:
            b.add_widget(label(S.OFFERS_EMPTY, size_hint_y=None, height=dp(40)))
        for o in vis:
            b.add_widget(self.card(o))
            if o["id"] == self.sel_id:
                b.add_widget(self.detail(o))

    def card(self, o):
        expired = o["left"] <= 0
        bg, fg, bar = STATUS_STYLE.get(o["status"], STATUS_STYLE["redeemable"])
        c = Tappable(orientation="vertical", padding=dp(12), spacing=dp(6), size_hint_y=None,
                     height=dp(76 if expired else 118))
        c.set_selected(o["id"] == self.sel_id)
        c.bind(on_release=lambda *_, i=o["id"]: self.select(i))
        eth = core.eth(o["count"] * core.UNIT)
        if expired:
            sub = S.OC_SUB_EXPIRED
        elif o["kind"] == "G":
            sub = S.OC_SUB_GATED.format(eth=eth)
        elif o.get("donor", "").lower() == self.d["address"].lower():
            sub = S.OC_SUB_YOU.format(eth=eth)
        else:
            sub = S.OC_SUB_FROM.format(eth=eth, donor=short(o.get("donor", "")))
        row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(12))
        row.add_widget(Badge(o["kind"], pos_hint={"center_y": 0.5}))
        mid = BoxLayout(orientation="vertical")
        mid.add_widget(label(S.OC_TITLE.format(
            count=o["count"], id=o["id"], pin=S.OFFER_PIN_TAG if o["kind"] == "G" else ""),
            font_size="17sp"))
        mid.add_widget(label(sub, font_size="13sp"))
        row.add_widget(mid)
        row.add_widget(Pill(text=S.STATUS.get(o["status"], o["status"]), bg=bg, color=fg,
                            bold=True, font_size="13sp", size_hint=(None, None),
                            size=(dp(104), dp(30)), pos_hint={"center_y": 0.5}))
        c.add_widget(row)
        if not expired:
            window = max(o.get("sweepable_at", 0) - o.get("created_at", 0), 1)
            c.add_widget(ProgressBar(o["left"] / window, bar))
            c.add_widget(label(S.OC_LEFT.format(left=left_text(o["left"]), block=o["sweepable_at"]),
                               size_hint_y=None, height=dp(20), font_size="13sp"))
        return c

    def detail(self, o):
        expired = o["left"] <= 0
        eth = core.eth(o["count"] * core.UNIT)
        p = Panel(orientation="vertical", spacing=dp(6), size_hint_y=None,
                  height=dp(210 if expired else 372))
        p.add_widget(label(S.OD_TITLE.format(id=o["id"], count=o["count"], eth=eth,
                                             left=left_text(o["left"])),
                           size_hint_y=None, height=dp(54)))
        self.note = Label(text="", color=BLACK, font_size="13sp", halign="left", valign="top")
        self.note.bind(size=lambda i, s: setattr(i, "text_size", s))

        if expired:
            btn = Choice(base=BLUE, fg=WHITE, bold=True, font_size="17sp", size_hint_y=None,
                         height=dp(56), text=S.OD_SWEEP.format(id=o["id"]))
            btn.bind(on_release=lambda *_: self.on_sweep(o))
            p.add_widget(btn)
            self.note.text = S.OD_NOTE_EXPIRED
            p.add_widget(self.note)
            return p

        p.add_widget(label(S.OD_SLICES, size_hint_y=None, height=dp(30)))
        mid = BoxLayout(size_hint_y=None, height=dp(64))
        minus = RoundBtn(text=S.ICON_MINUS, font_size="30sp", bg=BLACK, color=WHITE,
                         size_hint=(None, 1), width=dp(64))
        minus.bind(on_release=lambda *_: self.set_amount(self.amount - 1))
        plus = RoundBtn(text=S.ICON_PLUS, font_size="28sp", bg=BLACK, color=WHITE,
                        size_hint=(None, 1), width=dp(64))
        plus.bind(on_release=lambda *_: self.set_amount(self.amount + 1))
        self.of_mid = label("", halign="center")
        mid.add_widget(minus)
        mid.add_widget(self.of_mid)
        mid.add_widget(plus)
        p.add_widget(mid)

        self.to_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.to_in = make_input(S.HINT_RECIPIENT, self.to_text)
        self.to_in.bind(text=lambda _i, v: self.on_to_text(v))
        pb = Button(text=S.BTN_PASTE, size_hint=(None, 1), width=dp(72), background_normal="",
                    background_color=BLUE, color=WHITE, bold=True)
        pb.bind(on_release=lambda *_: self.paste_to())
        self.to_row.add_widget(self.to_in)
        self.to_row.add_widget(pb)
        p.add_widget(self.to_row)

        if o["kind"] == "G":                  # gated: the PIN goes where the recipient would be
            pin_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
            self.pin_in = make_input(S.OD_PIN_HINT, self.pin_text, password=True)
            self.pin_in.bind(text=lambda _i, v: self.on_pin_text(v))
            pp = Button(text=S.BTN_PASTE, size_hint=(None, 1), width=dp(72), background_normal="",
                        background_color=BLUE, color=WHITE, bold=True)
            pp.bind(on_release=lambda *_: self.paste_pin())
            pin_row.add_widget(self.pin_in)
            pin_row.add_widget(pp)
            p.add_widget(pin_row)

        btns = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(10))
        self.redeem_btn = Choice(base=BLUE, fg=WHITE, bold=True, font_size="16sp")
        self.redeem_btn.bind(on_release=lambda *_: self.on_redeem(o))
        self.transfer_btn = Choice(base=LIGHT, fg=BLACK, bold=True, font_size="16sp")
        self.transfer_btn.bind(on_release=lambda *_: self.on_transfer(o))
        btns.add_widget(self.redeem_btn)
        btns.add_widget(self.transfer_btn)
        p.add_widget(btns)
        p.add_widget(self.note)
        self.refresh_detail()
        return p

    # ---- detail state
    def set_amount(self, n):
        o = self.selected()
        if o:
            self.amount = max(1, min(o["count"], n))
            self.persist()
            self.refresh_detail()

    def on_to_text(self, v):
        self.to_text = v
        self.persist()
        if self.transfer_mode:
            self.refresh_detail()

    def paste_to(self):
        import util
        t = util.paste_text()
        if t:
            self.to_in.text = t
        else:
            self.note.text = S.MSG_CLIPBOARD_EMPTY_DOT

    def on_pin_text(self, v):
        self.pin_text = v
        self.persist()
        if self.pin_msg:
            self.pin_msg = ""
            self.refresh_detail()

    def paste_pin(self):
        import util
        t = util.paste_text()
        if t:
            self.pin_in.text = t
        else:
            self.note.text = S.MSG_CLIPBOARD_EMPTY_DOT

    def transfer_problem(self):
        a = self.to_text.strip()
        if not tx.valid_address(a):
            return S.SEND_ERR_ADDRESS
        low = a.lower()
        if low == self.d["address"].strip().lower():
            return S.SEND_ERR_SELF
        if low == core.DSOS:
            return S.SEND_ERR_CONTRACT
        if low == tx.ZERO_ADDR:
            return S.SEND_ERR_ZERO
        return ""

    def refresh_detail(self):
        o = self.selected()
        if not o or o["left"] <= 0:
            return
        n, total = self.amount, o["count"]
        gated = o["kind"] == "G"
        self.of_mid.text = S.OD_OF.format(n=n, total=total)
        self.redeem_btn.text = S.OD_REDEEM.format(eth=core.eth(n * core.UNIT))
        self.transfer_btn.text = S.OD_TRANSFER.format(n=n)
        self.redeem_btn.set_enabled(True)
        self.transfer_btn.set_enabled(not gated)
        set_visible(self.to_row, self.transfer_mode and not gated)
        s = "" if n == 1 else "s"
        if gated:
            self.note.text = self.pin_msg or S.OD_NOTE_GATED
        elif self.transfer_mode:
            self.note.text = self.transfer_problem() or S.OD_NOTE_TRANSFER.format(n=n, s=s)
        elif n < total:
            r = total - n
            self.note.text = S.OD_NOTE_PARTIAL.format(n=r, s="" if r == 1 else "s")
        else:
            self.note.text = S.OD_NOTE_ALL

    # ---- transactions (built, never sent)
    def on_redeem(self, o):
        if o["left"] <= 0:
            return
        n = self.amount
        if o["kind"] == "G":
            self.redeem_gated(o, n)
        else:
            self.open_redeem_tx(o, n, None)

    def redeem_gated(self, o, n):
        text = self.pin_text.strip()
        if not text:
            self.pin_msg = S.OD_PIN_NEEDED
            self.refresh_detail()
            return
        self.pin_msg = S.OD_PIN_CHECKING
        self.refresh_detail()
        threading.Thread(target=self._pin_worker,
                         args=(o, n, text, self.d["address"].strip()), daemon=True).start()

    def _pin_worker(self, o, n, text, me):
        """Read the offer's on-chain PIN hash and find which form of the typed PIN matches it."""
        try:
            c = core.Chain(self.app.key.text).pin_commitment(o["id"])
            pin = tx.match_pin(text, c, o.get("donor", ""), me)
            Clock.schedule_once(lambda dt: self.pin_done(o, n, pin, None))
        except Exception as e:  # noqa: BLE001
            m = str(e)
            Clock.schedule_once(lambda dt: self.pin_done(o, n, None, m))

    def pin_done(self, o, n, pin, err):
        if self.sel_id != o["id"]:
            return                              # the person moved on to another offer
        if err:
            self.pin_msg = S.OD_PIN_ERROR.format(error=err)
        elif pin is None:
            self.pin_msg = S.OD_PIN_BAD
        else:
            self.pin_msg = ""
            self.open_redeem_tx(o, n, pin)
        self.refresh_detail()

    def open_redeem_tx(self, o, n, pin):
        t = tx.redeem_slices_tx(o["id"], n, pin, o.get("donor"))
        p = t["params"]
        R = S.RO_ROWS
        rows = [(R["id"], p["id"], p["id"]), (R["slices"], p["slices"], p["slices"]),
                (R["pin"], p["pin"], short(p["pin"])),
                (R["r"], p["r"], '["' + short(p["payloadHash"]) + '","0x",""]')]
        summary = S.RO_SUMMARY.format(n=n, id=o["id"], kind=o["kind"], eth=t["payout_eth"])
        tip = (S.RO_TIP_PIN if pin is not None else S.RO_TIP).format(
            wallet=short(self.d["address"]), block=o["sweepable_at"])
        self.app.safe_overlay(lambda: TxScreen(self.app, t, summary, S.RO_FN, rows, tip, S.RO_WARN))

    def on_transfer(self, o):
        if o["kind"] == "G" or o["left"] <= 0:
            return
        if not self.transfer_mode:            # first tap: ask for the recipient
            self.transfer_mode = True
            self.persist()
            self.refresh_detail()
            return
        if self.transfer_problem():
            self.refresh_detail()
            return
        n, to = self.amount, self.to_text.strip()
        t = tx.transfer_slices_tx(o["id"], n, to)
        p = t["params"]
        R = S.OT_ROWS
        rows = [(R["id"], p["id"], p["id"]), (R["slices"], p["slices"], p["slices"]),
                (R["to"], to, short(to)),
                (R["r"], p["r"], '["' + short(p["payloadHash"]) + '","0x",""]')]
        summary = S.OT_SUMMARY.format(n=n, id=o["id"], kind=o["kind"], to=short(to))
        tip = S.OT_TIP.format(wallet=short(self.d["address"]))
        self.app.safe_overlay(lambda: TxScreen(self.app, t, summary, S.OT_FN, rows, tip, S.OT_WARN))

    def on_sweep(self, o):
        t = tx.sweep_offer_tx(o["id"])
        summary = S.OD_SWEEP_SUMMARY.format(id=o["id"])
        rows = [(S.SWEEP_ROWS["id"], str(o["id"]), str(o["id"]))]
        self.app.safe_overlay(lambda: TxScreen(self.app, t, summary, S.SWEEP_FN, rows,
                                       S.SWEEP_TIP, S.SWEEP_WARN))


class ActivityPage:
    """Read-only transaction Activity, sharing the existing Chain and page container."""
    def __init__(self, app, box, data):
        self.app, self.box, self.data = app, box, data
        app.activity_scope = getattr(app, "activity_scope", "mine")
        app.activity_filter = getattr(app, "activity_filter", "all")
        app.activity = getattr(app, "activity", [])
        app.activity_loading = getattr(app, "activity_loading", False)
        app.activity_error = getattr(app, "activity_error", None)
        self.render()

    def render(self):
        b = self.box
        b.clear_widgets()
        mode_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        for mode, caption in (("offers", "Offers"), ("activity", "Activity")):
            tab = Choice(base=WHITE, text=caption, bold=True, font_size="14sp")
            tab.set_selected(mode == "activity")
            tab.bind(on_release=lambda _w, m=mode: self.switch_mode(m))
            mode_row.add_widget(tab)
        b.add_widget(mode_row)
        head = BoxLayout(size_hint_y=None, height=dp(46))
        head.add_widget(label("Activity", font_size="28sp"))
        refresh = Choice(base=BLUE, fg=WHITE, text="Refresh", bold=True, size_hint_x=None, width=dp(100))
        refresh.bind(on_release=lambda *_: self.load())
        head.add_widget(refresh)
        b.add_widget(head)

        scopes = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        for scope, caption in (("mine", "Mine"), ("contract", "Contract")):
            ch = Choice(base=WHITE, text=caption, bold=True, font_size="13sp")
            ch.set_selected(self.app.activity_scope == scope)
            ch.bind(on_release=lambda _w, v=scope: self.set_scope(v))
            scopes.add_widget(ch)
        b.add_widget(scopes)
        filters = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        for key, caption in (("all", "All"), ("offers", "Offers"), ("ledger", "Ledger"), ("failed", "Failed")):
            ch = Choice(base=WHITE, text=caption, bold=True, font_size="12sp")
            ch.set_selected(self.app.activity_filter == key)
            ch.bind(on_release=lambda _w, v=key: self.set_filter(v))
            filters.add_widget(ch)
        b.add_widget(filters)

        if self.app.activity_loading:
            b.add_widget(Card("Loading on-chain Activity…"))
        if self.app.activity_error:
            b.add_widget(Card("[color=bb001f]Activity error[/color]\n" + str(self.app.activity_error), fg=BLACK))
        items = self.filtered()
        if not items and not self.app.activity_loading and not self.app.activity_error:
            b.add_widget(Card("No Activity found in the recent indexed block range."))
        for item in items:
            row = Tappable(orientation="vertical", size_hint_y=None, height=dp(92), padding=dp(10), spacing=dp(3))
            with row.canvas.before:
                from kivy.graphics import Color, RoundedRectangle
                Color(1, 1, 1, 1)
                bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(12)])
            row.bind(pos=lambda w, p, r=bg: setattr(r, "pos", p), size=lambda w, z, r=bg: setattr(r, "size", z))
            row.add_widget(label(item.get("title", "Contract activity"), font_size="16sp"))
            stamp = item.get("timestamp") or 0
            when = __import__("datetime").datetime.fromtimestamp(stamp).strftime("%Y-%m-%d %H:%M") if stamp else "Time unavailable"
            amount = core.eth(item.get("amount_wei", 0)) if item.get("amount_wei", 0) else ""
            sub = f"{when}  ·  Block {item.get('block', 0)}"
            if amount:
                sub += f"  ·  {amount} ETH"
            row.add_widget(label(sub, font_size="12sp", color=(0.25, 0.28, 0.28, 1)))
            short_hash = item.get("hash", "")
            row.add_widget(label((short_hash[:10] + "…" + short_hash[-8:]) if len(short_hash) > 20 else short_hash,
                                 font_size="11sp", color=BLUE))
            row.bind(on_release=lambda _w, it=item: self.show_detail(it))
            b.add_widget(row)

        if self.app.activity and self.app.activity_scope == "mine":
            b.add_widget(label("Mine includes indexed successful events. Failed transactions are included when Etherscan API access is available.",
                               font_size="11sp", color=(0.25, 0.28, 0.28, 1), size_hint_y=None, height=dp(34)))
        if not self.app.activity and not self.app.activity_loading and not self.app.activity_error:
            self.load()

    def filtered(self):
        items = list(self.app.activity or [])
        f = self.app.activity_filter
        if f == "offers":
            items = [x for x in items if any(e.get("contract") == "dsos" and e.get("event") != "Transfer"
                                               for e in x.get("events", []))]
        elif f == "ledger":
            items = [x for x in items if any(e.get("contract") == "ledger" for e in x.get("events", []))]
        elif f == "failed":
            items = [x for x in items if x.get("failed")]
        return items[:100]

    def switch_mode(self, mode):
        self.app.offers_mode = mode
        self.app.render()

    def set_scope(self, scope):
        self.app.activity_scope = scope
        self.load()

    def set_filter(self, key):
        self.app.activity_filter = key
        self.render()

    def load(self):
        if self.app.activity_loading:
            return
        self.app.activity_loading = True
        self.app.activity_error = None
        self.render()
        scope = self.app.activity_scope
        address = self.data.get("address", "")
        api_key = self.app.key.text.strip()
        def worker():
            try:
                chain = core.Chain(api_key)
                result = chain.activity_mine(address) if scope == "mine" else chain.activity_contract()
                rows = result.get("items", [])
                err = None
            except Exception as exc:
                rows, err = [], str(exc)
            Clock.schedule_once(lambda _dt: self.done(rows, err, scope))
        threading.Thread(target=worker, daemon=True).start()

    def done(self, rows, err, loaded_scope):
        self.app.activity = rows
        self.app.activity_error = err
        self.app.activity_loading = False
        if self.app.page == "offers" and getattr(self.app, "offers_mode", "offers") == "activity":
            if self.app.activity_scope != loaded_scope:
                self.load()
            else:
                self.render()

    def show_detail(self, item):
        events = item.get("events", [])
        detail = [f"[b]{item.get('title', 'Activity')}[/b]", item.get("hash", ""),
                  f"Block: {item.get('block', 0)}", f"From: {item.get('from', '')}",
                  f"To: {item.get('to', '')}"]
        if item.get("offer_id") is not None:
            detail.append(f"Offer ID: {item['offer_id']}")
        if item.get("function"):
            detail.append(f"Function: {item['function']}")
        for key, value in (item.get("input_args") or {}).items():
            detail.append(f"{key}: {value}")
        for ev in events:
            detail.append(f"• {ev.get('event')} ({ev.get('contract')})")
        self.app.safe_overlay(lambda: Card("\n".join(detail), bg=WHITE, size_hint=(0.92, None),
                                   pos_hint={"center_x": .5, "center_y": .5}))


def build(app, b, d):
    if getattr(app, "offers_mode", "offers") == "activity":
        ActivityPage(app, b, d)
    else:
        OffersPage(app, b, d)
