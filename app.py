#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import date, timedelta, datetime
from typing import Optional, List, Dict, Any

from flask import Flask, render_template_string, request, jsonify, abort
import statsapi
import plotly.graph_objects as go
import math          

from services.mlb_service import (
    TEAMS,
    fetch_schedule,
    fetch_game_page,
    team_abbr_from_name,
)
from services.nba_service import (
    NBA_TEAMS,
    fetch_nba_schedule,
    fetch_nba_game,
)

app = Flask(__name__)

# =========================
# HOME PAGE (MLB / NBA CHOICE)
# =========================

HOME_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>EZSportsPicks</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      margin: 0;
      min-height: 100vh;
      background-image: url('/static/images/main.jpeg');
      background-size: cover;
      background-position: center;
      background-attachment: fixed;
      color: #fff;
      position: relative;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.60);
      z-index: -1;
    }
    .container {
      max-width: 920px;
      margin: 0 auto;
      padding: 40px 20px;
    }
    header { text-align: center; margin-bottom: 40px; }
    h1 {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 56px;
      letter-spacing: 3px;
      margin: 0 0 8px;
      text-transform: uppercase;
    }
    .subtitle { font-size: 16px; opacity: 0.9; }
    .cards {
      display: flex;
      flex-wrap: wrap;
      gap: 24px;
      justify-content: center;
    }
    .card {
      background: rgba(15,15,20,0.85);
      border-radius: 18px;
      padding: 26px 30px;
      min-width: 260px;
      max-width: 360px;
      text-align: left;
      backdrop-filter: blur(8px);
      border: 1px solid rgba(255,255,255,0.14);
      box-shadow: 0 18px 45px rgba(0,0,0,0.4);
    }
    .card h2 {
      font-family: 'Bebas Neue', sans-serif;
      letter-spacing: 2px;
      margin: 0 0 8px;
      font-size: 34px;
    }
    .tag {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      padding: 4px 10px;
      border-radius: 999px;
      text-transform: uppercase;
      letter-spacing: 1px;
      background: rgba(255,255,255,0.08);
      margin-bottom: 10px;
    }
    .tag span.dot {
      width: 8px; height: 8px; border-radius: 999px; background: #22c55e;
    }
    .card p { font-size: 14px; opacity: 0.9; margin-bottom: 18px; }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 18px;
      border-radius: 999px;
      border: none;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      color: #fff;
      transition: transform 0.08s ease, box-shadow 0.08s ease, background 0.15s ease;
    }
    .btn span.icon { margin-left: 6px; font-size: 15px; }
    .btn-mlb {
      background: linear-gradient(135deg, #f97316, #facc15);
      box-shadow: 0 8px 20px rgba(248, 181, 0, 0.35);
    }
    .btn-nba {
      background: linear-gradient(135deg, #22d3ee, #6366f1);
      box-shadow: 0 8px 20px rgba(56, 189, 248, 0.35);
    }
    .btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 12px 30px rgba(0,0,0,0.45);
    }
    .btn:active {
      transform: translateY(0);
      box-shadow: 0 6px 16px rgba(0,0,0,0.45);
    }
    footer {
      margin-top: 40px;
      text-align: center;
      font-size: 12px;
      opacity: 0.8;
    }
    @media (min-width: 780px) {
      .cards { justify-content: space-between; }
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Sports Dashboard</h1>
      <div class="subtitle">Choose a league to explore schedules, box scores, and analytics.</div>
    </header>

    <div class="cards">
      <div class="card">
        <div class="tag"><span class="dot"></span><span>Baseball • MLB</span></div>
        <h2>MLB Games</h2>
        <p>See upcoming and recent MLB games, box scores, win probabilities, and advanced charts.</p>
        <a href="/mlb" class="btn btn-mlb">Open MLB Dashboard <span class="icon">→</span></a>
      </div>

      <div class="card">
        <div class="tag"><span class="dot"></span><span>Basketball • NBA</span></div>
        <h2>NBA Games</h2>
        <p>Browse NBA matchups, scores, top players, and simple win probabilities.</p>
        <a href="/nba" class="btn btn-nba">Open NBA Dashboard <span class="icon">→</span></a>
      </div>
    </div>

    <footer>Built for fun sports analytics</footer>
  </div>
</body>
</html>
"""

# =========================
# MLB MAIN PAGE
# =========================

INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MLB Schedule</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap" rel="stylesheet">
  <style>
    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      margin: 24px;
      background-image: url('/static/images/wallpaper.jpeg');
      background-size: cover;
      background-position: center;
      background-attachment: fixed;
      color: #fff;
      position: relative;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.60);
      z-index: -1;
    }
    h1, h2 {
      font-family: 'Bebas Neue', sans-serif;
      text-transform: uppercase;
      letter-spacing: 1px;
      text-shadow: 0 2px 4px rgba(0, 0, 0, 0.7);
    }
    h1 {
      font-size: 60px;
      color: #ffffff;
      letter-spacing: 2px;
      margin-bottom: 10px;
    }
    h2 {
      font-size: 34px;
      color: #f2f2f2;
      margin-top: 30px;
      margin-bottom: 10px;
    }
    select, input, button {
      padding: 8px 10px;
      font-size: 14px;
      border-radius: 4px;
      border: 1px solid #ccc;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      margin-top: 12px;
      background: rgba(255, 255, 255, 0.1);
      backdrop-filter: blur(4px);
      color: #fff;
    }
    th, td {
      border: 1px solid rgba(255, 255, 255, 0.3);
      padding: 8px;
      font-size: 14px;
    }
    th {
      background: rgba(0, 0, 0, 0.4);
      color: #fff;
    }
    a {
      color: #4da3ff;
      text-decoration: none;
      font-weight: 500;
    }
    a:hover { text-decoration: underline; }
    .muted {
      color: #ddd;
      font-size: 13px;
      margin-left: 8px;
    }
    .section { margin-top: 20px; }
  </style>
</head>
<body>
  <p><a href="/" style="color:#fff;text-decoration:none;">← Back to Sports Home</a></p>
  <h1>MLB Games</h1>

  <div class="row">
    <label>Team:</label>
    <select id="team">
      <option value="">ALL TEAMS</option>
      {% for t in teams %}
      <option value="{{ t.id }}">{{ t.name }} ({{ t.abbr }})</option>
      {% endfor %}
    </select>
  </div>

  <div class="section">
    <h2>Upcoming Games</h2>
    <div class="row">
      <label>Days ahead:</label>
      <input id="daysAhead" type="number" min="1" value="7" style="width:90px">
      <button id="loadUpcoming">Load</button>
      <span id="metaUpcoming" class="muted"></span>
    </div>

    <table id="tblUpcoming" style="display:none">
      <thead>
        <tr>
          <th>Date</th><th>Time</th><th>Matchup</th><th>Score</th><th>Venue</th><th>Status</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

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
          <th>Date</th><th>Time</th><th>Matchup</th><th>Score</th><th>Venue</th><th>Status</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

  <script>
    const $ = (sel) => document.querySelector(sel);
    const teamSel = $("#team");

    async function loadUpcoming() {
      const teamId = teamSel.value;
      const days = parseInt($("#daysAhead").value || "7", 10);
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
        const scoreCell = (g.away_score != null && g.home_score != null)
          ? `${g.away_score} - ${g.home_score}`
          : "—";
        const qs = new URLSearchParams({
          a: g.away ?? "",
          h: g.home ?? "",
          v: g.venue ?? "",
          d: g.date ?? "",
          t: g.time ?? ""
        });
        tr.innerHTML = `
          <td>${g.date ?? ""}</td>
          <td>${timeCell}</td>
          <td><a href="/game/${g.game_pk}?${qs.toString()}" target="_blank" rel="noopener">${matchup}</a></td>
          <td>${scoreCell}</td>
          <td>${g.venue ?? ""}</td>
          <td>${g.status ?? ""}</td>
        `;
        tbody.appendChild(tr);
      }
      tbl.style.display = "";
    }

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
        const scoreCell = (g.away_score != null && g.home_score != null)
          ? `${g.away_score} - ${g.home_score}`
          : "—";
        const qs = new URLSearchParams({
          a: g.away ?? "",
          h: g.home ?? "",
          v: g.venue ?? "",
          d: g.date ?? "",
          t: g.time ?? ""
        });
        tr.innerHTML = `
          <td>${g.date ?? ""}</td>
          <td>${timeCell}</td>
          <td><a href="/game/${g.game_pk}?${qs.toString()}" target="_blank" rel="noopener">${matchup}</a></td>
          <td>${scoreCell}</td>
          <td>${g.venue ?? ""}</td>
          <td>${g.status ?? ""}</td>
        `;
        tbody.appendChild(tr);
      }
      tbl.style.display = "";
    }

    $("#loadUpcoming").addEventListener("click", loadUpcoming);
    $("#loadPrevious").addEventListener("click", loadPrevious);

    loadUpcoming();
    loadPrevious();
  </script>
</body>
</html>
"""

# =========================
# NBA MAIN PAGE
# =========================

NBA_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>NBA Schedule</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap" rel="stylesheet">
  <style>
    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      margin: 24px;
      background-image: url('/static/images/basketball.jpeg');
      background-size: cover;
      background-position: center;
      background-attachment: fixed;
      color: #fff;
      position: relative;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.60);
      z-index: -1;
    }
    h1, h2 {
      font-family: 'Bebas Neue', sans-serif;
      text-transform: uppercase;
      letter-spacing: 1px;
      text-shadow: 0 2px 4px rgba(0, 0, 0, 0.7);
    }
    h1 {
      font-size: 60px;
      color: #ffffff;
      letter-spacing: 2px;
      margin-bottom: 10px;
    }
    h2 {
      font-size: 34px;
      color: #f2f2f2;
      margin-top: 30px;
      margin-bottom: 10px;
    }
    select, input, button {
      padding: 8px 10px;
      font-size: 14px;
      border-radius: 4px;
      border: 1px solid #ccc;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      margin-top: 12px;
      background: rgba(255, 255, 255, 0.1);
      backdrop-filter: blur(4px);
      color: #fff;
    }
    th, td {
      border: 1px solid rgba(255, 255, 255, 0.3);
      padding: 8px;
      font-size: 14px;
    }
    th {
      background: rgba(0, 0, 0, 0.4);
      color: #fff;
    }
    a { color: #4da3ff; text-decoration: none; font-weight: 500; }
    a:hover { text-decoration: underline; }
    .muted { color: #ddd; font-size: 13px; margin-left: 8px; }
    .section { margin-top: 20px; }
    .final { color: #90EE90; font-weight: bold; }
    .scheduled { color: #FFD700; }
    .live { color: #FF6B6B; font-weight: bold; }
  </style>
</head>
<body>
  <p><a href="/" style="color:#fff;text-decoration:none;">← Back to Sports Home</a></p>
  <h1>NBA Games</h1>

  <div class="row">
    <label>Team:</label>
    <select id="team">
      <option value="">ALL TEAMS</option>
      {% for t in teams %}
      <option value="{{ t.id }}">{{ t.name }} ({{ t.abbr }})</option>
      {% endfor %}
    </select>
  </div>

  <div class="section">
    <h2>Upcoming Games</h2>
    <div class="row">
      <label>Days ahead:</label>
      <input id="daysAhead" type="number" min="1" value="7" style="width:90px">
      <button id="loadUpcoming">Load</button>
      <span id="metaUpcoming" class="muted"></span>
    </div>

    <table id="tblUpcoming" style="display:none">
      <thead>
        <tr>
          <th>Date</th><th>Time</th><th>Matchup</th><th>Score</th><th>Venue</th><th>Status</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

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
          <th>Date</th><th>Time</th><th>Matchup</th><th>Score</th><th>Venue</th><th>Status</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

  <script>
    const $ = (sel) => document.querySelector(sel);
    const teamSel = $("#team");

    function getStatusClass(status) {
      if (status.toLowerCase().includes('final')) return 'final';
      if (status.toLowerCase().includes('live') || status.toLowerCase().includes('progress')) return 'live';
      return 'scheduled';
    }

    async function loadUpcoming() {
      const teamId = teamSel.value;
      const days = parseInt($("#daysAhead").value || "7", 10);
      const meta = $("#metaUpcoming");
      const tbl = $("#tblUpcoming");
      const tbody = $("#tblUpcoming tbody");

      meta.textContent = "Loading...";
      tbody.innerHTML = "";
      tbl.style.display = "none";

      const params = new URLSearchParams({ mode: "future", days: String(days) });
      if (teamId) params.set("teamId", teamId);

      const res = await fetch("/nba/api/schedule?" + params.toString());
      if (!res.ok) { meta.textContent = "Error loading schedule"; return; }
      const data = await res.json();
      meta.textContent = `Team: ${data.team} | Window: ${data.window} | Rows: ${data.rows.length}`;

      if (!data.rows.length) { tbl.style.display = "none"; return; }

      for (const g of data.rows) {
        const tr = document.createElement("tr");
        const timeCell = g.time && g.time !== "TBD" ? g.time : "<span class='tbd'>TBD</span>";
        const matchup = `${g.away ?? ""} @ ${g.home ?? ""}`;
        
        // Handle scores - show only if both scores exist
        let scoreCell = "—";
        if (g.away_score !== null && g.home_score !== null && g.away_score !== undefined && g.home_score !== undefined) {
          scoreCell = `${g.away_score} - ${g.home_score}`;
        }
        
        const statusClass = getStatusClass(g.status);
        const qs = new URLSearchParams({
          a: g.away ?? "",
          h: g.home ?? "",
          d: g.date ?? "",
          t: g.time ?? ""
        });
        tr.innerHTML = `
          <td>${g.date ?? ""}</td>
          <td>${timeCell}</td>
          <td><a href="/nba/game/${g.game_id}?${qs.toString()}" target="_blank" rel="noopener">${matchup}</a></td>
          <td>${scoreCell}</td>
          <td>${g.venue ?? ""}</td>
          <td class="${statusClass}">${g.status ?? ""}</td>
        `;
        tbody.appendChild(tr);
      }
      tbl.style.display = "";
    }

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

      const res = await fetch("/nba/api/schedule?" + params.toString());
      if (!res.ok) { meta.textContent = "Error loading schedule"; return; }
      const data = await res.json();
      meta.textContent = `Team: ${data.team} | Window: ${data.window} | Rows: ${data.rows.length}`;

      if (!data.rows.length) { tbl.style.display = "none"; return; }

      for (const g of data.rows) {
        const tr = document.createElement("tr");
        const timeCell = g.time && g.time !== "TBD" ? g.time : "<span class='tbd'>TBD</span>";
        const matchup = `${g.away ?? ""} @ ${g.home ?? ""}`;
        
        // Handle scores - show only if both scores exist
        let scoreCell = "—";
        if (g.away_score !== null && g.home_score !== null && g.away_score !== undefined && g.home_score !== undefined) {
          scoreCell = `${g.away_score} - ${g.home_score}`;
        }
        
        const statusClass = getStatusClass(g.status);
        const qs = new URLSearchParams({
          a: g.away ?? "",
          h: g.home ?? "",
          d: g.date ?? "",
          t: g.time ?? ""
        });
        tr.innerHTML = `
          <td>${g.date ?? ""}</td>
          <td>${timeCell}</td>
          <td><a href="/nba/game/${g.game_id}?${qs.toString()}" target="_blank" rel="noopener">${matchup}</a></td>
          <td>${scoreCell}</td>
          <td>${g.venue ?? ""}</td>
          <td class="${statusClass}">${g.status ?? ""}</td>
        `;
        tbody.appendChild(tr);
      }
      tbl.style.display = "";
    }

    $("#loadUpcoming").addEventListener("click", loadUpcoming);
    $("#loadPrevious").addEventListener("click", loadPrevious);

    loadUpcoming();
    loadPrevious();
  </script>
</body>
</html>
"""
# =========================
# MLB GAME PAGE (unchanged)
# =========================

GAME_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --card-bg: rgba(0,0,0,0.55);
      --card-border: rgba(255,255,255,0.2);
      --text-main: #fff;
      --text-muted: #ddd;
      --home-color: #42a5f5;
      --away-color: #ef5350;
    }

    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      margin: 24px;
      background-image: url('/static/images/wallpaper.jpeg');
      background-size: cover;
      background-position: center;
      background-attachment: fixed;
      color: var(--text-main);
      position: relative;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.60);
      z-index: -1;
    }

    a {
      color: #7cc9ff;
      text-decoration: none;
      font-weight: 500;
    }
    a:hover { text-decoration: underline; }

    h1 {
      margin: 0 0 4px;
      font-size: 28px;
    }
    h2 {
      margin: 12px 0 6px;
      font-size: 20px;
    }
    h3 {
      margin: 10px 0 6px;
      font-size: 18px;
    }

    .muted { color: var(--text-muted); }

    .grid-top {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 18px;
      margin-top: 16px;
    }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 18px;
      backdrop-filter: blur(6px);
    }

    table {
      border-collapse: collapse;
      width: 100%;
      background: rgba(255,255,255,0.06);
      color: var(--text-main);
      backdrop-filter: blur(4px);
      font-size: 14px;
    }
    th, td {
      border: 1px solid rgba(255,255,255,0.25);
      padding: 6px 8px;
      text-align: center;
    }
    th {
      background: rgba(0,0,0,0.4);
    }
    .left { text-align: left; }

    .wp-bar {
      display: flex;
      border-radius: 999px;
      overflow: hidden;
      border: 1px solid rgba(255,255,255,0.3);
      margin-top: 8px;
      height: 24px;
      font-size: 12px;
    }
    .wp-away {
      background: var(--away-color);
      display: flex;
      align-items: center;
      justify-content: center;
      white-space: nowrap;
    }
    .wp-home {
      background: var(--home-color);
      display: flex;
      align-items: center;
      justify-content: center;
      white-space: nowrap;
    }

    .charts-section {
      margin-top: 24px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }
    .chart-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 18px;
      backdrop-filter: blur(6px);
    }
    canvas {
      max-width: 100%;
    }

    @media (max-width: 600px) {
      body {
        margin: 12px;
      }
    }
  </style>
</head>
<body>
  <p><a href="/mlb">&larr; Back to MLB schedule</a></p>
  <h1>{{ title }}</h1>
  <p class="muted">{{ subtitle }}</p>

  <div class="grid-top">
    <!-- Meta -->
    <div class="card">
      <h2>Meta</h2>
      <div><strong>Status:</strong> {{ status }}</div>
      <div><strong>Date/Time:</strong> {{ when or "TBD" }}</div>
      <div><strong>Venue:</strong> {{ venue or "TBD" }}</div>
      <p class="muted" style="margin-top:8px;">Our Win Prediction.</p>
      <div class="wp-bar">
        <div class="wp-away" style="width: {{ wp_away_pct }}%;">Away {{ wp_away_pct }}%</div>
        <div class="wp-home" style="width: {{ wp_home_pct }}%;">Home {{ wp_home_pct }}%</div>
      </div>
      <p class="muted" style="margin-top:6px;">{{ wp_note }}</p>
      <p style="margin-top:6px;"><strong>Model pick:</strong> {{ wp_pick }}</p>
    </div>

    <!-- Score R/H/E -->
    <div class="card">
      <h2>Score</h2>
      <table>
        <thead>
          <tr>
            <th class="left">Team</th>
            <th>R</th>
            <th>H</th>
            <th>E</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="left">{{ away_name }}</td>
            <td>{{ away_r }}</td>
            <td>{{ away_h }}</td>
            <td>{{ away_e }}</td>
          </tr>
          <tr>
            <td class="left">{{ home_name }}</td>
            <td>{{ home_r }}</td>
            <td>{{ home_h }}</td>
            <td>{{ home_e }}</td>
          </tr>
        </tbody>
      </table>
    </div>

        <div class="card">
      {% if innings and innings|length > 0 %}
        <h2>Innings</h2>
        <table>
          <thead>
          <tr>
            <th>Team</th>
            {% for inn in innings %}
              <th>{{ inn }}</th>
            {% endfor %}
          </tr>
          </thead>
          <tbody>
          <tr>
            <td class="left">{{ away_name }}</td>
            {% for r in away_innings %}
              <td>{{ r }}</td>
            {% endfor %}
          </tr>
          <tr>
            <td class="left">{{ home_name }}</td>
            {% for r in home_innings %}
              <td>{{ r }}</td>
            {% endfor %}
          </tr>
          </tbody>
        </table>
      {% else %}
        <h2>Pitching Comparison</h2>
        <table>
          <thead>
          <tr>
            <th class="left">Pitcher</th>
            <th>Team</th>
            <th>IP</th>
            <th>H</th>
            <th>ER</th>
            <th>SO</th>
            <th>BB</th>
          </tr>
          </thead>
          <tbody>
          <tr>
            <td class="left">{{ away_pitcher.name }}</td>
            <td>{{ away_name }}</td>
            <td>{{ away_pitcher.ip }}</td>
            <td>{{ away_pitcher.h }}</td>
            <td>{{ away_pitcher.er }}</td>
            <td>{{ away_pitcher.so }}</td>
            <td>{{ away_pitcher.bb }}</td>
          </tr>
          <tr>
            <td class="left">{{ home_pitcher.name }}</td>
            <td>{{ home_name }}</td>
            <td>{{ home_pitcher.ip }}</td>
            <td>{{ home_pitcher.h }}</td>
            <td>{{ home_pitcher.er }}</td>
            <td>{{ home_pitcher.so }}</td>
            <td>{{ home_pitcher.bb }}</td>
          </tr>
          </tbody>
        </table>
        <p class="muted" style="margin-top:6px;">
          H2H Pitching Stats.
        </p>
      {% endif %}
    </div>

  </div>

  <!-- Charts -->
  <div class="charts-section">

    <!-- Chart 1: Recent scoring trends -->
    <div class="chart-card">
      <h3>Recent Scoring Trends (Last 5 Games)</h3>
      <p class="muted">
        Not betting advice – charts show recent runs scored and allowed for each team.
      </p>
      <canvas id="mlbTrendsChart" height="120"></canvas>
    </div>

    <!-- Chart 2: Team averages -->
    <div class="chart-card">
      <h3>Team Averages (Last 5 Games)</h3>
      <p class="muted">
        Average runs scored and allowed across each club's last few games.
      </p>
      <canvas id="mlbAveragesChart" height="120"></canvas>
    </div>

    <!-- Chart 3: Head-to-Head (Last 5 Matchups) -->
    <div class="chart-card">
      <h3>Head-to-Head – Last 5 Matchups</h3>
      <p class="muted" id="h2hSummary">
        <!-- Filled by JS -->
      </p>
      <canvas id="mlbH2HChart" height="120"></canvas>
    </div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    (function() {
      const homeAbbr = {{ home_abbr|default("HOME")|tojson }};
      const awayAbbr = {{ away_abbr|default("AWAY")|tojson }};
      const trendHome = {{ trend_home|default({})|tojson }};
      const trendAway = {{ trend_away|default({})|tojson }};
      const h2h = {{ h2h|default({"games": [], "team_a_wins": 0, "team_b_wins": 0})|tojson }};

      // ---------- Chart 1: Recent scoring trends ----------
      const trendLabels =
        (trendHome.labels && trendHome.labels.length) ? trendHome.labels :
        (trendAway.labels || []);

      const homeRunsFor = trendHome.runs_for || [];
      const homeRunsAgainst = trendHome.runs_against || [];
      const awayRunsFor = trendAway.runs_for || [];
      const awayRunsAgainst = trendAway.runs_against || [];

      const ctxTrend = document.getElementById('mlbTrendsChart').getContext('2d');
      new Chart(ctxTrend, {
        type: 'line',
        data: {
          labels: trendLabels,
          datasets: [
            {
              label: homeAbbr + ' runs scored',
              data: homeRunsFor,
              tension: 0.25
            },
            {
              label: awayAbbr + ' runs scored',
              data: awayRunsFor,
              tension: 0.25
            }
          ]
        },
        options: {
          responsive: true,
          plugins: {
            legend: { labels: { color: '#fff' } },
            tooltip: { mode: 'index', intersect: false }
          },
          scales: {
            x: {
              ticks: { color: '#fff' },
              title: { display: true, text: 'Recent games (MM-DD)', color: '#fff' }
            },
            y: {
              ticks: { color: '#fff' },
              title: { display: true, text: 'Runs scored', color: '#fff' }
            }
          }
        }
      });

      // ---------- Chart 2: Team averages ----------
      const avgHomeFor = trendHome.avg_runs_for || 0;
      const avgHomeAgainst = trendHome.avg_runs_against || 0;
      const avgAwayFor = trendAway.avg_runs_for || 0;
      const avgAwayAgainst = trendAway.avg_runs_against || 0;

      const ctxAvg = document.getElementById('mlbAveragesChart').getContext('2d');
      new Chart(ctxAvg, {
        type: 'bar',
        data: {
          labels: [
            homeAbbr + ' runs for',
            homeAbbr + ' runs allowed',
            awayAbbr + ' runs for',
            awayAbbr + ' runs allowed'
          ],
          datasets: [{
            label: 'Average runs (last 5 games)',
            data: [avgHomeFor, avgHomeAgainst, avgAwayFor, avgAwayAgainst]
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: { labels: { color: '#fff' } },
            tooltip: { mode: 'index', intersect: false }
          },
          scales: {
            x: {
              ticks: { color: '#fff' },
              title: { display: true, text: 'Team averages', color: '#fff' }
            },
            y: {
              ticks: { color: '#fff' },
              title: { display: true, text: 'Runs per game (approx.)', color: '#fff' }
            }
          }
        }
      });

      // ---------- Chart 3: Head-to-head last 5 ----------
      const h2hGames = h2h.games || [];
      const h2hLabels = h2hGames.map(g => g.date_label);
      const h2hHomeRuns = h2hGames.map(g => g.team_a_runs);
      const h2hAwayRuns = h2hGames.map(g => g.team_b_runs);

      const ctxH2H = document.getElementById('mlbH2HChart').getContext('2d');
      new Chart(ctxH2H, {
        type: 'bar',
        data: {
          labels: h2hLabels,
          datasets: [
            {
              label: homeAbbr + ' runs',
              data: h2hHomeRuns
            },
            {
              label: awayAbbr + ' runs',
              data: h2hAwayRuns
            }
          ]
        },
        options: {
          responsive: true,
          plugins: {
            legend: { labels: { color: '#fff' } },
            tooltip: { mode: 'index', intersect: false }
          },
          scales: {
            x: {
              ticks: { color: '#fff' },
              title: { display: true, text: 'Recent head-to-head games (MM-DD)', color: '#fff' }
            },
            y: {
              ticks: { color: '#fff' },
              title: { display: true, text: 'Runs scored', color: '#fff' }
            }
          }
        }
      });

      // Summary text for W/L split
      const h2hSummaryEl = document.getElementById('h2hSummary');
      if (h2hSummaryEl) {
        const aWins = h2h.team_a_wins || 0;
        const bWins = h2h.team_b_wins || 0;
        if (h2hGames.length) {
          h2hSummaryEl.textContent =
            `Last ${h2hGames.length} meetings: ` +
            `${homeAbbr} ${aWins}-${bWins} ${awayAbbr}.`;
        } else {
          h2hSummaryEl.textContent = 'No recent head-to-head games found.';
        }
      }
    })();
  </script>
</body>
</html>
"""

# =========================
# NBA GAME PAGE (unchanged)
# =========================

NBA_GAME_HTML = """
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
      background-image: url('/static/images/basketball.jpeg');
      background-size: cover;
      background-position: center;
      background-attachment: fixed;
      color: #fff;
      position: relative;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.65);
      z-index: -1;
    }

    a {
      color: #7cc9ff;
      text-decoration: none;
      font-weight: 500;
    }
    a:hover { text-decoration: underline; }

    .muted { color: #ddd; }

    h1 {
      margin: 0 0 6px;
      font-size: 28px;
      color: #fff;
    }
    h2 {
      margin: 12px 0 6px;
      font-size: 20px;
      color: #f2f2f2;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 18px;
      margin-top: 16px;
    }

    .card {
      background: rgba(0,0,0,0.45);
      backdrop-filter: blur(6px);
      border: 1px solid rgba(255,255,255,0.15);
      border-radius: 14px;
      padding: 18px;
    }

    table {
      border-collapse: collapse;
      width: 100%;
      background: rgba(255,255,255,0.08);
      color: #fff;
      backdrop-filter: blur(4px);
      font-size: 14px;
    }

    th, td {
      border: 1px solid rgba(255,255,255,0.25);
      padding: 6px 8px;
      text-align: center;
    }

    th {
      background: rgba(0,0,0,0.4);
      color: #fff;
      text-align: center;
    }

    .left { text-align: left; }

    .wp-bar {
      display: flex;
      border-radius: 999px;
      overflow: hidden;
      border: 1px solid rgba(255,255,255,0.2);
      margin-top: 8px;
      height: 24px;
      font-size: 12px;
    }

    .wp-away {
      background: #00b0ff;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      white-space: nowrap;
    }

    .wp-home {
      background: #ff7043;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      white-space: nowrap;
    }

    .chart-container {
      height: 260px;
      width: 100%;
    }

    .starter-usage-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      margin-top: 12px;
    }
  </style>
</head>
<body>
  <p><a href="/nba">&larr; Back to NBA schedule</a></p>
  <h1>{{ title }}</h1>
  <p class="muted">{{ subtitle }}</p>

  <!-- Top row: meta + score + starting fives -->
  <div class="grid">
    <!-- Meta -->
    <div class="card">
      <h2>Meta</h2>
      <div><strong>Status:</strong> {{ status }}</div>
      <div><strong>Date/Time:</strong> {{ when }}</div>
      <div><strong>Venue:</strong> {{ venue or 'TBD' }}</div>
      <p class="muted" style="margin-top:8px;">Our Best Predection.</p>
      <div class="wp-bar">
        <div class="wp-away" style="width: {{ wp_away_pct }}%;">Away {{ wp_away_pct }}%</div>
        <div class="wp-home" style="width: {{ wp_home_pct }}%;">Home {{ wp_home_pct }}%</div>
      </div>
      <p class="muted" style="margin-top:8px;">{{ wp_note }}</p>
      <p style="margin-top:4px;"><strong>Model pick:</strong> {{ wp_pick }}</p>
    </div>

    <!-- Score -->
    <div class="card">
      <h2>Score</h2>
      <table>
        <thead><tr><th class="left">Team</th><th>PTS</th></tr></thead>
        <tbody>
          <tr><td class="left">{{ away_name }}</td><td>{{ away_score }}</td></tr>
          <tr><td class="left">{{ home_name }}</td><td>{{ home_score }}</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Starting Five – Home -->
    <div class="card">
      <h2>{{ home_name }} Starting Five – Last 5 Games</h2>
      {% if starters_home and starters_home|length > 0 %}
      <table>
        <thead>
          <tr>
            <th class="left">Player</th>
            <th>Pos</th>
            <th>PTS (Last 5)</th>
            <th>REB (Last 5)</th>
            <th>AST (Last 5)</th>
          </tr>
        </thead>
        <tbody>
          {% for p in starters_home %}
          <tr>
            <td class="left">{{ p.name }}</td>
            <td>{{ p.pos }}</td>
            <td>{{ p.pts }}</td>
            <td>{{ p.reb }}</td>
            <td>{{ p.ast }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% else %}
        <p class="muted">No stats available for {{ home_name }}’s starting lineup.</p>
      {% endif %}
    </div>

    <!-- Starting Five – Away -->
    <div class="card">
      <h2>{{ away_name }} Starting Five – Last 5 Games</h2>
      {% if starters_away and starters_away|length > 0 %}
      <table>
        <thead>
          <tr>
            <th class="left">Player</th>
            <th>Pos</th>
            <th>PTS (Last 5)</th>
            <th>REB (Last 5)</th>
            <th>AST (Last 5)</th>
          </tr>
        </thead>
        <tbody>
          {% for p in starters_away %}
          <tr>
            <td class="left">{{ p.name }}</td>
            <td>{{ p.pos }}</td>
            <td>{{ p.pts }}</td>
            <td>{{ p.reb }}</td>
            <td>{{ p.ast }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% else %}
        <p class="muted">No stats available for {{ away_name }}’s starting lineup.</p>
      {% endif %}
    </div>
  </div>

  <!-- Chart section -->
  <div class="card" style="margin-top:20px;">
    <h2>Recent Scoring Trends (Last 5 Games)</h2>
    <p class="muted" style="margin-bottom:8px;">
      Not betting advice – charts show recent scoring, point margins, and simple team averages for each side.
    </p>
    <div class="chart-container">
      <canvas id="scoringTrendChart"></canvas>
    </div>
    <div class="chart-container" style="margin-top:18px;">
      <canvas id="marginTrendChart"></canvas>
    </div>
  </div>

  <div class="card" style="margin-top:18px;">
    <h2>Team Averages (Last 5 Games)</h2>
    <div class="chart-container">
      <canvas id="teamAvgChart"></canvas>
    </div>
  </div>

  <div class="card" style="margin-top:18px;">
    <h2>Head-to-Head (Last 5 Matchups)</h2>
    <p class="muted" style="margin-bottom:8px;">
      How many of the last 5 games between these teams each side has won.
    </p>
    <div class="chart-container">
      <canvas id="h2hWinChart"></canvas>
    </div>
  </div>

  <div class="card" style="margin-top:18px;">
    <h2>Total Points vs Sample Total (Recent Games)</h2>
    <p class="muted" style="margin-bottom:8px;">
      Compares total points scored in recent games to a sample total line (e.g. 220). Not betting advice.
    </p>
    <div class="chart-container">
      <canvas id="totalPointsChart"></canvas>
    </div>
  </div>

  <div class="card" style="margin-top:18px;">
    <h2>Margin of Victory Profile (Last 5 Games)</h2>
    <p class="muted" style="margin-bottom:8px;">
      How often each team wins by a small margin vs a blowout, based on the last 5 games.
    </p>
    <div class="chart-container">
      <canvas id="marginProfileChart"></canvas>
    </div>
  </div>

  <div class="card" style="margin-top:18px;">
    <h2>Starter Scoring Load (This Game)</h2>
    <p class="muted" style="margin-bottom:8px;">
      Points scored by each starter in this game – a quick view of how concentrated the scoring is.
    </p>
    <div class="starter-usage-grid">
      <div>
        <h3 style="margin:0 0 4px; font-size:16px;">{{ home_name }}</h3>
        <div class="chart-container" style="height:220px;">
          <canvas id="starterHomeChart"></canvas>
        </div>
      </div>
      <div>
        <h3 style="margin:0 0 4px; font-size:16px;">{{ away_name }}</h3>
        <div class="chart-container" style="height:220px;">
          <canvas id="starterAwayChart"></canvas>
        </div>
      </div>
    </div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    const homeName   = {{ home_name | tojson }};
    const awayName   = {{ away_name | tojson }};
    const trendHome  = {{ trend_home | tojson }};
    const trendAway  = {{ trend_away | tojson }};
    const startersHome = {{ starters_home | tojson }};
    const startersAway = {{ starters_away | tojson }};
    const h2h = {{ h2h | tojson }};

    // Helper to safely pull arrays
    function arr(x) { return Array.isArray(x) ? x : []; }

    // -------- Scoring Trends (line chart) --------
    (function() {
      if (!trendHome || (!trendHome.labels && !trendAway.labels)) return;

      const labelsHome = arr(trendHome.labels);
      const labelsAway = arr(trendAway.labels);
      const labels = labelsHome.length >= labelsAway.length ? labelsHome : labelsAway;

      const homePts = arr(trendHome.pts_for);
      const awayPts = arr(trendAway.pts_for);

      const ctx = document.getElementById('scoringTrendChart').getContext('2d');
      new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: homeName + ' PTS',
              data: homePts,
              borderColor: 'rgba(54, 162, 235, 1)',
              backgroundColor: 'rgba(54, 162, 235, 0.25)',
              tension: 0.25,
              pointRadius: 3
            },
            {
              label: awayName + ' PTS',
              data: awayPts,
              borderColor: 'rgba(255, 99, 132, 1)',
              backgroundColor: 'rgba(255, 99, 132, 0.25)',
              tension: 0.25,
              pointRadius: 3
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#fff' } },
            tooltip: { mode: 'index', intersect: false }
          },
          scales: {
            x: {
              ticks: { color: '#fff' },
              grid: { color: 'rgba(255,255,255,0.08)' },
              title: { display: true, text: 'Recent games (MM-DD)', color: '#fff' }
            },
            y: {
              beginAtZero: true,
              ticks: { color: '#fff' },
              grid: { color: 'rgba(255,255,255,0.08)' },
              title: { display: true, text: 'Points scored', color: '#fff' }
            }
          }
        }
      });
    })();

    // -------- Head-to-head margin trend (this opponent, last 5 games) --------
    (function() {
      if (!h2h || !Array.isArray(h2h.games) || !h2h.games.length) return;

      const labels = h2h.games.map(g => g.date_label || g.date);
      const homeMargin = h2h.games.map(g => (g.team_a_pts || 0) - (g.team_b_pts || 0));
      const awayMargin = homeMargin.map(v => -v);  // same games, opposite perspective

      const ctx = document.getElementById('marginTrendChart').getContext('2d');
      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            {
              label: homeName + ' margin (home - away)',
              data: homeMargin,
              backgroundColor: 'rgba(54, 162, 235, 0.8)',
              borderColor: 'rgba(54, 162, 235, 1)',
              borderWidth: 1
            },
            {
              label: awayName + ' margin (away - home)',
              data: awayMargin,
              backgroundColor: 'rgba(255, 99, 132, 0.8)',
              borderColor: 'rgba(255, 99, 132, 1)',
              borderWidth: 1
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#fff' } },
            tooltip: { mode: 'index', intersect: false }
          },
          scales: {
            x: {
              ticks: { color: '#fff' },
              grid: { color: 'rgba(255,255,255,0.08)' },
              title: { display: true, text: 'Head-to-head games (most recent)', color: '#fff' }
            },
            y: {
              ticks: { color: '#fff' },
              grid: { color: 'rgba(255,255,255,0.08)' },
              title: { display: true, text: 'Point differential', color: '#fff' }
            }
          }
        }
      });
    })();

    // -------- Team Averages (blue vs red) --------
    (function() {
      const homeAvgFor = trendHome && typeof trendHome.avg_pts_for === 'number' ? trendHome.avg_pts_for : 0;
      const homeAvgAgainst = trendHome && typeof trendHome.avg_pts_against === 'number' ? trendHome.avg_pts_against : 0;
      const awayAvgFor = trendAway && typeof trendAway.avg_pts_for === 'number' ? trendAway.avg_pts_for : 0;
      const awayAvgAgainst = trendAway && typeof trendAway.avg_pts_against === 'number' ? trendAway.avg_pts_against : 0;

      const labels = [
        homeName + ' PTS For',
        homeName + ' PTS Allowed',
        awayName + ' PTS For',
        awayName + ' PTS Allowed',
      ];

      const data = [homeAvgFor, homeAvgAgainst, awayAvgFor, awayAvgAgainst];

      const ctx = document.getElementById('teamAvgChart').getContext('2d');
      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Average points (last 5 games)',
            data: data,
            backgroundColor: [
              'rgba(54, 162, 235, 0.8)',
              'rgba(54, 162, 235, 0.6)',
              'rgba(255, 99, 132, 0.8)',
              'rgba(255, 99, 132, 0.6)',
            ],
            borderColor: [
              'rgba(54, 162, 235, 1)',
              'rgba(54, 162, 235, 0.9)',
              'rgba(255, 99, 132, 1)',
              'rgba(255, 99, 132, 0.9)',
            ],
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#fff' } },
            tooltip: { mode: 'index', intersect: false }
          },
          scales: {
            x: {
              ticks: { color: '#fff', maxRotation: 30, minRotation: 30 },
              grid: { color: 'rgba(255,255,255,0.08)' },
              title: { display: true, text: 'Team averages', color: '#fff' }
            },
            y: {
              beginAtZero: true,
              ticks: { color: '#fff' },
              grid: { color: 'rgba(255,255,255,0.08)' },
              title: { display: true, text: 'Points per game (approx.)', color: '#fff' }
            }
          }
        }
      });
    })();

    // -------- Head-to-head wins --------
    (function() {
      if (!h2h) return;
      const winsHome = h2h.team_a_wins || 0;
      const winsAway = h2h.team_b_wins || 0;

      if (!winsHome && !winsAway) return;

      const ctx = document.getElementById('h2hWinChart').getContext('2d');
      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: [homeName, awayName],
          datasets: [{
            label: 'Wins in last 5 head-to-head games',
            data: [winsHome, winsAway],
            backgroundColor: [
              'rgba(54, 162, 235, 0.8)',
              'rgba(255, 99, 132, 0.8)'
            ],
            borderColor: [
              'rgba(54, 162, 235, 1)',
              'rgba(255, 99, 132, 1)'
            ],
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { mode: 'index', intersect: false }
          },
          scales: {
            x: {
              ticks: { color: '#fff' },
              grid: { color: 'rgba(255,255,255,0.08)' },
            },
            y: {
              beginAtZero: true,
              ticks: { stepSize: 1, color: '#fff' },
              grid: { color: 'rgba(255,255,255,0.08)' },
              title: { display: true, text: 'Wins (last 5 matchups)', color: '#fff' }
            }
          }
        }
      });
    })();

    // -------- Total points vs sample total --------
    (function() {
      if (!trendHome && !trendAway) return;

      const labels = arr(trendHome.labels || trendAway.labels);
      if (!labels.length) return;

      const homeTotals = arr(trendHome.pts_for).map((pf, i) => {
        const pa = arr(trendHome.pts_against)[i] || 0;
        return (pf || 0) + pa;
      });
      const awayTotals = arr(trendAway.pts_for).map((pf, i) => {
        const pa = arr(trendAway.pts_against)[i] || 0;
        return (pf || 0) + pa;
      });

      const targetTotal = 220;  // sample "total" line

      const ctx = document.getElementById('totalPointsChart').getContext('2d');
      new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: homeName + ' total points',
              data: homeTotals,
              borderColor: 'rgba(54, 162, 235, 1)',
              backgroundColor: 'rgba(54, 162, 235, 0.25)',
              tension: 0.25,
              pointRadius: 3
            },
            {
              label: awayName + ' total points',
              data: awayTotals,
              borderColor: 'rgba(255, 99, 132, 1)',
              backgroundColor: 'rgba(255, 99, 132, 0.25)',
              tension: 0.25,
              pointRadius: 3
            },
            {
              label: 'Sample total (' + targetTotal + ')',
              data: labels.map(() => targetTotal),
              borderColor: 'rgba(255, 206, 86, 1)',
              borderDash: [6,4],
              pointRadius: 0,
              fill: false
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#fff' } },
            tooltip: { mode: 'index', intersect: false }
          },
          scales: {
            x: {
              ticks: { color: '#fff' },
              grid: { color: 'rgba(255,255,255,0.08)' },
              title: { display: true, text: 'Recent games (MM-DD)', color: '#fff' }
            },
            y: {
              beginAtZero: true,
              ticks: { color: '#fff' },
              grid: { color: 'rgba(255,255,255,0.08)' },
              title: { display: true, text: 'Total points', color: '#fff' }
            }
          }
        }
      });
    })();

    // -------- Margin of victory profile --------
    (function() {
      if (!trendHome && !trendAway) return;

      function buildBuckets(margins) {
        let close = 0;    // wins by 0–5
        let solid = 0;    // wins by 6–12
        let blowout = 0;  // wins by 13+
        arr(margins).forEach(m => {
          if (m > 0 && m <= 5) close++;
          else if (m > 5 && m <= 12) solid++;
          else if (m > 12) blowout++;
        });
        return [close, solid, blowout];
      }

      const homeBuckets = buildBuckets(trendHome && trendHome.margin);
      const awayBuckets = buildBuckets(trendAway && trendAway.margin);

      const labels = ['0–5 pts', '6–12 pts', '13+ pts'];

      const ctx = document.getElementById('marginProfileChart').getContext('2d');
      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            {
              label: homeName,
              data: homeBuckets,
              backgroundColor: 'rgba(54, 162, 235, 0.8)',
              borderColor: 'rgba(54, 162, 235, 1)',
              borderWidth: 1
            },
            {
              label: awayName,
              data: awayBuckets,
              backgroundColor: 'rgba(255, 99, 132, 0.8)',
              borderColor: 'rgba(255, 99, 132, 1)',
              borderWidth: 1
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#fff' } },
            tooltip: { mode: 'index', intersect: false }
          },
          scales: {
            x: {
              ticks: { color: '#fff' },
              grid: { color: 'rgba(255,255,255,0.08)' },
              title: { display: true, text: 'Win margin buckets', color: '#fff' }
            },
            y: {
              beginAtZero: true,
              ticks: { stepSize: 1, color: '#fff' },
              grid: { color: 'rgba(255,255,255,0.08)' },
              title: { display: true, text: 'Number of games (last 5)', color: '#fff' }
            }
          }
        }
      });
    })();

    // -------- Starter scoring load (one chart per team) --------
    (function() {
      // Home starters
      if (startersHome && startersHome.length) {
        const labels = startersHome.map(p => p.name);
        const data = startersHome.map(p => p.pts || 0);

        const ctx = document.getElementById('starterHomeChart').getContext('2d');
        new Chart(ctx, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [{
              label: 'Points this game',
              data: data,
              backgroundColor: 'rgba(54, 162, 235, 0.8)',
              borderColor: 'rgba(54, 162, 235, 1)',
              borderWidth: 1
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { labels: { color: '#fff' } },
              tooltip: { mode: 'index', intersect: false }
            },
            scales: {
              x: {
                ticks: { color: '#fff', maxRotation: 40, minRotation: 40 },
                grid: { color: 'rgba(255,255,255,0.08)' }
              },
              y: {
                beginAtZero: true,
                ticks: { color: '#fff' },
                grid: { color: 'rgba(255,255,255,0.08)' },
                title: { display: true, text: 'Points', color: '#fff' }
              }
            }
          }
        });
      }

      // Away starters
      if (startersAway && startersAway.length) {
        const labels = startersAway.map(p => p.name);
        const data = startersAway.map(p => p.pts || 0);

        const ctx = document.getElementById('starterAwayChart').getContext('2d');
        new Chart(ctx, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [{
              label: 'Points this game',
              data: data,
              backgroundColor: 'rgba(255, 99, 132, 0.8)',
              borderColor: 'rgba(255, 99, 132, 1)',
              borderWidth: 1
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { labels: { color: '#fff' } },
              tooltip: { mode: 'index', intersect: false }
            },
            scales: {
              x: {
                ticks: { color: '#fff', maxRotation: 40, minRotation: 40 },
                grid: { color: 'rgba(255,255,255,0.08)' }
              },
              y: {
                beginAtZero: true,
                ticks: { color: '#fff' },
                grid: { color: 'rgba(255,255,255,0.08)' },
                title: { display: true, text: 'Points', color: '#fff' }
              }
            }
          }
        });
      }
    })();
  </script>
</body>
</html>
"""




# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return render_template_string(HOME_HTML)


@app.route("/mlb")
def mlb_index():
    return render_template_string(INDEX_HTML, teams=TEAMS)


@app.route("/nba")
def nba_index():
    return render_template_string(NBA_HTML, teams=NBA_TEAMS)


@app.route("/api/schedule")
def api_schedule():
    team_id = request.args.get("teamId", type=int)
    days = request.args.get("days", default=7, type=int)
    mode = request.args.get("mode", default="future")
    data = fetch_schedule(team_id, days, mode)
    return jsonify(data)


@app.route("/nba/api/schedule")
def nba_api_schedule():
    team_id = request.args.get("teamId", type=int)
    days = request.args.get("days", default=7, type=int)
    mode = request.args.get("mode", default="future")
    
    try:
        data = fetch_nba_schedule(team_id, days, mode)
        return jsonify(data)
    except Exception as e:
        print(f"Error in nba_api_schedule: {e}")
        return jsonify({"team": "ERROR", "window": "Error", "rows": []})


@app.route("/game/<int:game_id>")
def game_page(game_id: int):
    page = fetch_game_page(
        game_id,
        away_hint=request.args.get("a"),
        home_hint=request.args.get("h"),
        venue_hint=request.args.get("v"),
        date_hint=request.args.get("d"),
        time_hint=request.args.get("t"),
    )
    return render_template_string(GAME_HTML, game_id=game_id, **page)


@app.route("/nba/game/<game_id>")
def nba_game_page(game_id: str):
    try:
        page = fetch_nba_game(
            game_id,
            away_hint=request.args.get("a"),
            home_hint=request.args.get("h"),
            date_hint=request.args.get("d"),
            time_hint=request.args.get("t"),
        )
        return render_template_string(NBA_GAME_HTML, **page)
    except Exception as e:
        print(f"Error loading NBA game {game_id}: {e}")
        # Return a basic error page
        return render_template_string(NBA_GAME_HTML, 
            title="Error Loading Game",
            subtitle=f"Game ID: {game_id}",
            status="Error",
            when="",
            away_name=request.args.get("a", "Away"),
            home_name=request.args.get("h", "Home"),
            away_score=0,
            home_score=0,
            top_players=[],
            wp_home_pct=50,
            wp_away_pct=50,
            wp_note="Error loading game data"
        )
    
@app.route("/nba/debug/detailed")
def nba_debug_detailed():
    """Detailed debug route to check NBA API data"""
    try:
        from nba_api.stats.endpoints import ScoreboardV2
        from datetime import date, timedelta
        
        # Check yesterday's games
        yesterday = date.today() - timedelta(days=1)
        game_date_str = yesterday.strftime("%m/%d/%Y")
        
        sb = ScoreboardV2(game_date=game_date_str)
        header_df = sb.game_header.get_data_frame()
        ls_df = sb.line_score.get_data_frame()
        
        return jsonify({
            "status": "success",
            "date_checked": yesterday.isoformat(),
            "header_columns": list(header_df.columns) if not header_df.empty else "No headers",
            "line_score_columns": list(ls_df.columns) if not ls_df.empty else "No line scores",
            "games_count": len(header_df),
            "sample_header": header_df.head(2).to_dict('records') if not header_df.empty else "No games",
            "sample_line_score": ls_df.head(2).to_dict('records') if not ls_df.empty else "No line scores",
            "game_statuses": header_df["GAME_STATUS_TEXT"].unique().tolist() if "GAME_STATUS_TEXT" in header_df.columns else "No status column"
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})
    
@app.route("/nba/debug/current")
def nba_debug_current():
    """Check current real NBA games"""
    try:
        from nba_api.stats.endpoints import ScoreboardV2
        from datetime import date
        
        # Check today's actual games
        today = date.today()
        game_date_str = today.strftime("%m/%d/%Y")
        
        sb = ScoreboardV2(game_date=game_date_str)
        header_df = sb.game_header.get_data_frame()
        ls_df = sb.line_score.get_data_frame()
        
        return jsonify({
            "status": "success", 
            "date_checked": today.isoformat(),
            "current_year": today.year,
            "games_count": len(header_df),
            "game_statuses": header_df["GAME_STATUS_TEXT"].unique().tolist() if not header_df.empty else "No games",
            "has_line_scores": not ls_df.empty,
            "line_score_count": len(ls_df) if not ls_df.empty else 0
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})
# ========= MLB ADVANCED CHARTS =========

@app.route("/game/<int:game_id>/charts")
def game_charts(game_id):
    import datetime

    # 1) Get basic game info from schedule (works for past + future)
    sched = statsapi.schedule(game_id=game_id)
    if not sched:
        abort(404, description=f"Could not load game metadata for {game_id}")

    s = sched[0]
    home_name = s.get("home_name", "Home")
    away_name = s.get("away_name", "Away")
    home_id = s.get("home_id")
    away_id = s.get("away_id")
    start_str = s.get("game_date")

    home_abbr = team_abbr_from_name(home_name)
    away_abbr = team_abbr_from_name(away_name)

    def parse_dt(s: str):
        if not s:
            return None
        # schedule usually gives ISO string; fall back to just the date part
        try:
            return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            try:
                return datetime.datetime.fromisoformat(s[:10])
            except Exception:
                return None

    game_start = parse_dt(start_str)
    today = datetime.date.today()
    base_date = game_start.date() if game_start else today
    lookback_start = base_date - datetime.timedelta(days=365)

    # 2) Pull last ~40 days of games for each team
    try:
        home_sched = statsapi.schedule(
            start_date=lookback_start.isoformat(),
            end_date=today.isoformat(),
            team=home_id,
        )
        away_sched = statsapi.schedule(
            start_date=lookback_start.isoformat(),
            end_date=today.isoformat(),
            team=away_id,
        )
    except Exception:
        home_sched = []
        away_sched = []

    # ---------- helpers for stats from past games ----------

    def batting_avg(stats):
        ab = stats.get("atBats", 0) or stats.get("ab", 0) or 0
        h = stats.get("hits", 0) or stats.get("h", 0) or 0
        return h / ab if ab > 0 else 0.0

    def pitcher_era(stats):
        """
        Compute ERA from either (outs, earnedRuns) or (inningsPitched, earnedRuns/er).
        Works with both schedule-style and boxscore-style pitching dicts.
        """
        er = stats.get("earnedRuns")
        if er is None:
            er = stats.get("er", 0)
        er = er or 0

        outs = stats.get("outs") or 0

        # Fallback: inningsPitched like '5.2' → 5 innings + 2 outs
        if outs <= 0:
            ip_str = stats.get("inningsPitched") or stats.get("ip")
            if isinstance(ip_str, str) and ip_str:
                try:
                    whole, frac = (ip_str.split(".") + ["0"])[:2]
                    outs = int(whole) * 3 + int(frac)
                except Exception:
                    outs = 0

        if outs <= 0:
            return None

        ip = outs / 3.0
        return 9.0 * er / ip

    def recent_team_batting(sched, team_id, max_games=10):
        """
        Last ~max_games for THIS team only, using boxscore_data for each game.
        """
        games = [g for g in sched if g.get("status") == "Final"]
        games.sort(key=lambda x: x.get("game_date", ""), reverse=True)
        games = games[:max_games]

        total_hits = 0
        total_ab = 0

        for g in games:
            gid = g.get("game_id")
            if not gid:
                continue
            try:
                box = statsapi.boxscore_data(gid)
            except Exception:
                continue

            teams = box.get("teamInfo", {}) or {}
            home_info = teams.get("home", {}) or {}
            away_info = teams.get("away", {}) or {}
            hid = home_info.get("id")
            aid = away_info.get("id")

            if team_id == hid:
                side_node = box.get("home", {}) or {}
            elif team_id == aid:
                side_node = box.get("away", {}) or {}
            else:
                continue

            bat = (side_node.get("teamStats") or {}).get("batting", {}) or {}
            hits = bat.get("hits") or bat.get("h") or 0
            ab = bat.get("atBats") or bat.get("ab") or 0

            total_hits += hits or 0
            total_ab += ab or 0

        return total_hits / total_ab if total_ab > 0 else 0.0

    def recent_runs_for_team(sched, tid, max_games=10):
        games = [g for g in sched if g.get("status") == "Final"]
        games.sort(key=lambda x: x.get("game_date", ""), reverse=True)
        games = games[:max_games]
        rf = ra = 0
        cnt = 0
        for g in games:
            hs, as_ = g.get("home_score"), g.get("away_score")
            hid, aid = g.get("home_id"), g.get("away_id")
            if None in (hs, as_, hid, aid):
                continue
            if tid == hid:
                rf += hs
                ra += as_
            elif tid == aid:
                rf += as_
                ra += hs
            else:
                continue
            cnt += 1
        if cnt == 0:
            return 0.0, 0.0
        return rf / cnt, ra / cnt

    def avg_recent_era(sched, team_id, max_games=10):
        """
        Average ERA over last ~max_games for THIS team only,
        again using boxscore_data for each game.
        """
        games = [g for g in sched if g.get("status") == "Final"]
        games.sort(key=lambda x: x.get("game_date", ""), reverse=True)
        games = games[:max_games]

        eras = []
        for g in games:
            gid = g.get("game_id")
            if not gid:
                continue
            try:
                box = statsapi.boxscore_data(gid)
            except Exception:
                continue

            teams = box.get("teamInfo", {}) or {}
            home_info = teams.get("home", {}) or {}
            away_info = teams.get("away", {}) or {}
            hid = home_info.get("id")
            aid = away_info.get("id")

            if team_id == hid:
                side_node = box.get("home", {}) or {}
            elif team_id == aid:
                side_node = box.get("away", {}) or {}
            else:
                continue

            pstats = (side_node.get("teamStats") or {}).get("pitching", {}) or {}
            era_val = pitcher_era(pstats)
            if era_val is not None:
                eras.append(era_val)

        if not eras:
            return None
        return sum(eras) / len(eras)

    def first_inning_score_ratio(sched, team_id, max_games=30):
        """
        % of recent games where THIS team scored in the 1st inning.
        Uses boxscore_data to read the first-inning runs.
        """
        games = [g for g in sched if g.get("status") == "Final"]
        games.sort(key=lambda x: x.get("game_date", ""), reverse=True)
        games = games[:max_games]

        scored = 0
        total = 0

        for g in games:
            gid = g.get("game_id")
            if not gid:
                continue

            hid = g.get("home_id")
            aid = g.get("away_id")
            if team_id not in (hid, aid):
                continue

            side = "home" if team_id == hid else "away"

            try:
                box = statsapi.boxscore_data(gid)
            except Exception:
                continue

            innings = box.get("innings") or []
            if not innings:
                continue

            first = innings[0]
            side_node = first.get(side) or {}
            runs = side_node.get("runs")

            if isinstance(runs, (int, float)):
                total += 1
                if runs > 0:
                    scored += 1

        if total == 0:
            return 0.0
        return 100.0 * scored / total

    # 3) Compute all stats from those schedules
    away_ba = recent_team_batting(away_sched, away_id)
    home_ba = recent_team_batting(home_sched, home_id)
    away_era = avg_recent_era(away_sched, away_id)
    home_era = avg_recent_era(home_sched, home_id)
    away_runs_for, away_runs_against = recent_runs_for_team(away_sched, away_id)
    home_runs_for, home_runs_against = recent_runs_for_team(home_sched, home_id)
    away_first = first_inning_score_ratio(away_sched, away_id)
    home_first = first_inning_score_ratio(home_sched, home_id)

    # 4) Build Plotly figures (same as you already had)
    fig1 = go.Figure(
        [go.Bar(
            x=[away_abbr, home_abbr],
            y=[away_ba, home_ba],
            text=[f"{away_ba:.3f}", f"{home_ba:.3f}"],
            textposition="auto",
        )]
    )
    fig1.update_layout(
        title="Recent Team Batting AVG (last ~10 games)",
        yaxis_title="AVG",
        template="plotly_dark",
    )

    fig2 = go.Figure()
    if away_era is not None:
        fig2.add_trace(
            go.Bar(
                name=away_abbr,
                x=["ERA"],
                y=[away_era],
                text=[f"{away_era:.2f}"],
                textposition="auto",
            )
        )
    if home_era is not None:
        fig2.add_trace(
            go.Bar(
                name=home_abbr,
                x=["ERA"],
                y=[home_era],
                text=[f"{home_era:.2f}"],
                textposition="auto",
            )
        )
    fig2.update_layout(
        title="Recent Team ERA (approx, last ~10 games)",
        yaxis_title="ERA",
        barmode="group",
        template="plotly_dark",
    )

    fig3 = go.Figure(
        [go.Bar(
            x=[away_abbr, home_abbr, away_abbr + " Allowed", home_abbr + " Allowed"],
            y=[away_runs_for, home_runs_for, away_runs_against, home_runs_against],
            text=[
                f"{away_runs_for:.2f}",
                f"{home_runs_for:.2f}",
                f"{away_runs_against:.2f}",
                f"{home_runs_against:.2f}",
            ],
            textposition="auto",
        )]
    )
    fig3.update_layout(
        title="Recent Runs For / Against (last ~10 games)",
        yaxis_title="Runs per game",
        template="plotly_dark",
    )

    fig4 = go.Figure(
        [go.Bar(
            x=[away_name, home_name],
            y=[away_first, home_first],
            text=[f"{away_first:.1f}%", f"{home_first:.1f}%"],
            textposition="auto",
        )]
    )
    fig4.update_layout(
        title="First Inning Scoring Frequency (approx last ~30 games)",
        yaxis_title="% of games with run in 1st",
        template="plotly_dark",
    )

    charts_html = f"""
    <!doctype html>
    <html lang='en'>
      <head>
        <meta charset='utf-8'>
        <title>Game {game_id} Charts</title>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <script src='https://cdn.plot.ly/plotly-latest.min.js'></script>
        <style>
          body {{
            font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
            margin: 16px;
            background: #050816;
            color: #f9fafb;
          }}
          h1 {{ font-size: 20px; margin-bottom: 4px; }}
          h2 {{ margin-top: 22px; font-size: 18px; }}
          .chart {{ margin-top: 8px; }}
          a {{ color: #93c5fd; }}
        </style>
      </head>
      <body>
        <p><a href="/game/{game_id}">&larr; Back to game summary</a></p>
        <h1>Advanced Charts for {away_name} @ {home_name}</h1>
        <p>Data is approximate and based on last ~10–40 games.</p>

        <h2>Recent Batting AVG</h2>
        <div id='fig1' class='chart'></div>

        <h2>Recent ERA</h2>
        <div id='fig2' class='chart'></div>

        <h2>Runs For / Against</h2>
        <div id='fig3' class='chart'></div>

        <h2>First Inning Scoring Frequency</h2>
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
    return charts_html


if __name__ == "__main__":
    app.run(debug=True)
