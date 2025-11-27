from datetime import date, timedelta
from typing import Optional, List, Dict, Any

import pandas as pd
from nba_api.stats.static import teams as nba_teams
from nba_api.stats.endpoints import (
    ScoreboardV2,
    BoxScoreSummaryV2,
    BoxScoreTraditionalV2,
)

# --------------------------------------------------
# Team metadata (id, name, abbr) cached once
# --------------------------------------------------

NBA_TEAMS: List[Dict[str, Any]] = sorted(
    [
        {"id": t["id"], "name": t["full_name"], "abbr": t["abbreviation"]}
        for t in nba_teams.get_teams()
    ],
    key=lambda x: x["name"],
)


def _tm_map() -> Dict[int, Dict[str, Any]]:
    return {t["id"]: t for t in NBA_TEAMS}


def _safe_int(x) -> Optional[int]:
    """Convert to int, but treat NaN/None safely."""
    try:
        if x is None:
            return None
        if isinstance(x, int):
            return x
        if pd.isna(x):
            return None
        return int(x)
    except Exception:
        return None


# --------------------------------------------------------------------
# SCHEDULE (REAL DATA): ScoreboardV2 + BoxScoreSummaryV2 fallback
# --------------------------------------------------------------------


def fetch_nba_schedule(team_id: Optional[int], days: int, mode: str) -> Dict[str, Any]:
    """
    Fetch NBA schedule + scores.

    mode = "future" → today .. today+days      (ascending)
    mode = "past"   → today-days .. yesterday  (most recent first)

    Behaviour:
      - FUTURE: scores always None → UI shows "—"
      - PAST:   try PTS_HOME/PTS_VISITOR; if missing but Final, use BoxScoreSummaryV2
    """
    today = date.today()
    tm = _tm_map()

    if mode == "past":
        start = today - timedelta(days=days)
        end = today - timedelta(days=1)
    else:
        start = today
        end = today + timedelta(days=days)

    rows: List[Dict[str, Any]] = []

    def parse_status_time(s: str):
        """
        Parse GAME_STATUS_TEXT into (status, display_time) for the table.
        """
        if not s:
            return "TBD", "TBD"
        s = str(s).strip()
        low = s.lower()

        if low.startswith("final"):
            # show status "Final", time just "Final"
            return "Final", "Final"
        if "in progress" in low or "qtr" in low or "ot" in low:
            return "Live", s
        if "pm" in low or "am" in low or "et" in low:
            # scheduled with tipoff time
            return "Scheduled", s
        return s, "TBD"

    cur = start
    delta = timedelta(days=1)

    while cur <= end:
        game_date_str = cur.strftime("%m/%d/%Y")

        try:
            sb = ScoreboardV2(game_date=game_date_str)
            header_df = sb.game_header.get_data_frame()
        except Exception as e:
            print(f"Error fetching schedule for {cur}: {e}")
            header_df = pd.DataFrame()

        for _, r in header_df.iterrows():
            gid = str(r.get("GAME_ID", "")).strip()
            if not gid:
                continue

            try:
                hid = int(r.get("HOME_TEAM_ID"))
                aid = int(r.get("VISITOR_TEAM_ID"))
            except Exception:
                continue

            # Filter by team if user picked one
            if team_id and team_id not in (hid, aid):
                continue

            status_raw = r.get("GAME_STATUS_TEXT", "") or r.get("GAME_STATUS", "")
            status, tm_txt = parse_status_time(status_raw)

            home = tm.get(hid, {"name": str(hid)})
            away = tm.get(aid, {"name": str(aid)})
            venue = r.get("ARENA_NAME", "") or ""

            home_score: Optional[int] = None
            away_score: Optional[int] = None

            if mode == "past":
                # 1) Try header points first
                home_score = _safe_int(r.get("PTS_HOME"))
                away_score = _safe_int(r.get("PTS_VISITOR"))

                # 2) If still missing but game is Final, try BoxScoreSummary
                if (home_score is None or away_score is None) and status.lower().startswith(
                    "final"
                ):
                    try:
                        sbox = BoxScoreSummaryV2(game_id=gid)
                        ldf = sbox.line_score.get_data_frame()
                        if not ldf.empty:
                            hrow = ldf[ldf["TEAM_ID"] == hid]
                            arow = ldf[ldf["TEAM_ID"] == aid]
                            if not hrow.empty:
                                home_score = _safe_int(hrow.iloc[0].get("PTS"))
                            if not arow.empty:
                                away_score = _safe_int(arow.iloc[0].get("PTS"))
                    except Exception as e:
                        print(f"Error fetching box score for {gid}: {e}")
                        # leave scores as None → UI shows "—"
            else:
                # FUTURE: keep scores as None
                home_score = None
                away_score = None

            rows.append(
                {
                    "date": cur.isoformat(),
                    "time": tm_txt,
                    "away": away["name"],
                    "home": home["name"],
                    "venue": venue,
                    "status": status,
                    "game_id": gid,
                    "away_score": away_score,
                    "home_score": home_score,
                }
            )

        cur += delta

    # Sort rows
    if mode == "past":
        rows.sort(key=lambda x: (x["date"], x["time"]), reverse=True)
    else:
        rows.sort(key=lambda x: (x["date"], x["time"]))

    label = "ALL" if not team_id else tm.get(team_id, {}).get("abbr", str(team_id))
    return {"team": label, "window": f"{start} to {end}", "rows": rows}


# --------------------------------------------------------------------
# SINGLE GAME PAGE (real data)
# --------------------------------------------------------------------


def fetch_nba_game(
    game_id: str,
    away_hint=None,
    home_hint=None,
    date_hint=None,
    time_hint=None,
) -> Dict[str, Any]:
    """
    NBA game detail page with score + top players.

    Uses BoxScoreSummaryV2 for scores and BoxScoreTraditionalV2 for player stats.
    """
    tm = _tm_map()

    try:
        box = BoxScoreSummaryV2(game_id=game_id)
        traditional_box = BoxScoreTraditionalV2(game_id=game_id)
    except Exception as e:
        print(f"Error fetching NBA game {game_id}: {e}")
        return {
            "title": "NBA Game Not Found",
            "subtitle": f"Game ID: {game_id}",
            "status": "Error",
            "when": date_hint or "",
            "away_name": away_hint or "Away",
            "home_name": home_hint or "Home",
            "away_score": 0,
            "home_score": 0,
            "top_players": [],
            "wp_home_pct": 50,
            "wp_away_pct": 50,
            "wp_note": "Win probability disabled for now.",
        }

    gdf = box.game_summary.get_data_frame()
    ldf = box.line_score.get_data_frame()

    if gdf.empty:
        return {
            "title": "NBA Game Not Found",
            "subtitle": f"Game ID: {game_id}",
            "status": "Unknown",
            "when": date_hint or "",
            "away_name": away_hint or "Away",
            "home_name": home_hint or "Home",
            "away_score": 0,
            "home_score": 0,
            "top_players": [],
            "wp_home_pct": 50,
            "wp_away_pct": 50,
            "wp_note": "Win probability disabled for now.",
        }

    row = gdf.iloc[0]
    status = row.get("GAME_STATUS_TEXT", "TBD")
    when = str(row.get("GAME_DATE_EST", ""))[:10]

    home_id = int(row.get("HOME_TEAM_ID"))
    away_id = int(row.get("VISITOR_TEAM_ID"))

    home = tm.get(home_id, {"name": home_hint or "Home"})
    away = tm.get(away_id, {"name": away_hint or "Away"})

    home_score = 0
    away_score = 0

    # Scores from line_score
    if not ldf.empty:
        hrow = ldf[ldf["TEAM_ID"] == home_id]
        arow = ldf[ldf["TEAM_ID"] == away_id]
        if not hrow.empty:
            home_score = _safe_int(hrow.iloc[0].get("PTS")) or 0
        if not arow.empty:
            away_score = _safe_int(arow.iloc[0].get("PTS")) or 0

    # Top players
    top_players: List[Dict[str, Any]] = []
    try:
        player_stats_df = traditional_box.player_stats.get_data_frame()
        if not player_stats_df.empty:
            top_players_data = player_stats_df.nlargest(5, "PTS")
            for _, player in top_players_data.iterrows():
                top_players.append(
                    {
                        "name": player.get("PLAYER_NAME", ""),
                        "team": tm.get(player.get("TEAM_ID"), {}).get("abbr", ""),
                        "pts": player.get("PTS", 0),
                        "reb": player.get("REB", 0),
                        "ast": player.get("AST", 0),
                    }
                )
    except Exception as e:
        print(f"Error fetching player stats for {game_id}: {e}")

    # Simple win probability based on final score
    if home_score > 0 or away_score > 0:
        total = home_score + away_score
        wp_home = round((home_score / total) * 100) if total > 0 else 50
        wp_away = 100 - wp_home
        wp_note = "Based on final score"
    else:
        wp_home = 50
        wp_away = 50
        wp_note = "Game not started or scores unavailable"

    return {
        "title": f"{away['name']} @ {home['name']}",
        "subtitle": f"Game ID: {game_id}",
        "status": status,
        "when": when,
        "away_name": away["name"],
        "home_name": home["name"],
        "away_score": away_score,
        "home_score": home_score,
        "top_players": top_players,
        "wp_home_pct": wp_home,
        "wp_away_pct": wp_away,
        "wp_note": wp_note,
    }
