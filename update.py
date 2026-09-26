#!/usr/bin/env python3
"""Pull Portland, ME's latest WastewaterSCAN SARS-CoV-2 reading and bake it into
the page.

The number is the same one the WastewaterSCAN dashboard plots as its trend line:
N Gene copies / PMMoV copies, 5-sample trimmed average, x 1,000,000.

Usage: python3 update.py   (rewrites the data block in site/index.html, plus
                            portland-covid.html when that local copy exists)
"""
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PLANT_URL = "https://storage.googleapis.com/wastewater-dev-data/json/8bed9020.json"
HERE = Path(__file__).parent
PAGES = [HERE / "site" / "index.html", HERE / "portland-covid.html"]
HISTORY_DAYS = 180
SCALE = 1_000_000  # dashboard shows "PMMoV Normalized (x1 million)"


def main() -> int:
    req = urllib.request.Request(PLANT_URL, headers={"User-Agent": "portland-covid-tracker"})
    with urllib.request.urlopen(req, timeout=60) as r:
        plant = json.load(r)

    points = []
    for s in plant["samples"]:
        n = (s.get("targets") or {}).get("N Gene") or {}
        trend = n.get("gc_g_dry_weight_trimmed5_pmmov")
        if trend is None:
            continue
        single = n.get("gc_g_dry_weight_pmmov")
        points.append({
            "date": s["collection_date"],
            "trend": round(trend * SCALE, 2),
            "sample": None if single is None else round(single * SCALE, 2),
            "level": n.get("activity_category"),
        })
    if not points:
        print("No N Gene readings found in plant data", file=sys.stderr)
        return 1

    points.sort(key=lambda p: p["date"])
    latest = points[-1]
    cutoff = (date.fromisoformat(latest["date"]) - timedelta(days=HISTORY_DAYS)).isoformat()

    data = {
        "latest": latest,
        "history": [[p["date"], p["trend"]] for p in points if p["date"] >= cutoff],
        "sourceUpdated": plant.get("updated"),
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    block = re.compile(r'(<script id="ww-data" type="application/json">)(.*?)(</script>)', re.S)
    blob = json.dumps(data, separators=(",", ":"))
    written = []
    for page in PAGES:
        if not page.exists():
            continue
        html = page.read_text()
        if not block.search(html):
            print(f"Data block not found in {page.relative_to(HERE)}", file=sys.stderr)
            return 1
        page.write_text(block.sub(lambda m: m.group(1) + blob + m.group(3), html, count=1))
        written.append(str(page.relative_to(HERE)))
    if not written:
        print("No page found to update", file=sys.stderr)
        return 1

    print(f"Portland, ME {latest['date']}: {latest['trend']} ({latest['level']}); "
          f"{len(data['history'])} points written to {', '.join(written)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
