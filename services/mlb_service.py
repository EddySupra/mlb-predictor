from datetime import date, timedelta, datetime, timezone
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

def _format_game_time(g: Dict[str, Any]) -> str:
    """Return a nice time string for the schedule row.

    Prefer statsapi's game_time field; if it's missing or 'TBD', try to
    derive the time from game_datetime (ISO timestamp) if available.
    """
    raw = str(g.get("game_time") or "").strip()
    if raw and raw.upper() != "TBD":
        # StatsAPI already gave us something like '7:07 PM'
        return raw

    # Try to fall back to full datetime
    dt_raw = g.get("game_datetime") or g.get("game_date")
    if not dt_raw:
        return "TBD"

    try:
        ds = str(dt_raw)
        if "T" not in ds:
            return "TBD"

        if ds.endswith("Z"):
            ds = ds[:-1] + "+00:00"

        dt = datetime.fromisoformat(ds)

        return dt.strftime("%I:%M %p").lstrip("0")
    except Exception:
        return "TBD"
def _clean_game_time(g: Dict[str, Any]) -> str:

    raw = str(g.get("game_time") or "").strip()
    if not raw:
        return "TBD"

    lower = raw.lower()
    if lower.startswith("12:00") and "am" in lower:
        return "TBD"

    return raw
def fetch_schedule(team_id: Optional[int], days: int, mode: str) -> Dict[str, Any]:

    today = date.today()

    if mode == "past":
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
                    "time": _clean_game_time(g),
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

def _recent_team_trend(team_id: Optional[int], limit: int = 5) -> Dict[str, Any]:
    """
    Very simple 'last N games' trend for a team using statsapi.schedule.

    Returns:
      {
        "labels": [...],        # ['11-28', '11-30', ...]
        "runs_for": [...],
        "runs_against": [...],
        "avg_runs_for": float,
        "avg_runs_against": float,
      }
    """
    empty = {
        "labels": [],
        "runs_for": [],
        "runs_against": [],
        "avg_runs_for": 0.0,
        "avg_runs_against": 0.0,
    }

    if not team_id:
        return empty

    labels: List[str] = []
    runs_for: List[int] = []
    runs_against: List[int] = []

    today = date.today()
    cur = today - timedelta(days=1)
    scanned_days = 0
    max_days = 60 

    while len(labels) < limit and scanned_days < max_days:
        try:
            sched = statsapi.schedule(cur.isoformat())
        except Exception:
            sched = []

        for g in sched:
            hid = g.get("home_id")
            aid = g.get("away_id")
            if team_id not in (hid, aid):
                continue

            h_runs = g.get("home_score") or 0
            a_runs = g.get("away_score") or 0

            if team_id == hid:
                rf, ra = h_runs, a_runs
            else:
                rf, ra = a_runs, h_runs

            labels.append(cur.strftime("%m-%d"))
            runs_for.append(int(rf))
            runs_against.append(int(ra))
            break  # only one game per day for this team

        cur -= timedelta(days=1)
        scanned_days += 1

    if not runs_for:
        return empty

    return {
        "labels": list(reversed(labels)),
        "runs_for": list(reversed(runs_for)),
        "runs_against": list(reversed(runs_against)),
        "avg_runs_for": sum(runs_for) / len(runs_for),
        "avg_runs_against": sum(runs_against) / len(runs_against),
    }
def _head_to_head_last_n(team_a_id: Optional[int], team_b_id: Optional[int], limit: int = 5) -> Dict[str, Any]:

    result = {
        "games": [],
        "team_a_wins": 0,
        "team_b_wins": 0,
    }

    if not team_a_id or not team_b_id:
        return result

    games: List[Dict[str, Any]] = []
    today = date.today()
    cur = today - timedelta(days=1)
    scanned_days = 0
    max_days = 365  # up to 1 season back

    while len(games) < limit and scanned_days < max_days:
        try:
            sched = statsapi.schedule(cur.isoformat())
        except Exception:
            sched = []

        for g in sched:
            hid = g.get("home_id")
            aid = g.get("away_id")
            if {hid, aid} != {team_a_id, team_b_id}:
                continue

            h_runs = g.get("home_score") or 0
            a_runs = g.get("away_score") or 0

            if hid == team_a_id:
                team_a_runs = h_runs
                team_b_runs = a_runs
            else:
                team_a_runs = a_runs
                team_b_runs = h_runs

            games.append(
                {
                    "date_label": cur.strftime("%m-%d"),
                    "team_a_runs": int(team_a_runs),
                    "team_b_runs": int(team_b_runs),
                }
            )
            break  

        cur -= timedelta(days=1)
        scanned_days += 1

    games.reverse()  

    team_a_wins = sum(1 for g in games if g["team_a_runs"] > g["team_b_runs"])
    team_b_wins = sum(1 for g in games if g["team_b_runs"] > g["team_a_runs"])

    result["games"] = games
    result["team_a_wins"] = team_a_wins
    result["team_b_wins"] = team_b_wins
    return result
def _parse_ip_to_outs(ip_raw: Any) -> float:

    if ip_raw is None:
        return 0.0

    try:
        s = str(ip_raw).strip()
        if not s:
            return 0.0

        if "." in s:
            whole, frac = s.split(".", 1)
            whole_outs = int(whole) * 3
            frac_outs = int(frac)
            return float(whole_outs + frac_outs)
        else:
            return float(int(s) * 3)
    except Exception:
        return 0.0


def _primary_pitcher(team_node: Dict[str, Any]) -> Dict[str, Any]:

    default = {
        "name": "N/A",
        "ip": "0.0",
        "h": 0,
        "er": 0,
        "so": 0,
        "bb": 0,
    }

    try:
        players = team_node.get("players") or {}
        if not isinstance(players, dict) or not players:
            return default

        best = None
        best_outs = -1.0

        for pdata in players.values():
            if not isinstance(pdata, dict):
                continue

            person = pdata.get("person") or {}
            name = (
                person.get("fullName")
                or person.get("lastName")
                or person.get("boxscoreName")
                or "Pitcher"
            )

            stats = (pdata.get("stats") or {}).get("pitching") or {}
            if not isinstance(stats, dict):
                continue

            ip_str = stats.get("ip") or stats.get("inningsPitched")
            outs = _parse_ip_to_outs(ip_str)
            if outs <= 0:
                continue

            if outs > best_outs:
                best_outs = outs
                best = {
                    "name": name,
                    "ip": str(ip_str) if ip_str is not None else "0.0",
                    "h": int(stats.get("h") or stats.get("hits") or 0),
                    "er": int(stats.get("er") or stats.get("earnedRuns") or 0),
                    "so": int(stats.get("so") or stats.get("strikeOuts") or 0),
                    "bb": int(stats.get("bb") or stats.get("baseOnBalls") or 0),
                }

        return best or default
    except Exception:
        return default

def fetch_game_page(
    game_id: int,
    away_hint=None,
    home_hint=None,
    venue_hint=None,
    date_hint=None,
    time_hint=None,
) -> Dict[str, Any]:

    try:
        box = statsapi.boxscore_data(game_id)
    except Exception:
        return {"title": "Game not found", "subtitle": "", "status": "Error"}

    teams = box.get("teamInfo", {}) or {}
    home_info = teams.get("home", {}) or {}
    away_info = teams.get("away", {}) or {}

    home_name = home_info.get("name") or home_hint or "Home"
    away_name = away_info.get("name") or away_hint or "Away"

    home_id = home_info.get("id")
    away_id = away_info.get("id")

    home_abbr = team_abbr_from_name(home_name)
    away_abbr = team_abbr_from_name(away_name)

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

    home_r = _stat(home_bat, "r", "runs", default=summed_home_r)
    away_r = _stat(away_bat, "r", "runs", default=summed_away_r)

    home_h = _stat(home_bat, "h", "hits", default=0)
    away_h = _stat(away_bat, "h", "hits", default=0)

    home_e = _stat(home_bat, "e", "errors", default=0)
    away_e = _stat(away_bat, "e", "errors", default=0)

    # ---- Primary pitcher comparison (for fallback card) ----
    home_pitcher = _primary_pitcher(home_node)
    away_pitcher = _primary_pitcher(away_node)


    # ---- Win probability heuristic ----
    if isinstance(away_r, (int, float)) and isinstance(home_r, (int, float)):
        total = (away_r or 0) + (home_r or 0)
        if total > 0:
            wp_away = round(100 * (away_r or 0) / total)
            wp_home = 100 - wp_away
            note = "Winner Prediction based off previous game stats/trends + Mix of personal betting strageies to determine best probable winner"
        else:
            wp_away = wp_home = 50
            note = "No runs yet."
    else:
        wp_away = wp_home = 50
        note = "Status TBD."

    # ---- Predicted winner text ----
    if abs(wp_home - wp_away) < 3:
        wp_pick = "Too close to call"
    elif wp_home > wp_away:
        wp_pick = home_name
    else:
        wp_pick = away_name

    # ---- Recent team trends + head-to-head ----
    trend_home = _recent_team_trend(home_id)
    trend_away = _recent_team_trend(away_id)
    h2h = _head_to_head_last_n(home_id, away_id, limit=5)

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
        "wp_pick": wp_pick,
        "home_abbr": home_abbr,
        "away_abbr": away_abbr,
        "trend_home": trend_home,
        "trend_away": trend_away,
        "h2h": h2h,
        "home_pitcher": home_pitcher,
        "away_pitcher": away_pitcher,
    }
