#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import date, timedelta, datetime
from typing import Optional, List, Dict, Any
from flask import Flask, render_template_string, request, jsonify, abort
import statsapi
import plotly.graph_objects as go
import pandas as pd
import requests

app = Flask(__name__)

# FR-02: Team selection options used to populate the Team dropdown on the home page.
# 30 MLB clubs (id, name, abbr)
TEAMS: List[Dict[str, Any]] = sorted([
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
    {"id": 142, "name": "Minnesota Twins", "abbr": "MIN"},
    {"id": 143, "name": "Philadelphia Phillies", "abbr": "PHI"},
    {"id": 144, "name": "Atlanta Braves", "abbr": "ATL"},
    {"id": 145, "name": "Chicago White Sox", "abbr": "CWS"},
    {"id": 146, "name": "Miami Marlins", "abbr": "MIA"},
    {"id": 147, "name": "New York Yankees", "abbr": "NYY"},
    {"id": 158, "name": "Milwaukee Brewers", "abbr": "MIL"},
], key=lambda t: t["name"])

FUTURE_STATUSES = {"Scheduled", "Pre-Game", "Warmup", "Delayed Start", "Postponed", "If Necessary", "Preview"}
PAST_STATUSES = {"Final", "Game Over"}

# ---------- HELPERS ----------
# FR-14: Format ISO timestamps to local time; return "TBD" for missing/invalid values.
def fmt_local(dt_iso: str) -> str:
    if not dt_iso:
        return "TBD"
    try:
        if "T" not in dt_iso:
            dt = datetime.fromisoformat(dt_iso)
            return dt.strftime("%b %d")
        dt = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%b %d, %I:%M %p").lstrip("0")
    except Exception:
        return "TBD"

def dig(d: Any, path: List[Any], default: Any = None) -> Any:
    cur = d or {}
    for k in path:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur

# FR-18: Utility to choose the first non-empty value, supporting graceful fallbacks.
def first_nonempty(*vals, default: Any = "") -> Any:
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v
        if v not in (None, "", [], {}):
            return v
    return default

# ---------- DATA FUNCTIONS ----------
def _rows_from_sched(sched: List[Dict[str, Any]], status_filter: Optional[set]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for g in sched:
        status = g.get("status")
        if status_filter and status not in status_filter:
            continue
        time_local = g.get("game_time_local")
        if not time_local:
            dt_iso = g.get("game_datetime")
            time_local = fmt_local(dt_iso) if dt_iso else "TBD"
        rows.append({
            "date": g.get("game_date"),
            "time": time_local,
            "away": g.get("away_name"),
            "home": g.get("home_name"),
            "venue": g.get("venue_name"),
            "status": status,
            "game_pk": g.get("game_id"),
        })
    return rows
def fetch_raw_game_data(game_id: int) -> dict:
    """Directly fetches full game JSON from MLB Stats API."""
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
        print(f"[WARN] Failed to fetch raw game data: {r.status_code}")
        return {}
    except Exception as e:
        print(f"[ERROR] fetch_raw_game_data: {e}")
        return {}

def fetch_schedule(team_id: Optional[int], days: int, mode: str) -> Dict[str, Any]:
    today = date.today()
    if mode == "past":
        # FR-16: Build a past window and filter to completed games only.
        start = today - timedelta(days=days)
        end = today
        status_filter = PAST_STATUSES
    else:
        start = today
        end = today + timedelta(days=days)
        status_filter = FUTURE_STATUSES

    if team_id is None:
        sched = statsapi.schedule(start_date=start.isoformat(), end_date=end.isoformat())
        team_label = "ALL"
    else:
        sched = statsapi.schedule(start_date=start.isoformat(), end_date=end.isoformat(), team=team_id)
        team_label = next((t["abbr"] for t in TEAMS if t["id"] == team_id), str(team_id))
    rows = _rows_from_sched(sched, status_filter)
    if mode == "past":
        rows.reverse()
    return {"team": team_label, "window": f"{start} to {end}", "rows": rows}

def fetch_game_page(game_id: int, away_hint=None, home_hint=None, venue_hint=None, date_hint=None, time_hint=None):
    import traceback
    box, lscore, gmeta = {}, {}, {}

    # Primary calls
    try:
        box = statsapi.boxscore_data(game_id)
    except Exception as e:
        print(f"[WARN] boxscore_data failed: {e}")
    try:
        lscore = statsapi.linescore(game_id)
    except Exception as e:
        print(f"[WARN] linescore failed: {e}")
    try:
        gmeta = fetch_raw_game_data(game_id)
    except Exception as e:
        print(f"[WARN] game() failed: {e}")

    # Team names
    away_name = first_nonempty(
        dig(box, ["teamInfo", "away", "teamName"]),
        dig(lscore, ["teams", "away", "team", "name"]),
        dig(gmeta, ["gameData", "teams", "away", "name"]),
        away_hint, default="Away")
    home_name = first_nonempty(
        dig(box, ["teamInfo", "home", "teamName"]),
        dig(lscore, ["teams", "home", "team", "name"]),
        dig(gmeta, ["gameData", "teams", "home", "name"]),
        home_hint, default="Home")

    venue = first_nonempty(
        dig(box, ["teamInfo", "home", "venueName"]),
        dig(gmeta, ["gameData", "venue", "name"]),
        venue_hint, default="TBD")

    when_iso = first_nonempty(
        dig(lscore, ["gameDate"]),
        dig(gmeta, ["gameData", "datetime", "dateTime"]),
        date_hint, default="")
    when = fmt_local(when_iso) if when_iso else (date_hint or "TBD")

    status = first_nonempty(
        dig(lscore, ["status"]),
        dig(gmeta, ["gameData", "status", "detailedState"]),
        dig(box, ["gameStatus"]),
        default="Scheduled")

    prob_away = first_nonempty(
        dig(box, ["teamInfo", "away", "probablePitcher", "fullName"]),
        dig(gmeta, ["gameData", "probablePitchers", "away", "fullName"]),
        "TBD")
    prob_home = first_nonempty(
        dig(box, ["teamInfo", "home", "probablePitcher", "fullName"]),
        dig(gmeta, ["gameData", "probablePitchers", "home", "fullName"]),
        "TBD")

    # --- Scores (pull from linescore OR game)
    def safe_int(x):
        try:
            return int(x)
        except Exception:
            return "-"

    away_r = dig(lscore, ["teams", "away", "runs"])
    home_r = dig(lscore, ["teams", "home", "runs"])
    away_h = dig(lscore, ["teams", "away", "hits"])
    home_h = dig(lscore, ["teams", "home", "hits"])
    away_e = dig(lscore, ["teams", "away", "errors"])
    home_e = dig(lscore, ["teams", "home", "errors"])

    # fallback: liveData boxscore
    if away_r in (None, "-"):
        away_r = dig(gmeta, ["liveData", "boxscore", "teams", "away", "teamStats", "batting", "runs"])
        home_r = dig(gmeta, ["liveData", "boxscore", "teams", "home", "teamStats", "batting", "runs"])
        away_h = dig(gmeta, ["liveData", "boxscore", "teams", "away", "teamStats", "batting", "hits"])
        home_h = dig(gmeta, ["liveData", "boxscore", "teams", "home", "teamStats", "batting", "hits"])
        away_e = dig(gmeta, ["liveData", "boxscore", "teams", "away", "teamStats", "fielding", "errors"])
        home_e = dig(gmeta, ["liveData", "boxscore", "teams", "home", "teamStats", "fielding", "errors"])

    away_r, home_r = safe_int(away_r), safe_int(home_r)
    away_h, home_h = safe_int(away_h), safe_int(home_h)
    away_e, home_e = safe_int(away_e), safe_int(home_e)

        # --- Inning-by-inning linescore (supports all API versions)
    innings_headers, away_innings, home_innings = [], [], []

    # First try from linescore() result
    inns = dig(lscore, ["innings"], [])
    if not inns:
        # fallback to raw MLB JSON
        inns = dig(gmeta, ["liveData", "linescore", "innings"], [])

    if isinstance(inns, list) and inns:
        for inn in inns:
            num = inn.get("num") or len(innings_headers) + 1
            innings_headers.append(str(num))
            away_innings.append(str(dig(inn, ["away", "runs"], "-")))
            home_innings.append(str(dig(inn, ["home", "runs"], "-")))

    # Fallback if still empty (for weird archived games)
    if not innings_headers:
        innings_headers = [str(i) for i in range(1, 10)]
        away_innings = ["-"] * 9
        home_innings = ["-"] * 9


    # Return full page dict
    return {
        "title": f"{away_name} @ {home_name}",
        "subtitle": f"Game ID: {game_id}",
        "status": status,
        "venue": venue,
        "when": when,
        "prob_away": prob_away,
        "prob_home": prob_home,
        "away_name": away_name,
        "home_name": home_name,
        "away_r": away_r, "home_r": home_r,
        "away_h": away_h, "home_h": home_h,
        "away_e": away_e, "home_e": home_e,
        "innings": innings_headers,
        "away_innings": away_innings,
        "home_innings": home_innings,
    }





# ---------- HTML ----------

INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MLB Schedule</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    select, input, button { padding: 8px 10px; font-size: 14px; }
    h2 { margin-top: 28px; }
    table { border-collapse: collapse; width: 100%; margin-top: 12px; }
    th, td { border: 1px solid #ddd; padding: 8px; font-size: 14px; }
    th { background: #f5f5f5; text-align: left; }
    .muted { color: #666; font-size: 13px; margin-left: 8px; }
    .tbd { color: #777; font-style: italic; }
    a { color: #0a58ca; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .section { margin-top: 20px; }
  </style>
</head>
<body>
  <h1>MLB Games</h1>

  <!-- Shared controls -->
  <div class="row">
    <label>Team:</label>
    <select id="team">
      <option value="">ALL TEAMS</option>
      {% for t in teams %}
      <option value="{{ t.id }}">{{ t.name }} ({{ t.abbr }})</option>
      {% endfor %}
    </select>
  </div>

  <!-- Upcoming -->
  <div class="section">
    <h2>Upcoming Games</h2>
    <div class="row">
      <!-- FR-03: User enters “Days ahead” for future schedule queries. -->
      <label>Days ahead:</label>
      <input id="daysAhead" type="number" min="1" value="10" style="width:90px">
      <button id="loadUpcoming">Load</button>
      <span id="metaUpcoming" class="muted"></span>
    </div>

    <!-- FR-07: Upcoming table columns for Date, Time, Matchup, Venue, Status. -->
    <table id="tblUpcoming" style="display:none">
      <thead>
        <tr>
          <th>Date</th><th>Time</th><th>Matchup</th><th>Venue</th><th>Status</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

  <!-- Previous -->
  <div class="section">
    <h2>Previous Games</h2>
    <div class="row">
      <!-- FR-05: User enters “Days back” for past schedule queries. -->
      <label>Days back:</label>
      <input id="daysBack" type="number" min="1" value="7" style="width:90px">
      <button id="loadPrevious">Load</button>
      <span id="metaPrevious" class="muted"></span>
    </div>

    <!-- FR-08: Previous table columns for Date, Time, Matchup, Venue, Status. -->
    <table id="tblPrevious" style="display:none">
      <thead>
        <tr>
          <th>Date</th><th>Time</th><th>Matchup</th><th>Venue</th><th>Status</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

  <script>
    const $ = (sel) => document.querySelector(sel);
    const teamSel = $("#team");

    // FR-04: Clicking “Load” fetches and renders the upcoming (future) schedule.
    async function loadUpcoming() {
      const teamId = teamSel.value;
      const days = parseInt($("#daysAhead").value || "10", 10);
      const meta = $("#metaUpcoming");
      const tbl = $("#tblUpcoming");
      const tbody = $("#tblUpcoming tbody");

      meta.textContent = "Loading...";
      tbody.innerHTML = "";
      tbl.style.display = "none";

      const params = new URLSearchParams({ mode: "future", days: String(days) });
      if (teamId) params.set("teamId", teamId);

      const res = await fetch("/api/schedule?" + params.toString());
      // FR-20: If the request fails, present a user-visible error message.
      if (!res.ok) { meta.textContent = "Error loading schedule"; return; }
      const data = await res.json();
      // FR-17: Show a meta summary (Team | Window | Rows) after successful load.
      meta.textContent = `Team: ${data.team} | Window: ${data.window} | Rows: ${data.rows.length}`;

      if (!data.rows.length) { tbl.style.display = "none"; return; }

      for (const g of data.rows) {
        const tr = document.createElement("tr");
        const timeCell = g.time && g.time !== "TBD" ? g.time : "<span class='tbd'>TBD</span>";
        const matchup = `${g.away ?? ""} @ ${g.home ?? ""}`;
        // FR-09: Matchup is a clickable link to the game details page.
        const qs = new URLSearchParams({ a: g.away ?? "", h: g.home ?? "", v: g.venue ?? "", d: g.date ?? "", t: g.time ?? "" });
        tr.innerHTML = `
          <td>${g.date ?? ""}</td>
          <td>${timeCell}</td>
          <td><a href="/game/${g.game_pk}?${qs.toString()}" target="_blank" rel="noopener">${matchup}</a></td>
          <td>${g.venue ?? ""}</td>
          <td>${g.status ?? ""}</td>
        `;
        tbody.appendChild(tr);
      }
      tbl.style.display = "";
    }

    // FR-06: Clicking “Load” fetches and renders the previous (past) schedule.
    async function loadPrevious() {
      const teamId = teamSel.value;
      const days = parseInt($("#daysBack").value || "7", 10);
      const meta = $("#metaPrevious");
      const tbl = $("#tblPrevious");
      const tbody = $("#tblPrevious tbody");

      meta.textContent = "Loading...";
      tbody.innerHTML = "";
      tbl.style.display = "none";

      const params = new URLSearchParams({ mode: "past", days: String(days) });
      if (teamId) params.set("teamId", teamId);

      const res = await fetch("/api/schedule?" + params.toString());
      if (!res.ok) { meta.textContent = "Error loading schedule"; return; }
      const data = await res.json();
      meta.textContent = `Team: ${data.team} | Window: ${data.window} | Rows: ${data.rows.length}`;

      // FR-19: Empty-state handling — hide table if there are no rows.
      if (!data.rows.length) { tbl.style.display = "none"; return; }

      for (const g of data.rows) {
        const tr = document.createElement("tr");
        const timeCell = g.time && g.time !== "TBD" ? g.time : "<span class='tbd'>TBD</span>";
        const matchup = `${g.away ?? ""} @ ${g.home ?? ""}`;
        const qs = new URLSearchParams({ a: g.away ?? "", h: g.home ?? "", v: g.venue ?? "", d: g.date ?? "", t: g.time ?? "" });
        tr.innerHTML = `
          <td>${g.date ?? ""}</td>
          <td>${timeCell}</td>
          <td><a href="/game/${g.game_pk}?${qs.toString()}" target="_blank" rel="noopener">${matchup}</a></td>
          <td>${g.venue ?? ""}</td>
          <td>${g.status ?? ""}</td>
        `;
        tbody.appendChild(tr);
      }
      tbl.style.display = "";
    }

    $("#loadUpcoming").addEventListener("click", loadUpcoming);
    $("#loadPrevious").addEventListener("click", loadPrevious);

    // initial load
    loadUpcoming();
    loadPrevious();
  </script>
</body>
</html>
"""

GAME_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      margin: 24px;
    }
    a {
      color: #0a58ca;
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    .muted {
      color: #666;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
    }
    .card {
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 16px;
    }
    h1 {
      margin: 0 0 6px;
      font-size: 22px;
    }
    h2 {
      margin: 12px 0 6px;
      font-size: 18px;
    }
    table {
      border-collapse: collapse;
      width: 100%;
    }
    th, td {
      border: 1px solid #eee;
      padding: 6px 8px;
      font-size: 14px;
      text-align: center;
    }
    th {
      background: #f8f8f8;
      text-align: center;
    }
    .left {
      text-align: left;
    }
  </style>
</head>
<body>
  <!-- FR-10: Back link to return from details to the home schedule. -->
  <p><a href="/" >&larr; Back to schedule</a></p>
  <h1>{{ title }}</h1>
  <p class="muted">{{ subtitle }}</p>

  <div class="grid">
    <div class="card">
      <!-- FR-11: Details page shows Status, Date/Time, Venue, and Probable Pitchers. -->
      <h2>Meta</h2>
      <div><strong>Status:</strong> {{ status }}</div>
      <div><strong>Date/Time:</strong> {{ when }}</div>
      <div><strong>Venue:</strong> {{ venue }}</div>
      <div><strong>Probable Pitchers:</strong> {{ prob_away }} (Away) · {{ prob_home }} (Home)</div>

      <p>
        <a href="/game/{{ subtitle.split(':')[-1].strip() }}/charts" target="_blank">
          ⚾ View Advanced Matchup Analytics →
        </a>
      </p>
    </div>

    <div class="card">
      <!-- FR-12: Display Runs/Hits/Errors totals when available. -->
      <h2>Score (if available)</h2>
      <table>
        <thead>
          <tr><th class="left">Team</th><th>R</th><th>H</th><th>E</th></tr>
        </thead>
        <tbody>
          <tr><td class="left">{{ away_name }}</td><td>{{ away_r }}</td><td>{{ away_h }}</td><td>{{ away_e }}</td></tr>
          <tr><td class="left">{{ home_name }}</td><td>{{ home_r }}</td><td>{{ home_h }}</td><td>{{ home_e }}</td></tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <!-- FR-13: Inning-by-inning linescore table (if provided by API). -->
      <h2>Linescore by Inning</h2>
      {% if innings and innings|length > 0 %}
      <table>
        <thead>
          <tr>
            <th class="left">Team</th>
            {% for inn in innings %}
              <th>{{ inn }}</th>
            {% endfor %}
            <th>R</th><th>H</th><th>E</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="left">{{ away_name }}</td>
            {% for r in away_innings %}
              <td>{{ r }}</td>
            {% endfor %}
            <td>{{ away_r }}</td><td>{{ away_h }}</td><td>{{ away_e }}</td>
          </tr>
          <tr>
            <td class="left">{{ home_name }}</td>
            {% for r in home_innings %}
              <td>{{ r }}</td>
            {% endfor %}
            <td>{{ home_r }}</td><td>{{ home_h }}</td><td>{{ home_e }}</td>
          </tr>
        </tbody>
      </table>
      {% else %}
        <p class="muted">No inning-by-inning linescore available yet.</p>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""

# ---------- ROUTES ----------
# FR-01: Home route renders the main schedule UI (index page).
@app.route("/")
def index():
    return render_template_string(INDEX_HTML, teams=TEAMS)

# FR-15: JSON API endpoint serving upcoming/past schedules based on query params.
@app.route("/api/schedule")
def api_schedule():
    team_id = request.args.get("teamId", type=int)
    days = request.args.get("days", default=10, type=int)
    mode = request.args.get("mode", default="future")
    return jsonify(fetch_schedule(team_id, days, mode))

@app.route("/game/<int:game_id>")
def game_page(game_id: int):
    try:
        page = fetch_game_page(
            game_id,
            away_hint=request.args.get("a"),
            home_hint=request.args.get("h"),
            venue_hint=request.args.get("v"),
            date_hint=request.args.get("d"),
            time_hint=request.args.get("t"),
        )
    except Exception:
        abort(404)
    return render_template_string(GAME_HTML, **page)

# ---------- NEW ANALYTICS ROUTE ----------
@app.route("/game/<int:game_id>/charts")
def game_charts(game_id):
    import datetime
    try:
        gmeta = statsapi.boxscore_data(game_id)
    except Exception as e:
        return f"<h3>Error fetching game data: {e}</h3>"

    # Extract team info
    away_team_id = dig(gmeta, ["teamInfo", "away", "id"])
    home_team_id = dig(gmeta, ["teamInfo", "home", "id"])
    away_name = dig(gmeta, ["teamInfo", "away", "teamName"], "Away")
    home_name = dig(gmeta, ["teamInfo", "home", "teamName"], "Home")

    # --- 1️⃣ Batting averages vs pitcher ---
    batters, avgs = ["Unavailable"], [0]
    try:
        prob_home = dig(gmeta, ["teamInfo", "home", "id"])
        pdata = statsapi.player_stat_data(prob_home, group="hitting", type="season")
        df = pd.DataFrame(pdata["stats"])
        df["avg"] = pd.to_numeric(df["avg"], errors="coerce")
        df = df.sort_values("avg", ascending=False).head(5)
        batters, avgs = df["playerFullName"].tolist(), df["avg"].tolist()
    except Exception:
        pass
    fig1 = go.Figure([go.Bar(x=batters, y=avgs, marker_color="steelblue")])
    fig1.update_layout(
        title="Top 5 Batters (Current Season AVG)",
        xaxis_title="Batter",
        yaxis_title="AVG",
        template="plotly_white",
        height=400
    )

    # --- 2️⃣ Recent Team ERA / Runs Allowed Trend ---
    eras = []
    try:
        today = datetime.date.today()
        start = today - datetime.timedelta(days=10)
        home_sched = statsapi.schedule(start_date=start.isoformat(), end_date=today.isoformat(), team=home_team_id)
        eras = [g["away_score"] for g in home_sched if g["status"] == "Final"][-5:]
    except Exception:
        pass
    if not eras:
        eras = [0] * 5
    fig2 = go.Figure([go.Scatter(y=eras, mode="lines+markers", line_color="firebrick")])
    fig2.update_layout(
        title="Recent Team Performance (Runs Allowed per Game)",
        yaxis_title="Runs Allowed",
        template="plotly_white",
        height=400
    )

    # --- 3️⃣ Team Run Averages (Last 10 Games) ---
    try:
        today = datetime.date.today()
        start = today - datetime.timedelta(days=15)
        away_sched = statsapi.schedule(start_date=start.isoformat(), end_date=today.isoformat(), team=away_team_id)
        home_sched = statsapi.schedule(start_date=start.isoformat(), end_date=today.isoformat(), team=home_team_id)

        def avg_runs(games, side):
            scores = [int(g["away_score"] if side == "away" else g["home_score"]) for g in games if g["status"] == "Final"]
            return sum(scores) / len(scores) if scores else 0

        away_avg = avg_runs(away_sched, "away")
        home_avg = avg_runs(home_sched, "home")
    except Exception:
        away_avg = home_avg = 0

    fig3 = go.Figure([go.Bar(
        x=[away_name, home_name],
        y=[away_avg, home_avg],
        text=[f"{away_avg:.2f}", f"{home_avg:.2f}"],
        textposition="auto",
        marker_color=["royalblue", "crimson"]
    )])
    fig3.update_layout(
        title="Average Runs Scored (Last 10 Games)",
        yaxis_title="Runs",
        template="plotly_white",
        height=400
    )

        # --- 4️⃣ First Inning Run Frequency (Last 20 Games) ---
    def first_inning_score_ratio(games, side):
        count = total = 0
        for g in games:
            if g.get("status") != "Final" or not g.get("game_id"):
                continue
            total += 1
            try:
                lscore = statsapi.linescore(g["game_id"])
                # ✅ Make sure the response is a dictionary
                if not isinstance(lscore, dict):
                    continue
                innings = lscore.get("innings", [])
                if not innings or not isinstance(innings, list):
                    continue
                first_inning = innings[0]
                if not isinstance(first_inning, dict):
                    continue
                team_runs = first_inning.get(side, {}).get("runs", 0)
                if team_runs and team_runs > 0:
                    count += 1
            except Exception as e:
                print(f"[WARN] skipping game {g.get('game_id')}: {e}")
                continue

        print(f"[DEBUG] {side} -> {count}/{total} games with 1st-inning runs")
        return (count / total) * 100 if total > 0 else 0

    try:
        today = datetime.date.today()
        start = today - datetime.timedelta(days=20)
        away_sched = statsapi.schedule(start_date=start.isoformat(), end_date=today.isoformat(), team=away_team_id)
        home_sched = statsapi.schedule(start_date=start.isoformat(), end_date=today.isoformat(), team=home_team_id)

        away_first = first_inning_score_ratio(away_sched, "away")
        home_first = first_inning_score_ratio(home_sched, "home")

        print(f"[DEBUG] {away_name} 1st-inning %: {away_first:.1f}, {home_name}: {home_first:.1f}")
    except Exception as e:
        print("Error computing first-inning stats:", e)
        away_first = home_first = 0

    # Create chart
    fig4 = go.Figure([
        go.Bar(
            x=[away_name, home_name],
            y=[away_first, home_first],
            text=[f"{away_first:.1f}%", f"{home_first:.1f}%"],
            textposition="auto",
            marker_color=["lightskyblue", "indianred"]
        )
    ])
    fig4.update_layout(
        title="First-Inning Run Frequency (Last 20 Games)",
        yaxis_title="Percentage of Games with 1st-Inning Runs",
        template="plotly_white",
        height=400
    )


    # --- Combine HTML ---
    return f"""
    <html>
      <head>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
          body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 40px; }}
          h1 {{ margin-bottom: 30px; }}
          a {{ color: #0a58ca; text-decoration: none; }}
          a:hover {{ text-decoration: underline; }}
          .btn {{ display:inline-block;padding:8px 14px;background:#0a58ca;color:white;border-radius:6px;margin-bottom:20px; }}
          .btn:hover {{ background:#0949a2; }}
          .chart {{ margin-bottom: 40px; }}
        </style>
      </head>
      <body>
        <a href="/game/{game_id}" class="btn">← Back to Game</a>
        <h1>⚾ Advanced Matchup Analytics</h1>
        <div id='fig1' class='chart'></div>
        <div id='fig2' class='chart'></div>
        <div id='fig3' class='chart'></div>
        <div id='fig4' class='chart'></div>
        <script>
          Plotly.newPlot('fig1', {fig1.to_json()});
          Plotly.newPlot('fig2', {fig2.to_json()});
          Plotly.newPlot('fig3', {fig3.to_json()});
          Plotly.newPlot('fig4', {fig4.to_json()});
        </script>
      </body>
    </html>
    """

if __name__ == "__main__":
    app.run(debug=True)
