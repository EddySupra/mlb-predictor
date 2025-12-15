# services/nba_service.py
from __future__ import annotations

from datetime import date, timedelta, datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlencode
import math


import requests

# =======================
# BALLDONTLIE CONFIG
# =======================

BALLDONTLIE_BASE = "https://api.balldontlie.io/v1"
BALLDONTLIE_API_KEY = "fd339e79-c3b6-4e99-bdf0-4dfbeebde702"


def _bdl_headers() -> Dict[str, str]:
    if not BALLDONTLIE_API_KEY or BALLDONTLIE_API_KEY == "YOUR_BALLDONTLIE_API_KEY_HERE":
        raise RuntimeError(
            "BALLDONTLIE_API_KEY is not set. "
            "Open services/nba_service.py and put your real BallDontLie key in BALLDONTLIE_API_KEY."
        )

    return {"Authorization": BALLDONTLIE_API_KEY}



_BDL_CACHE: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
_BDL_CACHE_TTL = timedelta(seconds=60)


def _bdl_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Wrapper around requests.get with:
      - in-memory caching (to avoid hammering the API)
      - graceful handling of 429 Too Many Requests
    """
    params = params or {}
    key = f"{path}?{urlencode(sorted(params.items()), doseq=True)}"
    now = datetime.utcnow()

    if key in _BDL_CACHE:
        ts, cached = _BDL_CACHE[key]
        if now - ts <= _BDL_CACHE_TTL:
            return cached

    url = f"{BALLDONTLIE_BASE}{path}"

    try:
        resp = requests.get(url, headers=_bdl_headers(), params=params, timeout=20)

        if resp.status_code == 429:
            print(f"[nba_service] BallDontLie 429 Too Many Requests for {url}")
            if key in _BDL_CACHE:
                return _BDL_CACHE[key][1]
            return {"data": [], "meta": {}}

        resp.raise_for_status()
        data = resp.json()

        _BDL_CACHE[key] = (now, data)
        return data

    except Exception as exc:
        print(f"[nba_service] BallDontLie GET error {url}: {exc}")
        if key in _BDL_CACHE:
            return _BDL_CACHE[key][1]
        return {"data": [], "meta": {}}


# =======================
# TEAMS
# =======================

def _load_nba_teams() -> List[Dict[str, Any]]:
    """
    Build NBA_TEAMS from /teams.
    Shape: {id, name, abbr}
    """
    teams: List[Dict[str, Any]] = []
    cursor: Optional[int] = None

    while True:
        params: Dict[str, Any] = {"per_page": 100}
        if cursor is not None:
            params["cursor"] = cursor

        data = _bdl_get("/teams", params)
        batch = data.get("data", [])
        if not batch:
            break

        for t in batch:
            try:
                tid = int(t["id"])
            except Exception:
                continue

            full_name = str(t.get("full_name") or "").strip()
            abbr = str(t.get("abbreviation") or "").upper()

            teams.append(
                {
                    "id": tid,
                    "name": full_name,
                    "abbr": abbr,
                }
            )

        meta = data.get("meta") or {}
        cursor = meta.get("next_cursor")
        if cursor in (None, 0):
            break

    # Fallback: if API failed, return an empty list so app still runs
    teams.sort(key=lambda x: x["name"])
    return teams


# Initialize global team list
try:
    NBA_TEAMS: List[Dict[str, Any]] = _load_nba_teams()
except Exception as exc:
    print(f"[nba_service] Failed to load teams: {exc}")
    NBA_TEAMS = []

_TEAMS_BY_ID = {t["id"]: t for t in NBA_TEAMS}
_TEAMS_BY_ABBR = {t["abbr"].upper(): t for t in NBA_TEAMS}


def _team_label(team_id: Optional[int]) -> str:
    if team_id is None:
        return "ALL TEAMS"
    t = _TEAMS_BY_ID.get(team_id)
    if not t:
        return f"Team {team_id}"
    return f'{t["name"]} ({t["abbr"]})'


# =======================
# DATE HELPERS
# =======================
def _minutes_to_seconds(min_str: str) -> int:

    if not min_str or min_str == "00:00":
        return 0
    try:
        parts = min_str.split(":")
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + int(s)
        elif len(parts) == 3:
            h, m, s = parts
            return (int(h) * 60 + int(m)) * 60 + int(s)
    except Exception:
        return 0
    return 0

def _iter_dates(days: int, mode: str) -> List[date]:

    today = date.today()
    if mode == "past":
        return [today - timedelta(days=i + 1) for i in range(days)]
    else:
        return [today + timedelta(days=i) for i in range(days)]


def _date_range(days: int, mode: str) -> Tuple[date, date]:
    today = date.today()
    if mode == "past":
        end = today - timedelta(days=1)
        start = end - timedelta(days=days - 1)
    else:
        start = today
        end = today + timedelta(days=days - 1)
    return start, end


def _parse_bdl_datetime(dt_str: Optional[str]) -> Tuple[str, str]:

    if not dt_str:
        return "", "TBD"

    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        dt_utc = dt.astimezone(timezone.utc)
        date_str = dt_utc.date().isoformat()
        # On Windows, %-I isn't valid; use %I and strip leading zero
        time_raw = dt_utc.strftime("%I:%M %p ET")
        time_str = time_raw.lstrip("0")
        return date_str, time_str
    except Exception:
        return dt_str[:10], "TBD"
def _fetch_team_ids_for_game(game_id: str) -> Dict[str, int]:

    if not game_id:
        return {}

    data = _bdl_get("/games", {"ids[]": game_id, "per_page": 1})
    games = data.get("data") or []
    if not games:
        return {}

    g = games[0]
    home_team = (g.get("home_team") or {})
    away_team = (g.get("visitor_team") or {})

    try:
        return {
            "home": int(home_team.get("id")) if home_team.get("id") is not None else None,
            "away": int(away_team.get("id")) if away_team.get("id") is not None else None,
        }
    except Exception:
        return {}
def _fetch_team_recent_trend(team_id: Optional[int], limit: int = 5) -> Dict[str, Any]:

    empty = {
        "labels": [],
        "pts_for": [],
        "pts_against": [],
        "margin": [],
        "avg_pts_for": 0.0,
        "avg_pts_against": 0.0,
    }

    if not team_id:
        return empty

    today = date.today()
    start = today - timedelta(days=40)  # look at roughly the last 40 days

    params = {
        "team_ids[]": team_id,
        "start_date": start.isoformat(),
        "end_date": today.isoformat(),
        "per_page": 100,
    }

    try:
        data = _bdl_get("/games", params)
    except Exception as exc:
        print(f"[nba_trend] error for team {team_id}: {exc}")
        return empty

    games = data.get("data") or []
    if not games:
        return empty

    try:
        games.sort(key=lambda g: str(g.get("date") or ""))
    except Exception:
        pass

    if len(games) > limit:
        games = games[-limit:]

    labels: List[str] = []
    pts_for: List[int] = []
    pts_against: List[int] = []
    margin: List[int] = []

    for g in games:
        try:
            date_str = str(g.get("date") or "")[:10]
            label = date_str[5:] if len(date_str) >= 10 else date_str

            home = g.get("home_team") or {}
            away = g.get("visitor_team") or {}
            home_id = home.get("id")
            away_id = away.get("id")

            home_score = int(g.get("home_team_score") or 0)
            away_score = int(g.get("visitor_team_score") or 0)

            if team_id == home_id:
                pf = home_score
                pa = away_score
            elif team_id == away_id:
                pf = away_score
                pa = home_score
            else:
                continue

            labels.append(label)
            pts_for.append(pf)
            pts_against.append(pa)
            margin.append(pf - pa)
        except Exception as row_exc:
            print(f"[nba_trend] row error for team {team_id}: {row_exc}")
            continue

    if not pts_for:
        return empty

    avg_for = sum(pts_for) / len(pts_for)
    avg_against = sum(pts_against) / len(pts_against)

    return {
        "labels": labels,
        "pts_for": pts_for,
        "pts_against": pts_against,
        "margin": margin,
        "avg_pts_for": avg_for,
        "avg_pts_against": avg_against,
    }


# =======================
# SCHEDULE 
# =======================

def fetch_nba_schedule(
    team_id: Optional[int],
    days: int,
    mode: str = "future",
) -> Dict[str, Any]:
    """
    Fetch NBA schedule using BallDontLie /games, querying ONE DATE AT A TIME
    with the 'dates[]' parameter instead of a start_date/end_date range.

    Returns:
        {
          "team": "Atlanta Hawks (ATL)" or "ALL TEAMS",
          "window": "2025-12-05 to 2025-12-11",
          "rows": [
             {
               "date": "2025-12-05",
               "time": "7:30 pm ET",
               "away": "CLE",
               "home": "ATL",
               "away_score": 110,
               "home_score": 120,
               "venue": "State Farm Arena",
               "status": "Final",
               "game_id": 18447091,
             },
             ...
          ]
        }
    """
    mode = mode or "future"

    try:
        days = int(days)
    except Exception:
        days = 7
    days = max(1, min(days, 7))

    dates_for_window = _iter_dates(days, mode)
    team_label = _team_label(team_id)

    rows: List[Dict[str, Any]] = []

    for d in dates_for_window:
        params: Dict[str, Any] = {
            "per_page": 100,
            "dates[]": d.isoformat(),
        }
        if team_id is not None:
            params["team_ids[]"] = team_id

        data = _bdl_get("/games", params)
        games = data.get("data", [])
        if not games:
            continue

        for g in games:
            try:
                gid = g.get("id")
                if not gid:
                    continue

                # ---------- DATE ----------
                game_date_str = str(g.get("date") or d.isoformat())
                date_str = game_date_str[:10]  # 'YYYY-MM-DD'

                # ---------- STATUS + TIME ----------
                raw_status = str(g.get("status", ""))
                dt_iso = g.get("datetime")

                time_str = "TBD"
                status_text = raw_status

                if "T" in raw_status and "Z" in raw_status:
                    date_str, time_str = _parse_bdl_datetime(raw_status)
                    status_text = "Scheduled"

                else:
                    if dt_iso:
                        _, parsed_time = _parse_bdl_datetime(dt_iso)
                        if parsed_time != "TBD":
                            time_str = parsed_time

                # ---------- TEAMS / SCORE ----------
                home_team = g.get("home_team") or {}
                away_team = g.get("visitor_team") or {}

                home_abbr = str(home_team.get("abbreviation", "")).upper()
                away_abbr = str(away_team.get("abbreviation", "")).upper()

                home_score = g.get("home_team_score")
                away_score = g.get("visitor_team_score")

                # ---------- VENUE ----------
                arena = g.get("arena")
                venue = ""
                if isinstance(arena, str):
                    venue = arena
                elif isinstance(arena, dict):
                    venue = arena.get("name") or ""
                if not venue:
                    venue = g.get("arena_name") or ""

                rows.append(
                    {
                        "date": date_str,
                        "time": time_str,
                        "away": away_abbr,
                        "home": home_abbr,
                        "away_score": home_score if away_abbr == home_abbr else away_score,
                        "home_score": home_score,
                        "venue": venue,
                        "status": status_text,
                        "game_id": gid,
                    }
                )

            except Exception as row_exc:
                print(f"[fetch_nba_schedule] row error: {row_exc}")
                continue

    rows.sort(key=lambda r: (r["date"], r["home"], r["away"]))

    window = ""
    if dates_for_window:
        window = f"{min(dates_for_window)} to {max(dates_for_window)}"

    return {
        "team": team_label,
        "window": window,
        "rows": rows,
    }



# =======================
# SINGLE GAME PAGE
# =======================

_STARTERS_CACHE: Dict[str, List[Dict[str, Any]]] = {}


def _fetch_top_players_for_game(game_id: str) -> List[Dict[str, Any]]:
    """
    Use BallDontLie /stats to get boxscore for one game and return the
    starting 5 for each team (up to 10 players total), with their GAME stats.

    Each returned dict looks like:
      {
        "name": "Player Name",
        "team": "ATL",
        "pos": "G",
        "pts": 23,
        "reb": 8,
        "ast": 6,
      }
    """
    if not game_id:
        return []

    if game_id in _STARTERS_CACHE:
        return _STARTERS_CACHE[game_id]

    data = _bdl_get("/stats", {"game_ids[]": game_id, "per_page": 100})
    stats = data.get("data", [])
    if not stats:
        _STARTERS_CACHE[game_id] = []
        return []

    by_team: Dict[str, List[Dict[str, Any]]] = {}

    for s in stats:
        try:
            player = s.get("player") or {}
            team = s.get("team") or {}

            first = str(player.get("first_name") or "").strip()
            last = str(player.get("last_name") or "").strip()
            name = (first + " " + last).strip() or "Unknown"

            team_abbr = str(team.get("abbreviation") or "").upper()

            position = str(player.get("position") or "").strip() or "—"  # <<<

            pts = int(s.get("pts") or 0)
            reb = int(s.get("reb") or 0)
            ast = int(s.get("ast") or 0)
            minutes = str(s.get("min") or "00:00")

            starter_flag = s.get("starter")
            is_starter = bool(starter_flag) if starter_flag is not None else False

            record = {
                "name": name,
                "team": team_abbr,
                "pos": position,
                "pts": pts,
                "reb": reb,
                "ast": ast,
                "min": minutes,
                "is_starter": is_starter,
            }

            by_team.setdefault(team_abbr, []).append(record)
        except Exception as row_exc:
            print(f"[starters] row error for game {game_id}: {row_exc}")
            continue

    starters: List[Dict[str, Any]] = []

    for team_abbr, players in by_team.items():
        if not players:
            continue

        if any(p["is_starter"] for p in players):
            team_starters = [p for p in players if p["is_starter"]]
        else:
            team_starters = sorted(
                players,
                key=lambda p: _minutes_to_seconds(p["min"]),
                reverse=True,
            )

        team_starters = team_starters[:5]

        for p in team_starters:
            starters.append(
                {
                    "name": p["name"],
                    "team": p["team"],
                    "pos": p["pos"],
                    "pts": p["pts"],
                    "reb": p["reb"],
                    "ast": p["ast"],
                }
            )

    starters.sort(key=lambda p: (p["team"], -p["pts"]))

    _STARTERS_CACHE[game_id] = starters
    return starters
def _fetch_head_to_head(
    home_id: Optional[int],
    away_id: Optional[int],
    home_label: str,
    away_label: str,
    limit: int = 5,
) -> Dict[str, Any]:

    result: Dict[str, Any] = {
        "team_a_name": home_label,
        "team_b_name": away_label,
        "team_a_wins": 0,
        "team_b_wins": 0,
        "games": [],
    }

    if not home_id or not away_id:
        return result

    today = date.today()
    start = today - timedelta(days=365 * 3)

    params: Dict[str, Any] = {
        "team_ids[]": [home_id, away_id],
        "start_date": start.isoformat(),
        "end_date": today.isoformat(),
        "per_page": 100,
    }

    data = _bdl_get("/games", params)
    games = data.get("data") or []
    h2h_games: List[Dict[str, Any]] = []

    for g in games:
        try:
            home_team = (g.get("home_team") or {})
            away_team = (g.get("visitor_team") or {})
            h_id = home_team.get("id")
            a_id = away_team.get("id")

            if set([h_id, a_id]) != set([home_id, away_id]):
                continue

            date_str = str(g.get("date") or "")[:10]
            label = date_str[5:] if len(date_str) >= 10 else date_str

            home_score = int(g.get("home_team_score") or 0)
            away_score = int(g.get("visitor_team_score") or 0)

            if h_id == home_id:
                a_pts = home_score
                b_pts = away_score
            else:
                a_pts = away_score
                b_pts = home_score

            h2h_games.append(
                {
                    "date": date_str,
                    "date_label": label,
                    "team_a_pts": a_pts,
                    "team_b_pts": b_pts,
                }
            )

            if a_pts > b_pts:
                result["team_a_wins"] += 1
            elif b_pts > a_pts:
                result["team_b_wins"] += 1

        except Exception as exc:
            print(f"[h2h] row error: {exc}")
            continue

    h2h_games.sort(key=lambda x: x["date"])
    if len(h2h_games) > limit:
        h2h_games = h2h_games[-limit:]

    result["games"] = h2h_games
    return result





def fetch_nba_game(
    game_id: str,
    away_hint: Optional[str] = None,
    home_hint: Optional[str] = None,
    date_hint: Optional[str] = None,
    time_hint: Optional[str] = None,
) -> Dict[str, Any]:
    data = _bdl_get(f"/games/{game_id}")
    g = data.get("data") or data

    raw_status = str(g.get("status", "Unknown"))
    game_date_str = str(g.get("date") or date_hint or "")
    dt_iso = g.get("datetime")

    date_str = game_date_str
    time_str = ""
    status_text = raw_status

    if "T" in raw_status and "Z" in raw_status:
        date_str, time_str = _parse_bdl_datetime(raw_status)
        status_text = "Scheduled"
    else:
        if dt_iso:
            _, parsed_time = _parse_bdl_datetime(dt_iso)
            time_str = parsed_time

    when = date_str
    if time_str:
        when = f"{date_str} • {time_str}"

    home = g.get("home_team") or {}
    away = g.get("visitor_team") or {}

    home_name = home.get("full_name") or home_hint or "Home"
    away_name = away.get("full_name") or away_hint or "Away"

    home_id = home.get("id")
    away_id = away.get("id")

    home_abbr = str(home.get("abbreviation") or home_hint or "").upper()
    away_abbr = str(away.get("abbreviation") or away_hint or "").upper()

    home_score = int(g.get("home_team_score") or 0)
    away_score = int(g.get("visitor_team_score") or 0)

    away_trend = _fetch_team_recent_trend(away_id)
    home_trend = _fetch_team_recent_trend(home_id)

    h2h = _fetch_head_to_head(home_id, away_id, home_abbr, away_abbr)

    arena = g.get("arena")
    venue = ""
    if isinstance(arena, dict):
        venue = str(arena.get("name") or "")
    elif arena is not None:
        venue = str(arena)

    raw_starters = _fetch_top_players_for_game(str(game_id))

    starters_home = [p for p in raw_starters if p.get("team") == home_abbr]
    starters_away = [p for p in raw_starters if p.get("team") == away_abbr]

    top_players = raw_starters

    wp_home_pct, wp_away_pct, wp_note = _compute_wp(
        status=status_text,
        home_score=home_score,
        away_score=away_score,
        trend_home=home_trend,
        trend_away=away_trend,
    )

    if abs(wp_home_pct - wp_away_pct) < 3:
        wp_pick = "Too close to call"
    elif wp_home_pct > wp_away_pct:
        wp_pick = home_name
    else:
        wp_pick = away_name

    title = f"{away_name} @ {home_name}"
    subtitle = f"{status_text} • {when}" if when else status_text

    return {
        "title": title,
        "subtitle": subtitle,
        "status": status_text,
        "when": when,
        "away_name": away_name,
        "home_name": home_name,
        "away_score": away_score,
        "home_score": home_score,
        "venue": venue,
        "wp_home_pct": int(round(wp_home_pct)),
        "wp_away_pct": int(round(wp_away_pct)),
        "wp_note": wp_note,
        "wp_pick": wp_pick,
        "starters_home": starters_home,
        "starters_away": starters_away,
        "top_players": top_players,
        "trend_home": home_trend,
        "trend_away": away_trend,
        "home_abbr": home_abbr,
        "away_abbr": away_abbr,
        "h2h": h2h,
    }




def _minutes_to_seconds(min_str: str) -> int:

    if not min_str or min_str == "00:00":
        return 0
    try:
        parts = min_str.split(":")
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + int(s)
        elif len(parts) == 3:
            h, m, s = parts
            return (int(h) * 60 + int(m)) * 60 + int(s)
    except Exception:
        return 0
    return 0



# =======================
# WIN PROBABILITY
# =======================

def _compute_wp(
    status: str,
    home_score: int,
    away_score: int,
    trend_home: Optional[Dict[str, Any]] = None,
    trend_away: Optional[Dict[str, Any]] = None,
) -> Tuple[float, float, str]:

    status_lower = status.lower()
    diff = home_score - away_score

    # ---------- LIVE GAME HEURISTIC ----------
    if any(
        k in status_lower
        for k in ["progress", "quarter", "1st", "2nd", "3rd", "4th", "ot", "half", "live"]
    ):
        base = 50.0 + 3.0 * diff  # each point ≈ 3% shift
        base = max(5.0, min(95.0, base))
        return base, 100.0 - base, "Heuristic based on current score (not final result)."

    # ---------- PRE-GAME STYLE USING LAST 5 GAMES ----------
    def _net_rating(tr: Optional[Dict[str, Any]]) -> Optional[float]:
        if not tr:
            return None
        pf = float(tr.get("avg_pts_for") or 0.0)
        pa = float(tr.get("avg_pts_against") or 0.0)
        if pf == 0.0 and pa == 0.0:
            return None
        return pf - pa

    home_net = _net_rating(trend_home)
    away_net = _net_rating(trend_away)

    if home_net is not None and away_net is not None:
        rating_diff = home_net - away_net + 2.0


        try:
            home_prob = 1.0 / (1.0 + math.exp(-rating_diff / 6.0))
        except OverflowError:
            home_prob = 1.0 if rating_diff > 0 else 0.0

        home_wp = max(5.0, min(95.0, home_prob * 100.0))
        away_wp = 100.0 - home_wp

        note = (
            "Pre-game prediction using each team's previous games stats "
            "+ as well as personmal betting factors(home-court edge, momentum edge, vegas bias, etc... (Our best bet!!!)."
        )
        return home_wp, away_wp, note

    # ---------- FALLBACK ----------
    home_wp = 55.0
    away_wp = 45.0
    note = (
        "Simple pre-game style prediction (home-court edge only); "
        "recent game data unavailable."
    )
    return home_wp, away_wp, note

