#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from datetime import date, timedelta
from typing import Optional, Tuple, Any, Dict, List

import pandas as pd
import statsapi  # from MLB-StatsAPI

FUTURE_STATUSES = {
    "Scheduled", "Pre-Game", "Warmup", "Delayed Start", "Postponed", "If Necessary", "Preview"
}


def resolve_team(query: Optional[str]) -> Tuple[Optional[int], str, str]:
    """
    Return (team_id, display_name, abbr) for queries like 'NYY', 'Yankees', etc.
    If query is None/empty/'all', returns (None, 'ALL TEAMS', 'ALL').
    """
    if not query or str(query).strip().lower() in {"all", "none"}:
        return None, "ALL TEAMS", "ALL"

    candidates: List[Dict[str, Any]] = statsapi.lookup_team(query)
    if not candidates:
        raise SystemExit(
            f"No MLB team found for '{query}'. Try an abbreviation like 'NYY' or a name like 'Yankees' or 'Dodgers'."
        )

    q = query.strip().lower()
    exact_abbr = next((t for t in candidates if str(t.get("abbreviation", "")).lower() == q), None)
    exact_name = next((t for t in candidates if str(t.get("name", "")).lower() == q), None)
    chosen = exact_abbr or exact_name or next((t for t in candidates if t.get("active")), candidates[0])

    return int(chosen["id"]), str(chosen["name"]), str(chosen.get("abbreviation", ""))


def upcoming_games(team_query: Optional[str], days_ahead: int = 60) -> pd.DataFrame:
    """
    Get upcoming MLB games for the next `days_ahead` days.
    If team_query is None or 'all', returns all games; otherwise filters to the given team.
    """
    team_id, team_name, abbr = resolve_team(team_query)
    start = date.today()
    end = start + timedelta(days=days_ahead)

    # IMPORTANT: Do not pass team=None. Only include team if filtering.
    if team_id is None:
        sched = statsapi.schedule(start_date=start.isoformat(), end_date=end.isoformat())
    else:
        sched = statsapi.schedule(start_date=start.isoformat(), end_date=end.isoformat(), team=team_id)

    rows = []
    for g in sched:
        status = g.get("status")
        if status not in FUTURE_STATUSES:
            continue
        broadcasts = g.get("broadcasts", [])
        rows.append({
            "date": g.get("game_date"),
            "time": g.get("game_time_local"),
            "away": g.get("away_name"),
            "home": g.get("home_name"),
            "venue": g.get("venue_name"),
            "status": status,
            "game_pk": g.get("game_id"),
            "doubleheader": g.get("doubleheader"),
            "series": g.get("series_description"),
            "tv": ", ".join([b.get("name", "") for b in broadcasts]) if broadcasts else ""
        })

    df = pd.DataFrame(rows).sort_values(["date", "time", "away", "home"]).reset_index(drop=True)
    df.attrs["team_selected"] = abbr or team_name
    df.attrs["window"] = f"{start} to {end}"
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch upcoming MLB games (uses MLB Stats API).")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--all", action="store_true", help="Show all teams")
    group.add_argument("--team", type=str, help="Team (abbr or name), e.g., NYY, Yankees, Dodgers")
    parser.add_argument("--days", type=int, default=60, help="Days ahead (default 60)")
    parser.add_argument("--csv", type=str, help="Optional path to save CSV")
    args = parser.parse_args()

    # Default behavior if no --all/--team provided: show ALL for next 7 days
    if not args.all and not args.team:
        args.all = True
        if args.days == 60:
            args.days = 7

    team_query = None if args.all else args.team
    df = upcoming_games(team_query, args.days)
    print(f"Team: {df.attrs.get('team_selected')} | Window: {df.attrs.get('window')}")
    if df.empty:
        print("No upcoming games in this window.")
        return

    # Console preview (first 30 rows)
    print(df.head(30).to_string(index=False))

    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"\nSaved {len(df)} rows to {args.csv}")


if __name__ == "__main__":
    # Optional: silence urllib3 LibreSSL warning (harmless)
    # import warnings
    # warnings.filterwarnings("ignore")
    main()
