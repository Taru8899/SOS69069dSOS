"""Sell records page (A / B offers): see an escrow, write your records to the SOS ledger, confirm
them in dSOS. Builds the data; the wallet app signs and sends. The app holds no keys."""
import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.utils import escape_markup

import core
import sell
import strings as S
import tx
from design import BTN_OFF_DARK, FONT_HELPER, FONT_ROW, FONT_SECTION, FONT_TITLE, TRACK_GRAY
from page_offers import STATUS_STYLE
from page_tx import TxScreen
from theme import (BLACK, BLUE, BROWN, CREAM, DARK_GREEN, GRAY, GREEN, LEDGER_ADDR, LIGHT, PILL_BG,
                   WHITE, left_text, short)
from widgets import (home_btn, Badge, Card, Choice, IconBtn, Overlay, Pill, PullScroll, Tappable, ThinBar, label,
                     make_input, text_label, title_row)


class DoneHook:
    """Mixin for a TxScreen: calls `on_ok()` once the transaction is confirmed (the page refreshes)."""
    on_ok = None

    def confirmed(self, h, ok, block, reason):
        super().confirmed(h, ok, block, reason)
        if ok and self.on_ok:
            self.on_ok()


class SyncTxScreen(DoneHook, TxScreen):
    pass


class RecordsTxScreen(DoneHook, TxScreen):
    """A TxScreen whose transaction does not exist yet: the wallet first signs every record
    (eth_signTypedData_v4), then the batch is checked against the ledger and sent."""

    def __init__(self, app, plan, summary, rows, tip="", warn="", **kw):
        self.plan = plan                   # {"id", "donor", "hashes": [32 raw bytes, ...]}
        self.sigs = []
        self.final = None
        placeholder = {"to": LEDGER_ADDR.lower(), "value_wei": 0, "value_eth": "0", "data": "0x",
                       "params": {}, "plain": True, "ledger": True}
        super().__init__(app, placeholder, summary, "recordSignatureOne", rows, tip, warn, **kw)

    def start_dry_run(self):
        if not self.frm:
            self.sim_card.lbl.text = S.SIM_NEEDS_WALLET
            return
        self.sim_card.lbl.text = S.SELL_SIM_LATER.format(n=len(self.plan["hashes"]))

    # the base class calls ask_send(t0) once the wallet is connected: sign first, send later
    def ask_send(self, t):
        if self.final is not None:
            super().ask_send(self.final)
            return
        self.sign_next()

    def sign_next(self):
        if not self.alive:
            return
        n, i = len(self.plan["hashes"]), len(self.sigs)
        if i >= n:
            self.signed()
            return
        typed = tx.ledger_typed_data(self.frm, self.plan["donor"], self.plan["hashes"][i], "")
        self.show(S.SELL_SIGNING.format(i=i + 1, n=n, wallet=self.wallet.label()))
        self.sign_typed(typed, ("eth_signTypedData_v4", "eth_signTypedData_v3"))

    @staticmethod
    def _unsupported(text, code):
        """True when the wallet says it does not offer this signing method."""
        t = (text or "").lower()
        return code in (-32601, 4200) or any(k in t for k in (
            "not exist", "not available", "method not found", "not supported", "unsupported",
            "not allowed", "invalid method"))

    def sign_typed(self, typed, methods):
        """Ask for a typed-data signature; when the wallet refuses the method, try the next one.
        (The record has no arrays, so v3 signs exactly the same message as v4.)"""
        granted = list(getattr(self.wallet, "methods", []) or [])
        if methods is not None and len(methods) == 2:
            self.note("wallet session allows: %s" % (", ".join(granted) or "(unknown)"))
        if granted and not any(m in granted for m in methods):
            self.note("signing was not granted in this session")
            self.no_typed_sign()
            return
        method, rest = methods[0], methods[1:]

        def on_err(text, code=None):
            if rest and self._unsupported(text, code):
                self.note("%s refused, trying %s" % (method, rest[0]))
                self.sign_typed(typed, rest)
            elif self._unsupported(text, code):
                self.no_typed_sign()
            else:
                self.fail(text, code)
        self.request(method, [self.frm, typed], self.got_sig, S.TX_STEP_SIGN, on_err=on_err)

    def no_typed_sign(self):
        """The wallet session has no typed-data signing: offer one fresh, strict connection."""
        self.busy = False
        if getattr(self.wallet, "_strict", False):          # already asked strictly: nothing more to try
            self.fail_final(S.SELL_NO_TYPED_SIGN)
            return
        self.reconnect_strict()                             # once, automatically: no extra button press

    def reconnect_strict(self):
        self.sigs = []
        self.busy = True
        self.show(S.SELL_RECONNECTING.format(wallet=self.wallet.label()))
        self.wallet.connect(self.after_reconnect, self.fail_final, strict=True)

    def after_reconnect(self):
        if self.alive:
            self.sign_next()

    def got_sig(self, result):
        if not self.alive:
            return
        try:
            sig = bytes.fromhex(str(result)[2:])
            if len(sig) != 65:
                raise ValueError("signature length")
        except Exception:  # noqa: BLE001
            self.fail("bad signature")
            return
        self.sigs.append(sig)
        self.sign_next()

    def signed(self):
        n = len(self.sigs)
        self.show(S.SELL_SIGNED.format(n=n))
        t = tx.ledger_batch_tx(self.frm, self.plan["donor"], self.plan["hashes"], self.sigs)
        threading.Thread(target=self._check, args=(t,), daemon=True).start()

    def _check(self, t):
        try:
            ok, reason = core.Chain("").simulate(self.frm, t["to"], t["data"], 0)
        except Exception:  # noqa: BLE001
            ok, reason = True, ""              # no node reachable: the chain decides
        Clock.schedule_once(lambda dt: self.checked(t, ok, reason))

    def checked(self, t, ok, reason):
        if not self.alive:
            return
        if not ok:
            self.busy = False
            self.sigs = []                     # signatures that the ledger refused are not reused
            self.show(S.SELL_SIGN_BAD.format(reason=escape_markup(self.reason_text(reason))),
                      bg=BLACK, fg=WHITE)
            self.refresh_buttons()
            return
        self.final = t
        self.t0 = t
        super().ask_send(t)

    def confirmed(self, h, ok, block, reason):
        super().confirmed(h, ok, block, reason)
        if ok and self.alive:
            self.status.text = S.SELL_WROTE_NEXT


class SellScreen(Overlay):
    def __init__(self, app, sale_id=None, **kw):
        super().__init__(**kw)
        self.app = app
        self.d = app.data
        self.me = self.d["address"].strip()
        self.sale = None
        self.state = None
        self.block = self.d.get("block", 0)
        self.alive = True
        self.gen = 0                       # a newer list load makes older answers stale
        self.found, self.marks, self.sold = [], None, None
        self.open_done, self.open_err = False, ""

        col = BoxLayout(orientation="vertical")
        head = BoxLayout(size_hint_y=None, height=dp(64), padding=[dp(14), dp(8)], spacing=dp(6))
        back = IconBtn(icon="back", bg=WHITE, color=BLACK, size_hint=(None, 1), width=dp(44))
        back.bind(on_release=lambda *_: self.close())
        head.add_widget(home_btn(app, before=self.close))
        head.add_widget(back)
        head.add_widget(label(S.SELL_TITLE, font_size=FONT_TITLE))
        col.add_widget(head)

        sv = PullScroll(on_pull=self.pull)
        form = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None,
                         padding=[dp(14), 0, dp(14), dp(20)])
        form.bind(minimum_height=form.setter("height"))
        self.form = form
        # one plain line of steps (15 sp like the old box text) and the A / B allowance, no box
        self.steps = text_label(S.SELL_STEPS, font_size="15sp")
        self.allow = None
        if self.d.get("produced") or self.d.get("redeemed"):
            self.allow = text_label(S.OFFERS_ALLOWANCE.format(
                allow=self.d["allowance"], produced=self.d["produced"], redeemed=self.d["redeemed"]),
                font_size=FONT_HELPER, bold=True)

        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.id_in = make_input(S.HINT_SELL_ID, str(sale_id) if sale_id else "", filt="int")
        go = Choice(base=BLUE, fg=WHITE, text=S.BTN_SELL_LOAD, bold=True, size_hint=(None, 1), width=dp(90))
        go.bind(on_release=lambda *_: self.load())
        row.add_widget(self.id_in)
        row.add_widget(go)
        self.row = row

        # message / offer info / open offers: an empty one is taken out, so it leaves no gap
        self.msg = text_label("", font_size=FONT_HELPER, bold=True)
        self.msg.bind(text=lambda *_: self._sync())
        self.info = self._box()
        self.open_box = self._box()
        self._sync()

        sv.add_widget(form)
        col.add_widget(sv)
        self.add_widget(col)
        self.k_in = self.n_in = None
        self.load_open()
        if sale_id:
            self.load()

    def _box(self):
        b = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        b.bind(minimum_height=b.setter("height"))
        b.bind(children=lambda *_: self._sync())
        return b

    def _sync(self):
        want = [self.row, self.steps] + ([self.allow] if self.allow else [])
        if self.msg.text:
            want.append(self.msg)
        want += [b for b in (self.info, self.open_box) if b.children]
        if list(reversed(self.form.children)) != want:
            self.form.clear_widgets()
            for w in want:
                self.form.add_widget(w)

    def close(self):
        self.alive = False
        self.app.close_top()

    def chain(self):
        return core.Chain(self.app.key.text)

    # ------------------------------------------------------------ open offers list
    def load_open(self):
        self.gen += 1
        gen = self.gen
        self.found, self.marks, self.sold = [], None, None
        self.open_done, self.open_err = False, ""
        self.draw_open()

        def work():
            ch = self.chain()
            try:
                try:
                    blk = ch.block()
                except Exception:  # noqa: BLE001
                    blk = 0
                now = blk or self.block
                scan = sell.scan_sales(ch)
                found = [s for s in scan if sell.is_open(s, now)][:sell.OPEN_LIMIT]
            except Exception as e:  # noqa: BLE001
                err = str(e) or e.__class__.__name__
                Clock.schedule_once(lambda dt: self.open_loaded(gen, 0, [], err))
                return
            Clock.schedule_once(lambda dt: self.open_loaded(gen, blk, found, ""))
            try:                           # second pass: what you did on each one
                marks, sold = sell.my_view(ch, scan, self.me, now)
            except Exception:  # noqa: BLE001
                marks, sold = {}, []
            Clock.schedule_once(lambda dt: self.marks_loaded(gen, marks, sold))
        threading.Thread(target=work, daemon=True).start()

    def open_loaded(self, gen, blk, found, err):
        if not self.alive or gen != self.gen:
            return
        if blk:
            self.block = blk
        self.found, self.open_err, self.open_done = found, err, True
        self.draw_open()

    def marks_loaded(self, gen, marks, sold):
        if not self.alive or gen != self.gen:
            return
        self.marks, self.sold = marks, sold
        self.draw_open()

    def draw_open(self):
        b = self.open_box
        b.clear_widgets()
        b.add_widget(title_row(S.SELLC_OPEN_H))
        if not self.open_done:
            b.add_widget(label(S.SELL_OPEN_LOADING, size_hint_y=None, height=dp(28)))
            return
        if self.open_err:
            b.add_widget(Card(S.SELL_ERROR.format(error=escape_markup(self.open_err))))
            return
        if not self.found:
            b.add_widget(label(S.SELL_OPEN_NONE, size_hint_y=None, height=dp(44), valign="top",
                               font_size=FONT_HELPER, bold=True))
        for s in self.found:
            b.add_widget(self.sale_card(s))
        b.add_widget(title_row(S.SELLC_SOLD_H))
        if self.sold is None:
            b.add_widget(label(S.SELLC_SOLD_LOADING, size_hint_y=None, height=dp(28)))
        elif not self.sold:
            b.add_widget(label(S.SELLC_SOLD_NONE, size_hint_y=None, height=dp(44), valign="top",
                               font_size=FONT_HELPER, bold=True))
        for r in self.sold or []:
            b.add_widget(self.sold_card(r))

    def pill(self, text, bg, fg):
        return Pill(text=text, bg=bg, color=fg, bold=True, font_size="13sp", size_hint=(None, None),
                    size=(dp(104), dp(30)), pos_hint={"center_y": 0.5})

    def card_row(self, kind, title, sub, pill):
        row = BoxLayout(size_hint_y=None, height=dp(58), spacing=dp(12))
        row.add_widget(Badge(kind, pos_hint={"center_y": 0.5}))
        mid = BoxLayout(orientation="vertical")
        mid.add_widget(label(title, font_size=FONT_ROW))
        mid.add_widget(label(sub, font_size=FONT_HELPER, bold=True))
        row.add_widget(mid)
        row.add_widget(pill)
        return row

    def sale_card(self, s):
        """One open A / B offer, drawn like the cards of the Offers tab; the pill says what you did."""
        m = (self.marks or {}).get(s["id"])
        state = m["state"] if m else ("loading" if self.marks is None else "open")
        n = m["next"] if m else 0
        text, bg, fg = {
            "open": (S.MARK_OPEN, PILL_BG, DARK_GREEN),
            "written": (S.MARK_WRITTEN, CREAM, BROWN),
            "synced": (S.MARK_SYNCED.format(n=n), DARK_GREEN, WHITE),
            "named": (S.MARK_NAMED, WHITE, BTN_OFF_DARK),
            "loading": (S.MARK_LOADING, TRACK_GRAY, BTN_OFF_DARK),
        }[state]
        left = s["sweepable_at"] - self.block
        grey = state in ("written", "named")          # still tappable: "written" is the one to Sync
        c = Tappable(orientation="vertical", padding=dp(12), spacing=dp(6), size_hint_y=None,
                     height=dp(128), bg=GRAY if grey else WHITE)
        c.bind(on_release=lambda *_, i=s["id"]: self.pick(i))
        if s["kind"] == "B":
            you = s["target"].lower() == self.me.lower()
            sub = S.SELLC_SUB_YOU if you else S.SELLC_SUB_NAMED.format(target=short(s["target"]))
        else:
            sub = S.SELLC_SUB
        c.add_widget(self.card_row(s["kind"], S.SELLC_TITLE.format(id=s["id"], records=s["records_left"]),
                                   sub.format(per=s["per_record"]), self.pill(text, bg, fg)))
        window = max(s["sweepable_at"] - s["created_at"], 1)
        c.add_widget(ThinBar(left / window, BLACK if left <= core.WINDOW else GREEN))
        c.add_widget(label(S.SELLC_LEFT.format(left=left_text(left), block=s["sweepable_at"]),
                           size_hint_y=None, height=dp(22), font_size=FONT_HELPER, bold=True))
        return c

    def sold_card(self, r):
        """An offer you already sold records to, with the state of the offer that holds your slices."""
        earned = r["earned"]
        o = next((x for x in (self.app.data or {}).get("offers", []) if earned and x["id"] == earned), None)
        slices = r["records"] * r["per"]
        sub = S.SOLD_SUB.format(slices=slices, earned=earned) if earned else S.SOLD_SUB_NONE.format(slices=slices)
        if o:
            bg, fg, bar = STATUS_STYLE.get(o["status"], STATUS_STYLE["redeemable"])
            text = S.STATUS.get(o["status"], o["status"])
        else:
            bg, fg, bar, text = TRACK_GRAY, BTN_OFF_DARK, GREEN, S.STATUS["closed"]
        live = bool(o) and o["left"] > 0
        c = Tappable(orientation="vertical", padding=dp(12), spacing=dp(6), size_hint_y=None,
                     height=dp(128 if live else 80))
        c.bind(on_release=lambda *_, rr=r: self.open_sold(rr))
        c.add_widget(self.card_row(r["kind"], S.SOLD_TITLE.format(id=r["id"], n=r["records"]), sub,
                                   self.pill(text, bg, fg)))
        if live:
            window = max(o.get("sweepable_at", 0) - o.get("created_at", 0), 1)
            c.add_widget(ThinBar(o["left"] / window, bar))
            c.add_widget(label(S.OC_LEFT.format(left=left_text(o["left"]), block=o["sweepable_at"]),
                               size_hint_y=None, height=dp(22), font_size=FONT_HELPER, bold=True))
        return c

    def open_sold(self, r):
        earned = r["earned"]
        if earned and any(x["id"] == earned and x["left"] > 0 for x in self.app.data.get("offers", [])):
            self.alive = False
            self.app.go_offer(earned)          # your earned offer, in the Offers tab
        else:
            self.pick(r["id"])

    def pull(self):
        """Pull down: read the list (and the open offer) again."""
        self.load_open()
        if self.sale:
            self.load()

    def after_tx(self):
        """A write / sync / sweep was confirmed: read the lists again a moment later."""
        def again(_dt):
            if self.alive:
                self.pull()
        Clock.schedule_once(again, 3)

    def pick(self, sale_id):
        self.id_in.text = str(sale_id)
        self.load()

    # ------------------------------------------------------------ one offer
    def load(self):
        t = self.id_in.text.strip()
        if not t.isdigit() or int(t) < 1:
            self.msg.text = S.SELL_BAD_ID
            return
        sid = int(t)
        self.msg.text = S.SELL_LOADING.format(id=sid)
        self.info.clear_widgets()

        def work():
            try:
                ch = self.chain()
                blk = ch.block()
                sale = sell.load_sale(ch, sid)
                st = sell.seller_state(ch, sale, self.me) if sale else None
                res = (blk, sale, st, "")
            except Exception as e:  # noqa: BLE001
                res = (0, None, None, str(e) or e.__class__.__name__)
            Clock.schedule_once(lambda dt: self.loaded(sid, *res))
        threading.Thread(target=work, daemon=True).start()

    def loaded(self, sid, blk, sale, st, err):
        if not self.alive:
            return
        if err:
            self.msg.text = S.SELL_ERROR.format(error=escape_markup(err))
            return
        if blk:
            self.block = blk
        if sale is None:
            self.msg.text = S.SELL_NOT_SALE
            return
        self.msg.text = ""
        self.sale, self.state = sale, st
        self.render_info()

    def render_info(self):
        s, st = self.sale, self.state
        b = self.info
        b.clear_widgets()
        ok, why = sell.can_sell(s, self.me, self.block)
        left = s["sweepable_at"] - self.block
        named = S.SELL_INFO_NAMED.format(target=short(s["target"])) if s["kind"] == "B" else ""
        b.add_widget(Card(S.SELL_INFO.format(
            id=s["id"], kind=s["kind"], donor=short(s["donor"]), named=named, per=s["per_record"],
            records=s["records_left"], slices=s["slices_left"], block=s["sweepable_at"],
            time=left_text(left),
            state=S.SELL_STATE_OPEN if s["active"] and left > 0 else S.SELL_STATE_CLOSED)))
        capped = S.SELL_MINE_CAPPED.format(n=st["scanned"]) if s["records_left"] > st["scanned"] else ""
        earned = S.SELL_EARNED_ID.format(id=st["earned"]) if st["earned"] else S.SELL_EARNED_NONE
        b.add_widget(Card(S.SELL_MINE.format(nxt=st["next"], ready=st["ready"], capped=capped, earned=earned)))

        if not ok:
            dead = why == "named" and s["kind"] == "B" and s["target"].lower() == tx.DEAD.lower()
            b.add_widget(Card(S.SELL_WHY_DEAD if dead else S.SELL_WHY[why], bg=BLACK, fg=WHITE))
        need = max(0, s["records_left"] - st["ready"])
        if ok:
            b.add_widget(label(S.SELL_HOW_MANY, size_hint_y=None, height=dp(28), font_size=FONT_SECTION))
            self.k_in = make_input(S.HINT_SELL_K.format(max=tx.SELL_BATCH_MAX),
                                   str(max(1, min(need, tx.SELL_BATCH_MAX))), filt="int")
            b.add_widget(self.k_in)
            w = Choice(base=BLUE, fg=WHITE, bold=True, size_hint_y=None, height=dp(52),
                       text=S.BTN_SELL_WRITE_NONE)
            w.bind(on_release=lambda *_: self.on_write())
            b.add_widget(w)
            self.n_in = make_input(S.HINT_SELL_N, str(max(1, st["ready"])), filt="int")
            b.add_widget(self.n_in)
            sy = Choice(base=LIGHT, fg=BLACK, bold=True, size_hint_y=None, height=dp(52),
                        text=S.BTN_SELL_SYNC_NONE)
            sy.bind(on_release=lambda *_: self.on_sync())
            b.add_widget(sy)
        if left <= 0 and s["active"]:
            sw = Choice(base=LIGHT, fg=BLACK, bold=True, size_hint_y=None, height=dp(52),
                        text=S.BTN_SELL_SWEEP)
            sw.bind(on_release=lambda *_: self.on_sweep())
            b.add_widget(sw)
        rl = Choice(base=WHITE, bold=True, size_hint_y=None, height=dp(44), text=S.BTN_SELL_LOAD)
        rl.bind(on_release=lambda *_: self.load())
        b.add_widget(rl)

    # ------------------------------------------------------------ transactions (built, never sent)
    def _int(self, field):
        t = field.text.strip() if field is not None else ""
        return int(t) if t.isdigit() else 0

    def on_write(self):
        s, st = self.sale, self.state
        need = max(0, s["records_left"] - st["ready"])
        if need < 1:
            self.msg.text = S.SELL_ERR_NOTHING_WRITE
            return
        k = min(self._int(self.k_in), tx.SELL_BATCH_MAX, need)
        if k < 1:
            self.msg.text = S.SELL_ERR_K
            return
        self.msg.text = S.SELL_PLANNING
        start = st["next"] + st["ready"]

        def work():
            try:
                hashes = sell.record_hashes(self.chain(), s["id"], self.me, start, k)
                err = ""
            except Exception as e:  # noqa: BLE001
                hashes, err = [], str(e) or e.__class__.__name__
            Clock.schedule_once(lambda dt: self.write_ready(hashes, err))
        threading.Thread(target=work, daemon=True).start()

    def write_ready(self, hashes, err):
        if not self.alive:
            return
        if err:
            self.msg.text = S.SELL_ERROR.format(error=escape_markup(err))
            return
        self.msg.text = ""
        s = self.sale
        plan = {"id": s["id"], "donor": s["donor"], "hashes": hashes}
        n = len(hashes)
        summary = S.SELL_WRITE_SUMMARY.format(n=n, id=s["id"], donor=short(s["donor"]))
        R = S.SELL_WRITE_ROWS
        rows = [(R["signer"], self.me, short(self.me)), (R["to"], s["donor"], short(s["donor"])),
                (R["n"], str(n), str(n))]
        scr = RecordsTxScreen(self.app, plan, summary, rows, S.SELL_WRITE_TIP, S.SELL_WRITE_WARN)
        scr.on_ok = self.after_tx
        self.app.open_overlay(scr)

    def on_sync(self):
        s, st = self.sale, self.state
        n = self._int(self.n_in)
        if n < 1 or n > st["ready"]:
            self.msg.text = S.SELL_ERR_N
            return
        try:
            t = tx.sync_records_tx(s["id"], n, nonce=self.d["redeem_nonce"])
        except Exception as e:  # noqa: BLE001
            self.msg.text = str(e)
            return
        p, R = t["params"], S.SYNC_RECORDS_ROWS
        rows = [(R["id"], p["id"], p["id"]), (R["n"], p["n"], p["n"]),
                (R["nonce"], p["expectedNonce"], p["expectedNonce"])]
        summary = S.SYNC_RECORDS_SUMMARY.format(n=n, id=s["id"], per=s["per_record"])
        scr = SyncTxScreen(self.app, t, summary, S.SYNC_RECORDS_FN, rows, S.SYNC_RECORDS_TIP,
                           S.SYNC_RECORDS_WARN)
        scr.on_ok = self.after_tx
        self.app.open_overlay(scr)

    def on_sweep(self):
        s = self.sale
        t = tx.sweep_offer_tx(s["id"], nonce=self.d["redeem_nonce"])
        rows = [(S.SWEEP_ROWS["id"], str(s["id"]), str(s["id"])),
                (S.SWEEP_ROWS["nonce"], t["params"]["expectedNonce"], t["params"]["expectedNonce"])]
        scr = SyncTxScreen(self.app, t, S.OD_SWEEP_SUMMARY.format(id=s["id"]), S.SWEEP_FN, rows,
                           S.SWEEP_TIP, S.SWEEP_WARN)
        scr.on_ok = self.after_tx
        self.app.open_overlay(scr)
