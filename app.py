#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import date, timedelta, datetime
from typing import Optional, List, Dict, Any
from flask import Flask, render_template_string, request, jsonify, abort
import statsapi

app = Flask(__name__)

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

FUTURE_STATUSES = {
    "Scheduled", "Pre-Game", "Warmup", "Delayed Start", "Postponed", "If Necessary", "Preview"
}
PAST_STATUSES = {"Final", "Game Over"}  # keep past list clean (finished games only)

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
      <label>Days ahead:</label>
      <input id="daysAhead" type="number" min="1" value="10" style="width:90px">
      <button id="loadUpcoming">Load</button>
      <span id="metaUpcoming" class="muted"></span>
    </div>

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
      <label>Days back:</label>
      <input id="daysBack" type="number" min="1" value="7" style="width:90px">
      <button id="loadPrevious">Load</button>
      <span id="metaPrevious" class="muted"></span>
    </div>

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

    // UPCOMING
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
      if (!res.ok) { meta.textContent = "Error loading schedule"; return; }
      const data = await res.json();
      meta.textContent = `Team: ${data.team} | Window: ${data.window} | Rows: ${data.rows.length}`;

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

    // PREVIOUS
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
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }
    a { color: #0a58ca; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .muted { color: #666; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 16px; }
    h1 { margin: 0 0 6px; font-size: 22px; }
    h2 { margin: 12px 0 6px; font-size: 18px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #eee; padding: 6px 8px; font-size: 14px; text-align: center; }
    th { background: #f8f8f8; text-align: center; }
    .left { text-align: left; }
  </style>
</head>
<body>
  <p><a href="/" >&larr; Back to schedule</a></p>
  <h1>{{ title }}</h1>
  <p class="muted">{{ subtitle }}</p>

  <div class="grid">
    <div class="card">
      <h2>Meta</h2>
      <div><strong>Status:</strong> {{ status }}</div>
      <div><strong>Date/Time:</strong> {{ when }}</div>
      <div><strong>Venue:</strong> {{ venue }}</div>
      <div><strong>Probable Pitchers:</strong> {{ prob_away }} (Away) &middot; {{ prob_home }} (Home)</div>
    </div>

    <div class="card">
      <h2>Score (if available)</h2>
      <table>
        <thead><tr><th class="left">Team</th><th>R</th><th>H</th><th>E</th></tr></thead>
        <tbody>
          <tr><td class="left">{{ away_name }}</td><td>{{ away_r }}</td><td>{{ away_h }}</td><td>{{ away_e }}</td></tr>
          <tr><td class="left">{{ home_name }}</td><td>{{ home_r }}</td><td>{{ home_h }}</td><td>{{ home_e }}</td></tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>Linescore by Inning</h2>
      {% if innings and innings|length > 0 %}
      <table>
        <thead>
          <tr>
            <th class="left">Team</th>
            {% for inn in innings %}<th>{{ inn }}</th>{% endfor %}
            <th>R</th><th>H</th><th>E</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="left">{{ away_name }}</td>
            {% for r in away_innings %}<td>{{ r }}</td>{% endfor %}
            <td>{{ away_r }}</td><td>{{ away_h }}</td><td>{{ away_e }}</td>
          </tr>
          <tr>
            <td class="left">{{ home_name }}</td>
            {% for r in home_innings %}<td>{{ r }}</td>{% endfor %}
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

# ---------- HELPERS ----------

def fmt_local(dt_iso: str) -> str:
    """Format ISO timestamp into local time. Works with date-only and full ISO (Z/offset)."""
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

def fetch_schedule(team_id: Optional[int], days: int, mode: str) -> Dict[str, Any]:
    today = date.today()
    if mode == "past":
        start = today - timedelta(days=days)
        end = today
        status_filter = PAST_STATUSES
    else:  # future (default)
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

    # API returns ascending; for past, show most recent first
    if mode == "past":
        rows.reverse()

    return {"team": team_label, "window": f"{start} to {end}", "rows": rows}

def fetch_game_page(
    game_id: int,
    away_hint: Optional[str] = None,
    home_hint: Optional[str] = None,
    venue_hint: Optional[str] = None,
    date_hint: Optional[str] = None,
    time_hint: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        gmeta = statsapi.game(game_id)
    except Exception:
        gmeta = {}
    try:
        box = statsapi.boxscore_data(game_id)
    except Exception:
        box = {}
    try:
        lscore = statsapi.linescore(game_id)
    except Exception:
        lscore = {}

    away_name = first_nonempty(
        dig(gmeta, ["gameData", "teams", "away", "name"]),
        dig(gmeta, ["gameData", "teams", "away", "teamName"]),
        dig(box,   ["teamInfo", "away", "name"]),
        away_hint,
        default="Away",
    )
    home_name = first_nonempty(
        dig(gmeta, ["gameData", "teams", "home", "name"]),
        dig(gmeta, ["gameData", "teams", "home", "teamName"]),
        dig(box,   ["teamInfo", "home", "name"]),
        home_hint,
        default="Home",
    )

    status = first_nonempty(
        dig(gmeta, ["gameData", "status", "detailedState"]),
        dig(gmeta, ["gameData", "status", "abstractGameState"]),
        default="Scheduled",
    )
    venue = first_nonempty(
        dig(gmeta, ["gameData", "venue", "name"]),
        dig(box,   ["info", "venueName"]),
        venue_hint,
        default="",
    )
    when_iso = first_nonempty(
        dig(gmeta, ["gameData", "datetime", "dateTime"]),
        gmeta.get("gameDate"),
        dig(gmeta, ["gameData", "datetime", "officialDate"]),
        default="",
    )
    when = fmt_local(when_iso)
    if when == "TBD" and date_hint:
        when = f"{date_hint}, {time_hint}" if (time_hint and time_hint != "TBD") else date_hint

    prob_away = first_nonempty(
        dig(gmeta, ["gameData", "probablePitchers", "away", "fullName"]),
        dig(gmeta, ["gameData", "probablePitchers", "away", "name"]),
        default="TBD",
    )
    prob_home = first_nonempty(
        dig(gmeta, ["gameData", "probablePitchers", "home", "fullName"]),
        dig(gmeta, ["gameData", "probablePitchers", "home", "name"]),
        default="TBD",
    )

    away_lines = dig(box, ["teams", "away"], {})
    home_lines = dig(box, ["teams", "home"], {})
    away_r = dig(away_lines, ["teamStats", "batting", "runs"], "-")
    away_h = dig(away_lines, ["teamStats", "batting", "hits"], "-")
    away_e = dig(away_lines, ["teamStats", "fielding", "errors"], "-")
    home_r = dig(home_lines, ["teamStats", "batting", "runs"], "-")
    home_h = dig(home_lines, ["teamStats", "batting", "hits"], "-")
    home_e = dig(home_lines, ["teamStats", "fielding", "errors"], "-")

    innings_headers: List[str] = []
    away_innings: List[str] = []
    home_innings: List[str] = []
    inns = lscore.get("innings") if isinstance(lscore, dict) else None
    if isinstance(inns, list) and len(inns) > 0:
        for inn in inns:
            num = inn.get("num")
            innings_headers.append(str(num))
            away_innings.append(str(dig(inn, ["away", "runs"], "-")))
            home_innings.append(str(dig(inn, ["home", "runs"], "-")))

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
        "away_r": away_r if away_r not in (None, "") else "-",
        "away_h": away_h if away_h not in (None, "") else "-",
        "away_e": away_e if away_e not in (None, "") else "-",
        "home_r": home_r if home_r not in (None, "") else "-",
        "home_h": home_h if home_h not in (None, "") else "-",
        "home_e": home_e if home_e not in (None, "") else "-",
        "innings": innings_headers,
        "away_innings": away_innings,
        "home_innings": home_innings,
    }

# ---------- ROUTES ----------

@app.route("/")
def index():
    return render_template_string(INDEX_HTML, teams=TEAMS)

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

if __name__ == "__main__":
    # Optional: silence urllib3 LibreSSL warning (harmless)
    # import warnings; warnings.filterwarnings("ignore")
    app.run(debug=True)
