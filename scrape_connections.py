"""
Scrape NYT Connections puzzle data from connections-hints.com.

Usage:
    # Scrape only puzzles newer than what's already in the CSV:
    python scrape_connections.py

    # Scrape all puzzles (full re-scrape):
    python scrape_connections.py --all

    # Scrape a specific date range:
    python scrape_connections.py --from 2025-12-16 --to 2026-03-01

    # Dry run: print without writing to CSV
    python scrape_connections.py --dry-run

Output appended to: environments/connections/connections_data.csv
"""

import argparse
import csv
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://connections-hints.com"
CSV_PATH = Path(__file__).parent / "environments" / "connections" / "connections_data.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
RATE_LIMIT_SEC = 0.5  # seconds between requests

COLOR_TO_LEVEL = {
    "yellow": 0,
    "green": 1,
    "blue": 2,
    "purple": 3,
}


def get_all_archive_dates() -> list[str]:
    """Fetch /archive and return all puzzle dates (YYYY-MM-DD) sorted ascending."""
    r = requests.get(f"{BASE_URL}/archive", headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    links = soup.find_all("a", href=lambda h: h and h.startswith("/hints/"))
    dates = sorted(set(a["href"].strip("/").split("/")[-1] for a in links))
    return dates


def get_existing_dates() -> set[str]:
    """Read the existing CSV and return the set of puzzle dates already present."""
    if not CSV_PATH.exists():
        return set()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["Puzzle Date"] for row in reader}


def get_max_game_id() -> int:
    """Return the highest Game ID currently in the CSV."""
    if not CSV_PATH.exists():
        return 0
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ids = [int(row["Game ID"]) for row in reader if row["Game ID"].isdigit()]
    return max(ids) if ids else 0


def parse_puzzle(date: str) -> list[dict] | None:
    """
    Fetch and parse a single puzzle page.
    Returns a list of row dicts or None on failure.
    """
    url = f"{BASE_URL}/hints/{date}/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # --- Game ID from page title e.g. "... (#943)" ---
    game_id = None
    title_el = soup.find("title")
    if title_el:
        m = re.search(r"\(#(\d+)\)", title_el.string or "")
        if m:
            game_id = int(m.group(1))

    # --- Word grid: 16 words in display order (row/col position) ---
    word_grid_el = soup.find(id="wordGrid")
    if not word_grid_el:
        print(f"  WARNING: No wordGrid found for {date}")
        return None

    grid_words = []
    for span in word_grid_el.find_all("span", class_=lambda c: c and "font-medium" in c):
        word = span.get_text(strip=True)
        if word:
            grid_words.append(word)

    if len(grid_words) != 16:
        print(f"  WARNING: Expected 16 words, got {len(grid_words)} for {date}")
        return None

    # Build position lookup: word -> (row, col) based on grid order
    word_position: dict[str, tuple[int, int]] = {}
    for i, w in enumerate(grid_words):
        row = (i // 4) + 1
        col = (i % 4) + 1
        word_position[w] = (row, col)

    # --- Categories section: determine color -> level for each hint id ---
    cats_el = soup.find(id="categories")
    if not cats_el:
        print(f"  WARNING: No categories section for {date}")
        return None

    # Each <a href="#hint-N"> has a color class like bg-yellow-50
    hint_level: dict[str, int] = {}  # hint id (e.g. "hint-1") -> level
    for a in cats_el.find_all("a", href=lambda h: h and h.startswith("#hint-")):
        hint_id = a["href"].lstrip("#")
        cls = " ".join(a.get("class", []))
        level = None
        for color, lvl in COLOR_TO_LEVEL.items():
            if f"bg-{color}-" in cls:
                level = lvl
                break
        if level is not None:
            hint_level[hint_id] = level

    # --- Hint sections: extract group name + words ---
    rows = []
    for hint_id, level in hint_level.items():
        hint_el = soup.find(id=hint_id)
        if not hint_el:
            continue

        # Group name is in the <h3> inside the header bar
        h3 = hint_el.find("h3")
        group_name = h3.get_text(strip=True) if h3 else ""

        # Words: each word card has a div with classes font-medium text-gray-900 mb-1
        word_divs = hint_el.find_all(
            "div",
            class_=lambda c: c and "font-medium" in c and "text-gray-900" in c and "mb-1" in c,
        )
        for wd in word_divs:
            word = wd.get_text(strip=True)
            pos = word_position.get(word, (0, 0))
            rows.append(
                {
                    "game_id": game_id,
                    "date": date,
                    "word": word,
                    "group_name": group_name,
                    "level": level,
                    "row": pos[0],
                    "col": pos[1],
                }
            )

    if len(rows) != 16:
        print(f"  WARNING: Expected 16 word-rows, got {len(rows)} for {date}")
        return None

    return rows


def write_rows(rows: list[dict], game_id_offset: int = 0) -> None:
    """Append rows to the CSV file."""
    file_exists = CSV_PATH.exists()
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(
                ["Game ID", "Puzzle Date", "Word", "Group Name", "Group Level", "Starting Row", "Starting Column"]
            )
        for r in rows:
            gid = r["game_id"] if r["game_id"] is not None else game_id_offset
            writer.writerow([gid, r["date"], r["word"], r["group_name"], r["level"], r["row"], r["col"]])


def main():
    parser = argparse.ArgumentParser(description="Scrape connections-hints.com puzzle data")
    parser.add_argument("--all", action="store_true", help="Re-scrape all puzzles (ignore existing CSV)")
    parser.add_argument("--from", dest="from_date", default=None, help="Start date (YYYY-MM-DD, inclusive)")
    parser.add_argument("--to", dest="to_date", default=None, help="End date (YYYY-MM-DD, inclusive)")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing to CSV")
    args = parser.parse_args()

    print("Fetching archive index...")
    all_dates = get_all_archive_dates()
    print(f"Found {len(all_dates)} puzzles on archive ({all_dates[0]} → {all_dates[-1]})")

    existing_dates = set() if args.all else get_existing_dates()
    if existing_dates:
        print(f"Existing CSV has {len(existing_dates)} puzzle dates, skipping those.")

    # Filter dates
    target_dates = [
        d for d in all_dates
        if d not in existing_dates
        and (args.from_date is None or d >= args.from_date)
        and (args.to_date is None or d <= args.to_date)
    ]

    if not target_dates:
        print("Nothing new to scrape.")
        return

    print(f"Will scrape {len(target_dates)} puzzles: {target_dates[0]} → {target_dates[-1]}")

    max_game_id = get_max_game_id()
    total_written = 0

    for i, date in enumerate(target_dates, 1):
        print(f"[{i}/{len(target_dates)}] Scraping {date}...", end=" ")
        rows = parse_puzzle(date)

        if rows is None:
            print("SKIPPED")
            time.sleep(RATE_LIMIT_SEC)
            continue

        # Fill in game_id if missing (site doesn't always embed it)
        if rows[0]["game_id"] is None:
            max_game_id += 1
            for r in rows:
                r["game_id"] = max_game_id
        else:
            max_game_id = max(max_game_id, rows[0]["game_id"])

        if args.dry_run:
            for r in rows:
                print(f"\n  {r}")
        else:
            write_rows(rows)
            total_written += len(rows)

        print(f"OK (game_id={rows[0]['game_id']}, {len(rows)} rows)")
        time.sleep(RATE_LIMIT_SEC)

    if not args.dry_run:
        print(f"\nDone. Wrote {total_written} rows to {CSV_PATH}")
    else:
        print(f"\nDry run complete. Would have written {len(target_dates) * 16} rows.")


if __name__ == "__main__":
    main()
