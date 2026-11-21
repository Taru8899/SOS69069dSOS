import os
import sys
from pathlib import Path

from dotenv import load_dotenv

frozen = getattr(sys, "frozen", False)
base = Path(sys._MEIPASS) if frozen else Path(__file__).parent
exe_dir = Path(sys.executable).parent if frozen else base

load_dotenv(exe_dir / ".env")  # your key stays next to the app, never inside it
os.chdir(base)

from streamlit.web import cli as stcli  # noqa: E402

sys.argv = [
    "streamlit", "run", str(base / "app.py"),
    "--global.developmentMode=false",
    "--server.headless=false",
]
sys.exit(stcli.main())
