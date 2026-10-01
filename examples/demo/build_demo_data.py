#!/usr/bin/env python3
"""Build the Datalens cricket demo dataset from Cricsheet IPL data.

Downloads (or reuses a cached copy of) Cricsheet's IPL ball-by-ball JSON and
player register, normalises them into five related entities, and writes two
snapshots as gzipped JSONL:

    <out>/day1/{matches,deliveries,players,teams,venues}.jsonl.gz
    <out>/day2/{matches,deliveries,players,teams,venues}.jsonl.gz
    <out>/daily/<match date>/{matches,deliveries}.jsonl.gz   (rolling-baseline demo)

day1 holds every match from --from-season up to the second-to-last match day.
day2 is a re-export one match day later, produced by a "changed" upstream
pipeline with deliberate schema and data drift injected (see INJECTED_CHANGES),
so Datalens can be scored on what it detects.

Data: Cricsheet (https://cricsheet.org), Open Data Commons Attribution License
(ODC-BY 1.0). See test_data/cricket/ATTRIBUTION.md.

Stdlib only:
    python examples/demo/build_demo_data.py --out test_data/cricket
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import random
import re
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

IPL_ZIP_URL = "https://cricsheet.org/downloads/ipl_json.zip"
REGISTER_URL = "https://cricsheet.org/register/people.csv"

INJECTED_CHANGES = [
    ("rename", "deliveries.runs.extras -> deliveries.runs.extra_runs", "schema drift: field removed + added"),
    ("type", "deliveries.over int -> string in 5% of rows", "type drift"),
    ("add_field", "deliveries.ball_speed_kph (~90% null)", "added field, low completeness"),
    ("drop_field", "matches.toss.decision removed", "removed nested field"),
    ("nulls", "deliveries.non_striker_id null in 30% of rows", "null-rate / coverage drift"),
    ("distribution", "deliveries.runs.batter: 20% of dot/single balls become 4/6", "distribution drift"),
    ("category", "new wicket kind 'timed out' + new venue 'Demo Park, Pune'", "new category values"),
    ("volume", "40% of deliveries rows dropped (truncated feed)", "row-count drift"),
    ("pii", "players.contact_email (synthetic, neutral-ish name)", "PII detection + masking"),
    ("orphans", "2% of deliveries.bowler_id point to unknown players", "referential-integrity drift"),
    ("nulls", "matches.city blank in 25% of matches", "coverage drift in a second object"),
    ("coverage_up", "matches.attendance filled for 63.2% of matches (day 1: 40%) — +58%", "coverage increase above the 50% rule"),
    ("coverage_up", "deliveries.shot_type filled for 56% of deliveries (day 1: 50%) — +12%", "coverage increase within the rule"),
]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def fetch(url: str, cache: Path) -> bytes:
    target = cache / url.rsplit("/", 1)[-1]
    if not target.exists():
        print(f"Downloading {url}")
        cache.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as resp:
            target.write_bytes(resp.read())
    return target.read_bytes()


def season_start(season: Any) -> int:
    """Cricsheet seasons are ints (2019) or strings ('2020/21')."""
    return int(str(season)[:4])


def load_matches(zip_bytes: bytes, from_season: int) -> list[dict[str, Any]]:
    matches = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            match = json.loads(zf.read(name))
            if season_start(match["info"]["season"]) >= from_season:
                match["_id"] = Path(name).stem
                matches.append(match)
    matches.sort(key=lambda m: (m["info"]["dates"][0], m["_id"]))
    return matches


def load_register(csv_bytes: bytes) -> dict[str, dict[str, str]]:
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
    return {row["identifier"]: row for row in reader}


# Optional enrichment fields present on a share of rows; day 2 fills more of them.
# Presence is decided by a hash of the row id, so a row filled on day 1 stays filled.
DAY1_FILL = {"shot_type": 0.50, "attendance": 0.40}
DAY2_FILL = {"shot_type": 0.56, "attendance": 0.632}
SHOT_TYPES = ["defended", "drive", "cut", "pull", "sweep", "flick", "glance", "lofted"]


def _unit(key: str) -> float:
    """Stable pseudo-random number in [0, 1) from a string."""
    import hashlib

    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16) / 0x100000000


def build_entities(
    matches: list[dict[str, Any]], register: dict[str, dict[str, str]], fill: dict[str, float] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Normalise Cricsheet match files into matches/deliveries/players/teams/venues."""
    fill = fill or DAY1_FILL
    match_rows, delivery_rows = [], []
    teams: dict[str, dict[str, Any]] = {}
    venues: dict[str, dict[str, Any]] = {}
    players: dict[str, dict[str, Any]] = {}

    for m in matches:
        info = m["info"]
        people = info.get("registry", {}).get("people", {})
        pid = people.get  # name -> registry id
        season = info["season"]
        date = info["dates"][0]
        venue_id = slug(info.get("venue", "unknown"))
        team_ids = [slug(t) for t in info["teams"]]

        venue = venues.setdefault(
            venue_id, {"venue_id": venue_id, "name": info.get("venue"), "city": info.get("city"), "matches": 0}
        )
        venue["matches"] += 1
        for team_name, team_id in zip(info["teams"], team_ids):
            team = teams.setdefault(
                team_id,
                {"team_id": team_id, "name": team_name, "first_season": season, "last_season": season, "matches": 0},
            )
            team["last_season"] = season
            team["matches"] += 1
            for player_name in info.get("players", {}).get(team_name, []):
                player_id = pid(player_name)
                if not player_id:
                    continue
                reg = register.get(player_id, {})
                player = players.setdefault(
                    player_id,
                    {
                        "player_id": player_id,
                        "name": reg.get("name", player_name),
                        "unique_name": reg.get("unique_name", player_name),
                        "key_cricinfo": reg.get("key_cricinfo") or None,
                        "team_ids": [],
                        "first_season": season,
                        "last_season": season,
                        "matches_played": 0,
                    },
                )
                if team_id not in player["team_ids"]:
                    player["team_ids"].append(team_id)
                player["last_season"] = season
                player["matches_played"] += 1

        outcome = info.get("outcome", {})
        event = info.get("event", {})
        match_rows.append(
            {
                "match_id": m["_id"],
                "season": season,
                "date": date,
                "match_number": event.get("match_number"),
                "stage": event.get("stage"),
                "city": info.get("city"),
                "venue_id": venue_id,
                "team1_id": team_ids[0],
                "team2_id": team_ids[1],
                "toss": {
                    "winner_id": slug(info["toss"]["winner"]),
                    "decision": info["toss"]["decision"],
                },
                "outcome": {
                    "winner_id": slug(outcome["winner"]) if "winner" in outcome else None,
                    "result": outcome.get("result"),
                    "method": outcome.get("method"),
                    "by": outcome.get("by"),
                },
                "player_of_match_id": pid(info["player_of_match"][0]) if info.get("player_of_match") else None,
                "umpire_ids": [pid(u) for u in info.get("officials", {}).get("umpires", [])],
            }
        )
        if _unit("att" + m["_id"]) < fill["attendance"]:
            match_rows[-1]["attendance"] = 15_000 + int(_unit("attv" + m["_id"]) * 45_000)

        for innings_no, innings in enumerate(m["innings"], start=1):
            batting_team_id = slug(innings["team"])
            for over in innings["overs"]:
                for ball_no, d in enumerate(over["deliveries"], start=1):
                    row: dict[str, Any] = {
                        "delivery_id": f"{m['_id']}-{innings_no}-{over['over']}-{ball_no}",
                        "match_id": m["_id"],
                        "date": date,
                        "innings": innings_no,
                        "batting_team_id": batting_team_id,
                        "over": over["over"],
                        "ball": ball_no,
                        "batter_id": pid(d["batter"]),
                        "bowler_id": pid(d["bowler"]),
                        "non_striker_id": pid(d["non_striker"]),
                        "runs": dict(d["runs"]),
                    }
                    if _unit("shot" + row["delivery_id"]) < fill["shot_type"]:
                        row["shot_type"] = SHOT_TYPES[int(_unit("shotv" + row["delivery_id"]) * len(SHOT_TYPES))]
                    if "extras" in d:
                        row["extras"] = d["extras"]
                    if "wickets" in d:
                        row["wickets"] = [
                            {
                                "kind": w["kind"],
                                "player_out_id": pid(w["player_out"]),
                                "fielder_ids": [pid(f["name"]) for f in w.get("fielders", []) if "name" in f],
                            }
                            for w in d["wickets"]
                        ]
                    delivery_rows.append(row)

    return {
        "matches": match_rows,
        "deliveries": delivery_rows,
        "players": sorted(players.values(), key=lambda p: p["player_id"]),
        "teams": sorted(teams.values(), key=lambda t: t["team_id"]),
        "venues": sorted(venues.values(), key=lambda v: v["venue_id"]),
    }


def inject_drift(entities: dict[str, list[dict[str, Any]]], new_match_ids: set[str], rng: random.Random) -> None:
    """Apply INJECTED_CHANGES in place to a day-2 export."""
    # New venue for the newly added match day.
    new_venue_id = slug("Demo Park, Pune")
    entities["venues"].append({"venue_id": new_venue_id, "name": "Demo Park", "city": "Pune", "matches": 0})
    # Own seeded stream, so adding this change doesn't shift the other injections.
    city_rng = random.Random(1_000)
    for match in entities["matches"]:
        match["toss"].pop("decision", None)
        if city_rng.random() < 0.25:
            match["city"] = None  # venue feed stopped sending the city for some matches
        if match["match_id"] in new_match_ids:
            match["venue_id"] = new_venue_id
            entities["venues"][-1]["matches"] += 1

    kept = []
    timed_out_budget = 3
    for row in entities["deliveries"]:
        if rng.random() < 0.40:
            continue
        runs = row["runs"]
        runs["extra_runs"] = runs.pop("extras")
        if runs["batter"] in (0, 1) and rng.random() < 0.20:
            runs["batter"] = rng.choice((4, 6))
            runs["total"] = runs["batter"] + runs["extra_runs"]
        if rng.random() < 0.05:
            row["over"] = str(row["over"])
        row["ball_speed_kph"] = round(rng.uniform(110, 150), 1) if rng.random() < 0.10 else None
        if rng.random() < 0.30:
            row["non_striker_id"] = None
        if rng.random() < 0.02:
            row["bowler_id"] = f"x{rng.getrandbits(28):07x}"
        if row["match_id"] in new_match_ids and row.get("wickets") and timed_out_budget:
            row["wickets"][0]["kind"] = "timed out"
            timed_out_budget -= 1
        kept.append(row)
    entities["deliveries"] = kept

    for player in entities["players"]:
        if rng.random() < 0.60:
            player["contact_email"] = f"{slug(player['unique_name'])}@example.com"
        else:
            player["contact_email"] = None


def build_daily_feed(
    matches: list[dict[str, Any]], register: dict[str, dict[str, str]], out: Path, days: int, rng: random.Random
) -> list[str]:
    """
    Daily feed: one directory per match day with that day's `matches` and
    `deliveries` only (what an incremental daily export looks like).

    The last day is a broken load: the deliveries feed is truncated to ~25% of a
    match and 30% of non_striker_id values are null. Everything before it is
    real, untouched data — including the natural 1-vs-2-matches-per-day swing
    that makes fixed day-over-day thresholds noisy.
    """
    match_days = sorted({m["info"]["dates"][0] for m in matches})[-(days + 1):]
    written = []
    for i, day in enumerate(match_days):
        entities = build_entities([m for m in matches if m["info"]["dates"][0] == day], register)
        daily = {"matches": entities["matches"], "deliveries": entities["deliveries"]}
        if i == len(match_days) - 1:
            daily["deliveries"] = daily["deliveries"][: max(1, len(daily["deliveries"]) // 8)]
            for row in daily["deliveries"]:
                if rng.random() < 0.30:
                    row["non_striker_id"] = None
        write_snapshot(daily, out / day)
        written.append(day)
    return written


def write_snapshot(entities: dict[str, list[dict[str, Any]]], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in entities.items():
        # mtime=0 and no stored filename: identical data → identical bytes (clean git diffs).
        with open(directory / f"{name}.jsonl.gz", "wb") as raw, \
                gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz, \
                io.TextIOWrapper(gz, encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
        print(f"  {directory.name}/{name}.jsonl.gz: {len(rows):,} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("test_data/cricket"))
    parser.add_argument("--cache", type=Path, default=Path(".datalens/.tmp/downloads/cricsheet"))
    parser.add_argument("--from-season", type=int, default=2017)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--daily", type=int, default=12,
                        help="Also write a daily feed of the last N normal match days + 1 broken day (0 = skip)")
    args = parser.parse_args()

    matches = load_matches(fetch(IPL_ZIP_URL, args.cache), args.from_season)
    register = load_register(fetch(REGISTER_URL, args.cache))

    match_days = sorted({m["info"]["dates"][0] for m in matches})
    cutoff = match_days[-2]
    day1 = [m for m in matches if m["info"]["dates"][0] <= cutoff]
    new_ids = {m["_id"] for m in matches if m["info"]["dates"][0] > cutoff}
    print(f"{len(matches)} matches from {args.from_season}; day1 cutoff {cutoff}, day2 adds {match_days[-1]}")

    write_snapshot(build_entities(day1, register), args.out / "day1")
    day2 = build_entities(matches, register, DAY2_FILL)
    inject_drift(day2, new_ids, random.Random(args.seed))
    write_snapshot(day2, args.out / "day2")

    daily_days = []
    if args.daily:
        daily_days = build_daily_feed(matches, register, args.out / "daily", args.daily, random.Random(args.seed))

    manifest = {
        "source": {"ipl_json": IPL_ZIP_URL, "register": REGISTER_URL, "license": "ODC-BY 1.0"},
        "from_season": args.from_season,
        "seed": args.seed,
        "day1_cutoff": cutoff,
        "day2_added_date": match_days[-1],
        "day2_added_match_ids": sorted(new_ids),
        "injected_changes": [{"kind": k, "change": c, "expected_detection": e} for k, c, e in INJECTED_CHANGES],
        "daily_feed": {
            "days": daily_days,
            "broken_day": daily_days[-1] if daily_days else None,
            "broken_day_changes": [
                "deliveries truncated to ~1/8 of the day's rows",
                "deliveries.non_striker_id null in ~30% of rows",
            ],
        },
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {args.out / 'manifest.json'}")


if __name__ == "__main__":
    main()
