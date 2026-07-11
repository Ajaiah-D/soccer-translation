"""Direct FBref fetcher: a short-lived real-Chrome (Selenium) session renders each
league-season stats page, and the standard player table is parsed from the HTML.

Why a browser: fbref.com sits behind a bot-protection layer that requires JavaScript
execution; plain HTTP clients receive a challenge page regardless of fingerprint.
A rendered navigation to the stats URL passes. The session is short (one page per
league-season, politely spaced) and every page is cached locally afterward, so this
runs once per new slice.

Etiquette: requests are spaced by config ingest.fbref_page_delay_seconds (default 6s,
well under the site's published rate limits), and cached pages are never re-fetched.

Parsing note: FBref wraps stat tables in HTML comments; _uncomment() strips the
comment markers before pandas.read_html can see the table. Column names are flattened
to the same snake_case schema the previous scraper produced (playing_time_min,
performance_gls, ...), so the fbref_player_season contract is unchanged.
"""

from __future__ import annotations

import time
from io import StringIO

import pandas as pd

from src.common.config import load_leagues, load_settings
from src.common.logging import get_logger

log = get_logger("ingest.fbref_direct")

BASE = "https://fbref.com"


def season_url(canon: str, season: int) -> str:
    """Build the stats-page URL for a canonical league code and season start year."""
    spec = load_leagues()["leagues"][canon]
    comp, slug = spec["fbref_comp_id"], spec["fbref_slug"]
    if spec["fbref_season_style"] == "cross":
        code = f"{season}-{season + 1}"
    else:
        code = str(season)
    return f"{BASE}/en/comps/{comp}/{code}/stats/{code}-{slug}-Stats"


def _launch_chrome():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1200,900")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(90)
    return driver


class BrowserSession:
    """One polite browser session for a batch of page fetches. Use as a context
    manager; the browser launches lazily on the first fetch."""

    def __init__(self) -> None:
        self._driver = None
        self._first = True
        self._delay = float(load_settings()["ingest"].get("fbref_page_delay_seconds", 6.0))

    def __enter__(self) -> "BrowserSession":
        return self

    def __exit__(self, *exc) -> None:
        if self._driver is not None:
            self._driver.quit()

    def fetch(self, url: str) -> str | None:
        """Fetch one URL, returning the rendered HTML or None. The first page may
        present an interactive "verify you are human" checkbox; a single human click
        clears the whole session, so the first page waits much longer."""
        if self._driver is None:
            self._driver = _launch_chrome()
        wait_seconds = 180 if self._first else 25
        html = None
        for attempt in range(2):
            try:
                self._driver.get(url)
                for _ in range(wait_seconds):
                    page = self._driver.page_source
                    if "stats_standard" in page:
                        html = page
                        break
                    time.sleep(1)
                if html:
                    break
            except Exception as exc:  # noqa: BLE001 - per-page failure is recorded
                log.warning("browser fetch failed (%s attempt %d): %s",
                            url, attempt + 1, str(exc)[:120])
            time.sleep(self._delay)
        self._first = False
        log.info("fetched %s -> %s", url, f"{len(html)} bytes" if html else "FAILED")
        time.sleep(self._delay)
        return html


def fetch_pages(urls: list[str]) -> dict[str, str | None]:
    """Fetch each URL in one browser session. Returns url -> html (None on failure)."""
    results: dict[str, str | None] = {}
    if not urls:
        return results
    with BrowserSession() as session:
        for url in urls:
            results[url] = session.fetch(url)
    return results


def _uncomment(html: str) -> str:
    return html.replace("<!--", "").replace("-->", "")


def parse_standard_table(html: str) -> pd.DataFrame:
    """Parse the stats_standard table into the flat snake_case schema the
    fbref_player_season contract expects."""
    tables = pd.read_html(StringIO(_uncomment(html)), attrs={"id": "stats_standard"})
    df = tables[0]
    # flatten the two-row header
    cols = []
    for col in df.columns:
        if isinstance(col, tuple):
            top, bottom = (str(col[0]), str(col[1]))
            name = bottom if top.startswith("Unnamed") else f"{top}_{bottom}"
        else:
            name = str(col)
        cols.append(name.strip().lower().replace(" ", "_"))
    df.columns = cols
    # drop repeated in-table header rows and footer junk
    df = df[df["player"].notna() & (df["player"] != "Player")].copy()
    df = df.rename(columns={"squad": "team"})
    for drop in ("rk", "matches"):
        if drop in df.columns:
            df = df.drop(columns=drop)
    # numeric coercion for the columns downstream code reads
    for col in df.columns:
        if col not in ("player", "nation", "pos", "team"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # nation arrives as "us USA"; keep the uppercase code to match prior pulls
    if "nation" in df.columns:
        df["nation"] = df["nation"].astype(str).str.split().str[-1]
    df = df.reset_index(drop=True)
    # parquet-safe: stringify residual object columns
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str)
    return df
