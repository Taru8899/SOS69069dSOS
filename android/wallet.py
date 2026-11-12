"""Wallet link: pairs with a wallet app over WalletConnect and asks it to sign and send.

The app never sees a private key. The WalletConnect client is JavaScript (wc_bundle.js, built by
CI from the wc/ folder) running in a hidden Android WebView. This file only starts that WebView,
polls its message queue and opens the wallet app when an approval is needed."""
import json
import os
import time

from kivy.clock import Clock

import strings as S
import util
from theme import WC_APP_URL, WC_ORIGIN, WC_PROJECT_ID, WC_RPC

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.join(HERE, "wc_bundle.js")
BOOT_TIMEOUT = 25            # seconds until the hidden page must have started
POLL_SECONDS = 0.4

_CB_CLASS = None


def _value_callback(fn):
    """Java ValueCallback<String> that calls fn(value). Needs pyjnius (Android only)."""
    global _CB_CLASS
    if _CB_CLASS is None:
        from jnius import PythonJavaClass, java_method

        class _CB(PythonJavaClass):
            __javainterfaces__ = ["android/webkit/ValueCallback"]
            __javacontext__ = "app"

            def __init__(self, f):
                super().__init__()
                self.f = f

            @java_method("(Ljava/lang/Object;)V")
            def onReceiveValue(self, value):
                try:
                    self.f(value)
                except Exception:  # noqa: BLE001
                    pass
        _CB_CLASS = _CB
    return _CB_CLASS(fn)


class Wallet:
    def __init__(self, app):
        self.app = app
        self.booted = False
        self.fatal = ""
        self.connected = False
        self.accounts = []
        self.name = ""
        self.native = ""
        self.universal = ""
        self.listener = None            # fn(text): progress notes from the link
        self._webview = None
        self._poll_ev = None
        self._cbs = {}                  # request id -> (on_ok, on_err)
        self._connect_cbs = []
        self._connecting = False
        self._connect_sent = False
        self._started_at = 0.0
        self._next = 1
        self._keep = []

    # ------------------------------------------------------------ capability
    def unavailable(self):
        """'' when the wallet link can run, else the text to show."""
        if not WC_PROJECT_ID:
            return S.TX_WC_NO_PROJECT
        try:
            import jnius  # noqa: F401
        except Exception:  # noqa: BLE001
            return S.TX_WALLET_UNAVAILABLE
        if not os.path.exists(BUNDLE):
            return S.TX_WALLET_UNAVAILABLE
        return ""

    def label(self):
        return self.name or S.TX_PEER_DEFAULT

    def set_listener(self, fn):
        self.listener = fn

    def _note(self, text):
        if self.listener:
            try:
                self.listener(text)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------ public calls
    def connect(self, on_ok, on_err):
        """Make sure a wallet session exists. on_ok() / on_err(text)."""
        why = self.unavailable()
        if why:
            on_err(why)
            return
        if self.connected:
            on_ok()
            return
        self._connect_cbs.append((on_ok, on_err))
        if self._connecting:
            return
        self._connecting = True
        self._connect_sent = False
        self._started_at = time.time()
        self._start()

    def request(self, method, params, on_ok, on_err):
        """Ask the wallet to run an RPC method. on_ok(result) / on_err(text, code)."""
        if not self.connected:
            on_err("not connected", None)
            return
        rid = self._next
        self._next += 1
        self._cbs[rid] = (on_ok, on_err)
        # json.dumps twice: the JS side receives the params as one JSON string
        self._js("window.DsosWC.request(%d,%s,%s)" % (
            rid, json.dumps(method), json.dumps(json.dumps(params))))
        Clock.schedule_once(lambda dt: self.open_wallet(), 0.6)

    def open_wallet(self):
        """Bring the wallet app forward so the person can approve."""
        target = self.native or self.universal
        if target and util.open_url(target):
            return
        self._note(S.TX_OPEN_WALLET.format(wallet=self.label()))

    def disconnect(self):
        self._js("window.DsosWC && window.DsosWC.disconnect()")
        self._set_disconnected()

    def on_resume(self):
        """The app came back from the wallet: wake the relay connection if it slept."""
        self._js("window.DsosWC && window.DsosWC.resume()")

    # ------------------------------------------------------------ hidden WebView (Android)
    def _html(self):
        with open(BUNDLE, encoding="utf-8") as f:
            js = f.read().replace("</script", "<\\/script")
        cfg = json.dumps({
            "projectId": WC_PROJECT_ID, "name": S.WC_APP_NAME, "description": S.WC_APP_DESC,
            "url": WC_APP_URL, "icons": [], "rpc": WC_RPC,
        }).replace("</", "<\\/")
        return ("<!doctype html><html><head><meta charset='utf-8'></head><body>"
                "<script>window.__CFG=" + cfg + ";</script><script>" + js + "</script></body></html>")

    def _start(self):
        if self._webview is not None or self._poll_ev is not None:
            return
        try:
            from android.runnable import run_on_ui_thread
            from jnius import autoclass
            html = self._html()
        except Exception as e:  # noqa: BLE001
            self.fatal = str(e)
            self._fail_connect(S.TX_WC_NOT_READY.format(error=self.fatal))
            return

        @run_on_ui_thread
        def make():
            try:
                activity = autoclass("org.kivy.android.PythonActivity").mActivity
                webview = autoclass("android.webkit.WebView")
                params = autoclass("android.view.ViewGroup$LayoutParams")
                wv = webview(activity)
                st = wv.getSettings()
                st.setJavaScriptEnabled(True)
                st.setDomStorageEnabled(True)
                wv.setAlpha(0.0)
                activity.addContentView(wv, params(1, 1))
                wv.loadDataWithBaseURL(WC_ORIGIN, html, "text/html", "utf-8", None)
                self._webview = wv
            except Exception as e:  # noqa: BLE001
                self.fatal = str(e)

        make()
        self._poll_ev = Clock.schedule_interval(self._poll, POLL_SECONDS)

    def _js(self, code, cb=None):
        wv = self._webview
        if wv is None:
            return
        try:
            from android.runnable import run_on_ui_thread
            cbo = None
            if cb is not None:
                cbo = _value_callback(cb)
                self._keep = (self._keep + [cbo])[-8:]    # keep the Java callback alive

            @run_on_ui_thread
            def go():
                try:
                    wv.evaluateJavascript(code, cbo)
                except Exception:  # noqa: BLE001
                    pass
            go()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ polling
    def _poll(self, dt):
        if self._connecting and not self.booted:
            if self.fatal or time.time() - self._started_at > BOOT_TIMEOUT:
                self._fail_connect(S.TX_WC_NOT_READY.format(error=self.fatal or "timeout"))
                return
        if self._webview is None:
            return
        if self._connecting and self.booted and not self._connect_sent:
            self._connect_sent = True
            self._js("window.DsosWC.connect()")
        self._js("window.DsosWC ? window.DsosWC.drain() : []", self._on_drain)

    def _on_drain(self, value):
        # called on a Java thread: hand over to the Kivy thread
        Clock.schedule_once(lambda dt: self.handle(value), 0)

    def handle(self, value):
        """Process the JSON text of the message list returned by drain()."""
        try:
            msgs = json.loads(value) if value else []
        except Exception:  # noqa: BLE001
            return
        if not isinstance(msgs, list):
            return
        for m in msgs:
            if isinstance(m, dict):
                self._one(m)

    def _one(self, m):
        t = m.get("t")
        if t == "boot":
            self.booted = True
        elif t == "uri":
            if not util.open_url(m.get("uri", "")):
                util.copy_text(m.get("uri", ""))
                self._note(S.TX_CONNECT_PASTE)
        elif t == "session":
            self.accounts = list(m.get("accounts") or [])
            self.name = m.get("wallet") or ""
            self.native = m.get("native") or ""
            self.universal = m.get("universal") or ""
            self.connected = bool(self.accounts)
            self._connecting = False
            cbs, self._connect_cbs = self._connect_cbs, []
            for ok, err in cbs:
                (ok() if self.connected else err(S.TX_ERROR.format(error="no account")))
        elif t == "accounts":
            self.accounts = list(m.get("accounts") or [])
            self.connected = bool(self.accounts)
        elif t == "result":
            cb = self._cbs.pop(m.get("id"), None)
            if cb:
                cb[0](m.get("result"))
        elif t == "error":
            if m.get("id") == "connect":
                self._fail_connect(S.TX_ERROR.format(error=m.get("error") or "error"), m.get("code"))
            else:
                cb = self._cbs.pop(m.get("id"), None)
                if cb:
                    cb[1](m.get("error") or "error", m.get("code"))
        elif t == "disconnect":
            self._set_disconnected()
        elif t == "fatal":
            self.fatal = m.get("error") or "error"

    # ------------------------------------------------------------ helpers
    def _fail_connect(self, text, code=None):
        self._connecting = False
        if self._webview is None and self._poll_ev is not None:   # the WebView never came up: allow a retry
            self._poll_ev.cancel()
            self._poll_ev = None
        cbs, self._connect_cbs = self._connect_cbs, []
        for _ok, err in cbs:
            err(text, code)

    def _set_disconnected(self):
        self.connected = False
        self.accounts = []
        pend, self._cbs = self._cbs, {}
        for _ok, err in pend.values():
            err("disconnected", None)
