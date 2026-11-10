"""Clipboard and browser helpers for Android, with safe fallbacks."""
import threading


def paste_text():
    """Text from the phone clipboard, or '' if it can't be read."""
    # 1) direct Android API (most reliable)
    try:
        from android.runnable import run_on_ui_thread
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        context = autoclass("android.content.Context")
        out, done = [], threading.Event()

        @run_on_ui_thread
        def grab():
            try:
                cm = activity.getSystemService(context.CLIPBOARD_SERVICE)
                clip = cm.getPrimaryClip()
                if clip is not None and clip.getItemCount() > 0:
                    out.append(str(clip.getItemAt(0).coerceToText(activity).toString()))
            except Exception:  # noqa: BLE001
                pass
            done.set()

        grab()
        done.wait(2)
        if out and out[0]:
            return out[0].strip()
    except Exception:  # noqa: BLE001
        pass
    # 2) Kivy's own clipboard
    try:
        from kivy.core.clipboard import Clipboard
        return (Clipboard.paste() or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def copy_text(text):
    """Copy text to the phone clipboard. Returns True if it probably worked."""
    try:
        from android.runnable import run_on_ui_thread
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        context = autoclass("android.content.Context")
        clipdata = autoclass("android.content.ClipData")
        done = threading.Event()

        @run_on_ui_thread
        def put():
            try:
                cm = activity.getSystemService(context.CLIPBOARD_SERVICE)
                cm.setPrimaryClip(clipdata.newPlainText("dSOS", text))
            except Exception:  # noqa: BLE001
                pass
            done.set()

        put()
        done.wait(2)
        return True
    except Exception:  # noqa: BLE001
        pass
    try:
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(text)
        return True
    except Exception:  # noqa: BLE001
        return False


def open_url(url):
    try:
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        intent = autoclass("android.content.Intent")
        uri = autoclass("android.net.Uri")
        activity.startActivity(intent(intent.ACTION_VIEW, uri.parse(url)))
        return True
    except Exception:  # noqa: BLE001
        try:
            import webbrowser
            return bool(webbrowser.open(url))
        except Exception:  # noqa: BLE001
            return False
