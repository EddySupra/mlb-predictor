from datetime import date, timedelta
from typing import Optional, List, Dict, Any
import statsapi

# 30 MLB clubs (id, name, abbr)
TEAMS: List[Dict[str, Any]] = sorted(
    [
        {"id": 108, "name": "Los Angeles Angels", "abbr": "LAA"},
        {"id": 109, "name": "Arizona Diamondbacks", "abbr": "ARI"},
        {"id": 110, "name": "Baltimore Orioles", "abbr": "BAL"},
        {"id": 111, "name": "Boston Red Sox", "abbr": "BOS"},
        {"id": 112, "name": "Chicago Cubs", "abbr": "CHC"},
        {"id": 113, "name": "Cincinnati Reds", "abbr": "CIN"},
        {"id": 114, "name": "Cleveland Guardians", "abbr": "CLE"},
        {"id": 115, "name": "Colorado Rockies", "abbr": "COL"},
        {"id": 116, "name": "Detroit Tigers", "abbr": "DET"},
        {"id": 117, "name": "Houston Astros", "abbr": "HOU"},
        {"id": 118, "name": "Kansas City Royals", "abbr": "KC"},
        {"id": 119, "name": "Los Angeles Dodgers", "abbr": "LAD"},
        {"id": 120, "name": "Washington Nationals", "abbr": "WSH"},
        {"id": 121, "name": "New York Mets", "abbr": "NYM"},
        {"id": 133, "name": "Oakland Athletics", "abbr": "OAK"},
        {"id": 134, "name": "Pittsburgh Pirates", "abbr": "PIT"},
        {"id": 135, "name": "San Diego Padres", "abbr": "SD"},
        {"id": 136, "name": "Seattle Mariners", "abbr": "SEA"},
        {"id": 137, "name": "San Francisco Giants", "abbr": "SF"},
        {"id": 138, "name": "St. Louis Cardinals", "abbr": "STL"},
        {"id": 139, "name": "Tampa Bay Rays", "abbr": "TB"},
        {"id": 140, "name": "Texas Rangers", "abbr": "TEX"},
        {"id": 141, "name": "Toronto Blue Jays", "abbr": "TOR"},
        {"id": 142, "name": "Atlanta Braves", "abbr": "ATL"},
        {"id": 143, "name": "Chicago White Sox", "abbr": "CWS"},
        {"id": 144, "name": "Miami Marlins", "abbr": "MIA"},
        {"id": 145, "name": "New York Yankees", "abbr": "NYY"},
        {"id": 146, "name": "Philadelphia Phillies", "abbr": "PHI"},
        {"id": 147, "name": "Minnesota Twins", "abbr": "MIN"},
        {"id": 158, "name": "Milwaukee Brewers", "abbr": "MIL"},
    ],
    key=lambda x: x["name"],
)


def team_abbr_from_name(name: str) -> str:
    if not name:
        return ""
    for t in TEAMS:
        if t["name"].lower() == name.lower():
            return t["abbr"]
    return name[:3].upper()


def fetch_schedule(team_id: Optional[int], days: int, mode: str) -> Dict[str, Any]:
    """
    Returns MLB schedule data formatted for your MLB UI.

    mode = "future" → today to today+days      (ascending)
    mode = "past"   → yesterday back N days   (descending)
    """
    today = date.today()

    if mode == "past":
        # Example days=7 → from yesterday back to (today-7)
        start = today - timedelta(days=1)
        end = today - timedelta(days=days)
        step = -1
    else:
        start = today
        end = today + timedelta(days=days)
        step = 1

    rows: List[Dict[str, Any]] = []
    cur = start
    delta = timedelta(days=1)

    while (step > 0 and cur <= end) or (step < 0 and cur >= end):
        try:
            sched = statsapi.schedule(cur.isoformat())
        except Exception:
            sched = []

        for g in sched:
            hid, aid = g.get("home_id"), g.get("away_id")
            if team_id and team_id not in (hid, aid):
                continue

            rows.append(
                {
                    "date": g.get("game_date", ""),
                    "time": g.get("game_time", ""),
                    "away": g.get("away_name", ""),
                    "home": g.get("home_name", ""),
                    "venue": g.get("venue_name", ""),
                    "status": g.get("status", ""),
                    "away_score": g.get("away_score"),
                    "home_score": g.get("home_score"),
                    "game_pk": g.get("game_id"),
                }
            )

        cur = cur + delta * step

    team_label = (
        "ALL"
        if not team_id
        else next((t["abbr"] for t in TEAMS if t["id"] == team_id), str(team_id))
    )

    return {
        "team": team_label,
        "window": f"{start} to {end}",
        "rows": rows,
    }


def _stat(d: Dict[str, Any], *keys: str, default=0):
    """
    Helper: try multiple possible keys (e.g., 'r' or 'runs').
    """
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def fetch_game_page(
    game_id: int,
    away_hint=None,
    home_hint=None,
    venue_hint=None,
    date_hint=None,
    time_hint=None,
) -> Dict[str, Any]:
    """
    Returns boxscore + win prob + inning table for MLB game page.
    """
    try:
        box = statsapi.boxscore_data(game_id)
    except Exception:
        return {"title": "Game not found", "subtitle": "", "status": "Error"}

    teams = box.get("teamInfo", {}) or {}
    home_info = teams.get("home", {}) or {}
    away_info = teams.get("away", {}) or {}

    home_name = home_info.get("name") or home_hint or "Home"
    away_name = away_info.get("name") or away_hint or "Away"

    # ---- Inning-by-inning linescore ----
    line_score = box.get("innings") or []
    inning_numbers: List[Any] = []
    away_lines: List[Any] = []
    home_lines: List[Any] = []
    summed_away_r = 0
    summed_home_r = 0

    for inn in line_score:
        inning_numbers.append(inn.get("num", "?"))

        away_inn = inn.get("away", {}) or {}
        home_inn = inn.get("home", {}) or {}

        a_runs = away_inn.get("runs")
        h_runs = home_inn.get("runs")

        away_lines.append(a_runs if a_runs is not None else "-")
        home_lines.append(h_runs if h_runs is not None else "-")

        if isinstance(a_runs, (int, float)):
            summed_away_r += a_runs
        if isinstance(h_runs, (int, float)):
            summed_home_r += h_runs

    # ---- Team totals (R / H / E) ----
    home_node = box.get("home", {}) or {}
    away_node = box.get("away", {}) or {}

    home_bat = (home_node.get("teamStats") or {}).get("batting", {}) or {}
    away_bat = (away_node.get("teamStats") or {}).get("batting", {}) or {}

    # Try both styles: r vs runs, h vs hits, e vs errors
    home_r = _stat(home_bat, "r", "runs", default=summed_home_r)
    away_r = _stat(away_bat, "r", "runs", default=summed_away_r)

    home_h = _stat(home_bat, "h", "hits", default=0)
    away_h = _stat(away_bat, "h", "hits", default=0)

    home_e = _stat(home_bat, "e", "errors", default=0)
    away_e = _stat(away_bat, "e", "errors", default=0)

    # ---- Win probability heuristic ----
    if isinstance(away_r, (int, float)) and isinstance(home_r, (int, float)):
        total = (away_r or 0) + (home_r or 0)
        if total > 0:
            wp_away = round(100 * (away_r or 0) / total)
            wp_home = 100 - wp_away
            note = "Heuristic: based on final score."
        else:
            wp_away = wp_home = 50
            note = "No runs yet."
    else:
        wp_away = wp_home = 50
        note = "Status TBD."

    status = box.get("gameStatus", {}).get("detailedState", "")
    when = date_hint or ""

    return {
        "title": f"{away_name} @ {home_name}",
        "subtitle": f"Game ID: {game_id}",
        "status": status,
        "when": when,
        "venue": venue_hint or "",
        "away_name": away_name,
        "home_name": home_name,
        "away_r": away_r,
        "home_r": home_r,
        "away_h": away_h,
        "home_h": home_h,
        "away_e": away_e,
        "home_e": home_e,
        "innings": inning_numbers,
        "away_innings": away_lines,
        "home_innings": home_lines,
        "wp_home_pct": wp_home,
        "wp_away_pct": wp_away,
        "wp_note": note,
    }
