"""Activity (inside the Offers tab): dSOS events grouped per transaction, Mine or Contract."""
import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.utils import escape_markup

import activity
import core
import strings as S
import util
from theme import BLACK, BLUE, ETHERSCAN_TX, GREEN, RED, WHITE, short
from widgets import Card, Choice, Dot, Panel, Tappable, label


class Slot:
    """State of one view (Mine / Contract): the store, a busy flag and the last error."""

    def __init__(self):
        self.store = None
        self.busy = False
        self.error = ""


def row_title(r):
    amt = (S.ACT_AMT_CREDITS if r["kind"] == "formed" or r["kind"] == "credit_redeemed"
           else S.ACT_AMT_DSOS).format(n=r["dsos"]) if r["dsos"] else S.ACT_AMT_UNKNOWN
    idpart = S.ACT_IDPART.format(id=r["offer_id"]) if r["offer_id"] is not None else ""
    return S.ACT_TITLE[r["kind"]].format(amt=amt, id=r["offer_id"], idpart=idpart,
                                         fn=r.get("who") or "?")


def row_amount(r):
    """(text, colour) of the amount on the right."""
    if r["failed"] or not r["eth"] or not r["sign"]:
        return "", BLACK
    t = core.eth(r["eth"])
    return (("+" if r["sign"] > 0 else "-") + t, GREEN if r["sign"] > 0 else BLACK)


def row_sub(r):
    eth = S.ACT_SUB_ETH.format(eth=core.eth(r["eth"])) if r["eth"] and not r["failed"] else ""
    when = ""
    if r["ts"]:
        a = activity.ago(r["ts"])
        when = (S.ACT_SUB_WHEN_APPROX if r.get("approx") else S.ACT_SUB_WHEN).format(ago=a)
    sub = S.ACT_SUB.format(eth=eth, when=when, block=r["block"])
    if r["failed"]:
        sub = S.ACT_FAILED_SUB + " · " + sub
    if r.get("note") == "staked" and r.get("staked_user") == (r.get("me") or ""):
        sub += " · " + S.ACT_NOW_STAKED
    return sub


def matches(r, key):
    return key == "all" or activity.FILTER_TAGS.get(key) in r["tags"]


class ActivityPage:
    def __init__(self, app, b, d):
        self.app, self.b, self.d = app, b, d
        self.ui = app.ui
        self.me = d["address"].strip().lower()

    # -- data
    def slot(self):
        sc = self.ui["act_scope"]
        s = self.app.activity.get(sc)
        if s is None:
            s = self.app.activity[sc] = Slot()
        return s

    def start(self, older=False):
        slot = self.slot()
        if slot.busy:
            return
        slot.busy = True
        slot.error = ""
        sc = self.ui["act_scope"]
        app = self.app
        key = app.key.text
        me = self.me

        def work():
            try:
                if slot.store is None or not older:
                    st = activity.Store(core.Chain(key), me, sc)
                    st.refresh()
                    slot.store = st
                else:
                    slot.store.older()
            except Exception as e:  # noqa: BLE001
                slot.error = str(e) or type(e).__name__
            slot.busy = False
            Clock.schedule_once(lambda dt: self.done(slot))
        threading.Thread(target=work, daemon=True).start()

    def done(self, slot):
        if self.app.activity.get(self.ui["act_scope"]) is slot and self.app.page == "offers" \
                and self.ui["offers_tab"] == "activity":
            self.app.render()

    # -- layout
    def build(self):
        b = self.b
        sw = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        for key, text in S.ACT_SCOPES:
            ch = Choice(base=WHITE, text=text, bold=True)
            ch.set_selected(key == self.ui["act_scope"])
            ch.bind(on_release=lambda _w, k=key: self.set_scope(k))
            sw.add_widget(ch)
        b.add_widget(sw)
        b.add_widget(self.chips())

        slot = self.slot()
        if slot.store is None and not slot.busy and not slot.error:
            self.start()
        if slot.busy and slot.store is None:
            b.add_widget(Card(S.ACT_LOADING))
            return
        if slot.error and slot.store is None:
            b.add_widget(Card(S.ACT_ERROR.format(error=escape_markup(slot.error))))
            retry = Choice(base=BLUE, fg=WHITE, text=S.BTN_RETRY, bold=True,
                           size_hint_y=None, height=dp(48))
            retry.bind(on_release=lambda *_: self.retry())
            b.add_widget(retry)
            return
        st = slot.store
        self.notes(st, slot)
        rows = [r for r in st.rows() if matches(r, self.ui["act_filter"])]
        if not rows:
            b.add_widget(Card(S.ACT_EMPTY))
        for r in rows:
            r["me"] = self.me
            b.add_widget(self.row(r))
            if self.ui.get("act_sel") == r["tx"]:
                b.add_widget(self.detail(r))
        if not st.complete:
            more = Choice(base=BLACK, fg=WHITE, text=S.ACT_LOADING if slot.busy else S.ACT_LOAD_OLDER,
                          bold=True, size_hint_y=None, height=dp(48))
            more.bind(on_release=lambda *_: self.start(older=True))
            b.add_widget(more)

    def chips(self):
        sv = ScrollView(size_hint_y=None, height=dp(48), do_scroll_y=False, bar_width=0)
        row = BoxLayout(size_hint=(None, 1), spacing=dp(8))
        row.bind(minimum_width=row.setter("width"))
        for key, text in S.ACT_FILTERS:
            ch = Choice(base=WHITE, text=text, font_size="13sp", bold=True, size_hint_x=None,
                        width=dp(24 + 9 * len(text)))
            ch.set_selected(key == self.ui["act_filter"])
            ch.bind(on_release=lambda _w, k=key: self.set_filter(k))
            row.add_widget(ch)
        sv.add_widget(row)
        return sv

    def notes(self, st, slot):
        b = self.b
        if not st.exact:
            b.add_widget(Card(S.ACT_NO_KEY))
        if slot.error:
            b.add_widget(Card(S.ACT_ERROR.format(error=escape_markup(slot.error))))
        if st.note:
            b.add_widget(Card(S.ACT_TX_NOTE.format(error=escape_markup(st.note))))
        if st.truncated:
            b.add_widget(Card(S.ACT_TRUNCATED))
        b.add_widget(label(S.ACT_COMPLETE if st.complete else S.ACT_WINDOW.format(
            lo=st.lo or 0, hi=st.latest), size_hint_y=None, height=dp(20), font_size="12sp"))

    def row(self, r):
        icon, col = S.ACT_ICONS.get(r["kind"], ("?", BLACK))
        c = Tappable(padding=dp(10), spacing=dp(10), size_hint_y=None, height=dp(72))
        c.set_selected(self.ui.get("act_sel") == r["tx"])
        c.bind(on_release=lambda *_: self.select(r["tx"]))
        c.add_widget(Dot(bg=col, text=icon, color=WHITE, pos_hint={"center_y": 0.5}))
        mid = BoxLayout(orientation="vertical")
        mid.add_widget(label(f"[b]{escape_markup(row_title(r))}[/b]", font_size="15sp"))
        mid.add_widget(label(escape_markup(row_sub(r)), font_size="12sp"))
        c.add_widget(mid)
        amt, acol = row_amount(r)
        if amt:
            c.add_widget(label(f"[b]{amt}[/b]", color=acol, halign="right", size_hint_x=None,
                               width=dp(86), font_size="15sp"))
        return c

    def detail(self, r):
        p = Panel(orientation="vertical", size_hint_y=None, height=dp(250), spacing=dp(6))
        p.add_widget(label(f"[size=12sp]{S.ACT_DETAIL_TX}[/size]\n[b]{short(r['tx'])}[/b]",
                           size_hint_y=None, height=dp(40)))
        p.add_widget(label(f"[size=12sp]{S.ACT_DETAIL_FROM}[/size] {short(r['frm']) or '-'}   "
                           f"[size=12sp]{S.ACT_DETAIL_TO}[/size] {short(r['to']) or '-'}",
                           size_hint_y=None, height=dp(24), font_size="13sp"))
        p.add_widget(label(S.ACT_DETAIL_BLOCK.format(block=r["block"]), size_hint_y=None,
                           height=dp(20), font_size="12sp"))
        self.msg = label("", size_hint_y=None, height=dp(20), font_size="12sp", color=RED)
        p.add_widget(self.msg)
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        cp = Button(text=S.BTN_COPY, size_hint_x=0.4, background_normal="", background_down="",
                    background_color=BLUE, color=WHITE, bold=True)
        cp.bind(on_release=lambda *_: self.copy(r["tx"]))
        op = Button(text=S.ACT_BTN_ETHERSCAN, background_normal="", background_down="",
                    background_color=BLUE, color=WHITE, bold=True)
        op.bind(on_release=lambda *_: self.open(ETHERSCAN_TX + r["tx"]))
        btns.add_widget(cp)
        btns.add_widget(op)
        p.add_widget(btns)
        if r["offer_id"] is not None:
            go = Button(text=S.ACT_BTN_OFFER.format(id=r["offer_id"]), size_hint_y=None,
                        height=dp(44), background_normal="", background_down="",
                        background_color=BLACK, color=WHITE, bold=True)
            go.bind(on_release=lambda *_: self.app.go_offer(r["offer_id"]))
            p.add_widget(go)
        else:
            p.height = dp(200)
        return p

    # -- actions
    def set_scope(self, k):
        self.ui["act_scope"] = k
        self.ui["act_sel"] = None
        self.app.render()

    def set_filter(self, k):
        self.ui["act_filter"] = k
        self.app.render()

    def select(self, tx):
        self.ui["act_sel"] = None if self.ui.get("act_sel") == tx else tx
        self.app.render()

    def retry(self):
        self.slot().error = ""
        self.app.render()

    def copy(self, tx):
        self.msg.text = S.ACT_COPIED if util.copy_text(tx) else S.TX_COPY_FAILED

    def open(self, url):
        if not util.open_url(url):
            self.msg.text = S.SETTINGS_OPEN_FAILED


def build(app, b, d):
    ActivityPage(app, b, d).build()
