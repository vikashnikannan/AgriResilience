"""Runs every dashboard section in Streamlit's own test runner (AppTest) for several reporting periods and
fails on any exception. Checks the data logic and page code, not visual appearance."""
import sys
from pathlib import Path
import logging; logging.disable(logging.WARNING)
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app" / "app.py")
PAGES = ["Overview", "Climate Hazard", "Crop Condition", "Integrated Assessment", "Adaptation Options", "Methodology and Data"]
fails = 0
for page in PAGES:
    for idx in (0, 1, 4, 12, 25):
        at = AppTest.from_file(APP, default_timeout=90)
        at.run()
        if at.exception:
            fails += 1; print("FAIL (initial run)", [e.value for e in at.exception]); break
        n = len(at.sidebar.selectbox[0].options)
        if idx >= n:
            continue
        at.sidebar.radio[0].set_value(page)
        at.sidebar.selectbox[0].select_index(idx)
        at.run()
        if at.exception:
            fails += 1; print("FAIL", page, "period index", idx, [e.value for e in at.exception][:2])
            break
    else:
        print("ok", page)
print("fails", fails)
sys.exit(1 if fails else 0)
