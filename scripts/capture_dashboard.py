"""Scripted G7 dashboard capture (Phase 6, plan 06-02, D-09).

Boot the dashboard headless first, then run this::

    streamlit run dashboard/app.py --server.headless true --server.port 8501 &
    python scripts/capture_dashboard.py

Needs ad-hoc ``playwright`` + Chromium (NOT in requirements.txt)::

    pip install playwright
    playwright install chromium

Writes results/figures/fig_g7_dashboard.png (1600x900). Manual fallback is
documented in REPRODUCE.md (step 5).
"""

import pathlib

from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"
OUT = pathlib.Path("results/figures/fig_g7_dashboard.png")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1600, "height": 900})
    page.goto(URL)
    page.wait_for_timeout(5000)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT))
    browser.close()
print(f"wrote {OUT}")
