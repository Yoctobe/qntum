<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FED CHAIR — The Monetary Policy Simulator</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&family=IBM+Plex+Mono:wght@300;400;600&display=swap');

  :root {
    --bg: #050a0e;
    --bg2: #0a1520;
    --bg3: #0f1f2e;
    --green: #00ff88;
    --green2: #00cc66;
    --red: #ff3355;
    --amber: #ffaa00;
    --blue: #00aaff;
    --cyan: #00ffcc;
    --dim: #1a3a4a;
    --text: #c8e8f0;
    --text2: #6a9ab0;
    --border: #1a4060;
    --glow: 0 0 10px rgba(0,255,136,0.3);
    --glow-red: 0 0 10px rgba(255,51,85,0.3);
    --glow-amber: 0 0 10px rgba(255,170,0,0.3);
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    min-height: 100vh;
    overflow-x: hidden;
    background-image: 
      radial-gradient(ellipse at 20% 50%, rgba(0,40,80,0.3) 0%, transparent 60%),
      radial-gradient(ellipse at 80% 20%, rgba(0,80,40,0.2) 0%, transparent 50%);
  }

  /* Scanline overlay */
  body::after {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(0,0,0,0.05) 2px,
      rgba(0,0,0,0.05) 4px
    );
    pointer-events: none;
    z-index: 1000;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    background: var(--bg2);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .logo {
    font-family: 'Orbitron', monospace;
    font-size: 18px;
    font-weight: 900;
    color: var(--green);
    text-shadow: var(--glow);
    letter-spacing: 3px;
  }

  .logo span { color: var(--text2); font-weight: 400; font-size: 12px; letter-spacing: 2px; display: block; }

  .header-center {
    text-align: center;
  }

  .quarter-display {
    font-family: 'Orbitron', monospace;
    font-size: 22px;
    color: var(--amber);
    text-shadow: var(--glow-amber);
    letter-spacing: 4px;
  }

  .date-sub { font-size: 11px; color: var(--text2); letter-spacing: 2px; margin-top: 2px; }

  .header-right { display: flex; gap: 16px; align-items: center; }

  .status-pill {
    padding: 4px 12px;
    border-radius: 2px;
    font-size: 11px;
    letter-spacing: 2px;
    font-weight: 600;
    border: 1px solid;
  }

  .status-normal { color: var(--green); border-color: var(--green); background: rgba(0,255,136,0.05); }
  .status-warning { color: var(--amber); border-color: var(--amber); background: rgba(255,170,0,0.05); }
  .status-critical { color: var(--red); border-color: var(--red); background: rgba(255,51,85,0.05); animation: pulse-red 1s infinite; }

  @keyframes pulse-red { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
  @keyframes pulse-green { 0%,100% { opacity:1; } 50% { opacity:0.6; } }

  .main { display: grid; grid-template-columns: 300px 1fr 280px; gap: 1px; background: var(--border); min-height: calc(100vh - 60px); }

  .panel { background: var(--bg); padding: 16px; overflow-y: auto; }
  .panel-title {
    font-family: 'Orbitron', monospace;
    font-size: 10px;
    letter-spacing: 3px;
    color: var(--text2);
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
    margin-bottom: 16px;
    text-transform: uppercase;
  }

  /* KPI CARDS */
  .kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px; }
  .kpi-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    padding: 10px 12px;
    position: relative;
    overflow: hidden;
    cursor: default;
    transition: border-color 0.3s;
  }
  .kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--green);
    transition: background 0.3s;
  }
  .kpi-card.warn::before { background: var(--amber); }
  .kpi-card.danger::before { background: var(--red); }
  .kpi-card.warn { border-color: rgba(255,170,0,0.3); }
  .kpi-card.danger { border-color: rgba(255,51,85,0.3); }

  .kpi-label { font-size: 9px; letter-spacing: 2px; color: var(--text2); text-transform: uppercase; }
  .kpi-value { font-family: 'Orbitron', monospace; font-size: 20px; font-weight: 700; margin: 4px 0 2px; }
  .kpi-value.green { color: var(--green); text-shadow: var(--glow); }
  .kpi-value.red { color: var(--red); text-shadow: var(--glow-red); }
  .kpi-value.amber { color: var(--amber); text-shadow: var(--glow-amber); }
  .kpi-delta { font-size: 10px; }
  .kpi-delta.up { color: var(--red); }
  .kpi-delta.down { color: var(--green); }
  .kpi-delta.upg { color: var(--green); }
  .kpi-delta.downd { color: var(--red); }
  .kpi-target { font-size: 9px; color: var(--text2); margin-top: 2px; }

  /* CONTROLS */
  .control-section { margin-bottom: 20px; }
  .control-label {
    font-size: 10px;
    letter-spacing: 2px;
    color: var(--text2);
    text-transform: uppercase;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .control-value {
    font-family: 'Orbitron', monospace;
    color: var(--amber);
    font-size: 13px;
  }

  .btn-group { display: flex; gap: 4px; flex-wrap: wrap; }
  .btn {
    padding: 6px 12px;
    border: 1px solid var(--border);
    background: var(--bg2);
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.2s;
    letter-spacing: 1px;
  }
  .btn:hover { background: var(--dim); border-color: var(--text2); }
  .btn.raise { border-color: rgba(255,51,85,0.5); }
  .btn.raise:hover { background: rgba(255,51,85,0.15); color: var(--red); border-color: var(--red); box-shadow: var(--glow-red); }
  .btn.cut { border-color: rgba(0,255,136,0.5); }
  .btn.cut:hover { background: rgba(0,255,136,0.1); color: var(--green); border-color: var(--green); box-shadow: var(--glow); }
  .btn.hold { border-color: rgba(255,170,0,0.5); }
  .btn.hold:hover { background: rgba(255,170,0,0.1); color: var(--amber); border-color: var(--amber); }
  .btn.action { border-color: var(--blue); color: var(--blue); }
  .btn.action:hover { background: rgba(0,170,255,0.1); box-shadow: 0 0 10px rgba(0,170,255,0.3); }
  .btn.danger-btn { border-color: var(--red); color: var(--red); }
  .btn.danger-btn:hover { background: rgba(255,51,85,0.2); }
  .btn.active-btn { background: rgba(0,255,136,0.1); border-color: var(--green); color: var(--green); }

  .advance-btn {
    width: 100%;
    padding: 14px;
    background: linear-gradient(135deg, rgba(0,255,136,0.05), rgba(0,204,102,0.1));
    border: 1px solid var(--green);
    color: var(--green);
    font-family: 'Orbitron', monospace;
    font-size: 13px;
    letter-spacing: 3px;
    cursor: pointer;
    transition: all 0.3s;
    text-transform: uppercase;
    margin-top: 16px;
  }
  .advance-btn:hover {
    background: rgba(0,255,136,0.15);
    box-shadow: var(--glow), inset 0 0 20px rgba(0,255,136,0.05);
    text-shadow: var(--glow);
  }
  .advance-btn:active { transform: scale(0.98); }

  /* CHART */
  .chart-area { background: var(--bg2); border: 1px solid var(--border); padding: 12px; margin-bottom: 12px; }
  .chart-title { font-size: 10px; letter-spacing: 2px; color: var(--text2); margin-bottom: 8px; }
  canvas { width: 100% !important; }

  /* EVENT LOG */
  .log-entry {
    font-size: 11px;
    padding: 8px 10px;
    border-left: 2px solid var(--border);
    margin-bottom: 6px;
    background: var(--bg2);
    line-height: 1.5;
    transition: all 0.3s;
  }
  .log-entry.new { border-left-color: var(--green); animation: fadeIn 0.5s ease; }
  .log-entry.warn { border-left-color: var(--amber); }
  .log-entry.crisis { border-left-color: var(--red); }
  .log-entry-time { font-size: 9px; color: var(--text2); margin-bottom: 2px; letter-spacing: 1px; }

  @keyframes fadeIn { from { opacity:0; transform: translateX(-10px); } to { opacity:1; transform: translateX(0); } }

  /* HEALTH BARS */
  .health-bar-wrap { margin-bottom: 12px; }
  .health-bar-label { display: flex; justify-content: space-between; font-size: 10px; letter-spacing: 1px; margin-bottom: 4px; }
  .health-bar-track { height: 6px; background: var(--dim); border-radius: 0; overflow: hidden; }
  .health-bar-fill { height: 100%; transition: width 0.8s ease, background 0.5s; border-radius: 0; }

  /* SCENARIO MODAL */
  .modal-overlay {
    position: fixed; top:0; left:0; right:0; bottom:0;
    background: rgba(0,0,0,0.85);
    z-index: 500;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(4px);
  }
  .modal {
    background: var(--bg2);
    border: 1px solid var(--green);
    padding: 32px;
    max-width: 600px;
    width: 90%;
    box-shadow: var(--glow), 0 0 60px rgba(0,255,136,0.05);
  }
  .modal h2 {
    font-family: 'Orbitron', monospace;
    color: var(--green);
    font-size: 20px;
    letter-spacing: 4px;
    margin-bottom: 8px;
    text-shadow: var(--glow);
  }
  .modal .subtitle { color: var(--text2); font-size: 12px; letter-spacing: 2px; margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 16px; }
  .scenario-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 24px; }
  .scenario-card {
    border: 1px solid var(--border);
    padding: 14px;
    cursor: pointer;
    transition: all 0.2s;
    background: var(--bg);
  }
  .scenario-card:hover { border-color: var(--amber); background: rgba(255,170,0,0.05); }
  .scenario-card.selected { border-color: var(--green); background: rgba(0,255,136,0.05); }
  .scenario-card h3 { font-size: 12px; color: var(--amber); letter-spacing: 1px; margin-bottom: 6px; font-family: 'Orbitron', monospace; }
  .scenario-card p { font-size: 10px; color: var(--text2); line-height: 1.5; }
  .difficulty { display: inline-block; font-size: 9px; padding: 2px 6px; border-radius: 0; margin-top: 6px; letter-spacing: 1px; }
  .d-easy { background: rgba(0,255,136,0.1); color: var(--green); border: 1px solid var(--green); }
  .d-med { background: rgba(255,170,0,0.1); color: var(--amber); border: 1px solid var(--amber); }
  .d-hard { background: rgba(255,51,85,0.1); color: var(--red); border: 1px solid var(--red); }

  .start-btn {
    width: 100%;
    padding: 16px;
    background: rgba(0,255,136,0.08);
    border: 1px solid var(--green);
    color: var(--green);
    font-family: 'Orbitron', monospace;
    font-size: 14px;
    letter-spacing: 4px;
    cursor: pointer;
    transition: all 0.3s;
  }
  .start-btn:hover { background: rgba(0,255,136,0.2); box-shadow: var(--glow); }

  /* GAME OVER */
  .gameover-overlay {
    position: fixed; top:0; left:0; right:0; bottom:0;
    background: rgba(0,0,0,0.92);
    z-index: 600;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(8px);
  }
  .gameover-box {
    text-align: center;
    max-width: 500px;
    padding: 48px;
    border: 1px solid;
  }
  .gameover-box.lose { border-color: var(--red); box-shadow: var(--glow-red), 0 0 100px rgba(255,51,85,0.05); }
  .gameover-box.win { border-color: var(--green); box-shadow: var(--glow), 0 0 100px rgba(0,255,136,0.05); }
  .gameover-title { font-family: 'Orbitron', monospace; font-size: 32px; font-weight: 900; letter-spacing: 6px; margin-bottom: 12px; }
  .lose .gameover-title { color: var(--red); text-shadow: var(--glow-red); }
  .win .gameover-title { color: var(--green); text-shadow: var(--glow); }
  .gameover-reason { font-size: 14px; color: var(--text2); margin-bottom: 8px; letter-spacing: 1px; line-height: 1.6; }
  .gameover-score { font-family: 'Orbitron', monospace; font-size: 40px; color: var(--amber); margin: 24px 0; text-shadow: var(--glow-amber); }
  .gameover-sub { font-size: 11px; color: var(--text2); letter-spacing: 2px; margin-bottom: 32px; }

  /* TOOLTIP */
  .tooltip { position: relative; }
  .tooltip:hover::after {
    content: attr(data-tip);
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg3);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 10px;
    padding: 6px 10px;
    white-space: nowrap;
    z-index: 200;
    pointer-events: none;
    letter-spacing: 0.5px;
  }

  .separator { height: 1px; background: var(--border); margin: 16px 0; }

  .mini-chart {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 32px;
    margin-top: 4px;
  }
  .mini-bar {
    flex: 1;
    background: var(--green);
    opacity: 0.6;
    transition: height 0.5s;
    min-height: 2px;
  }
  .mini-bar.red { background: var(--red); }
  .mini-bar.amber { background: var(--amber); }

  .ticker {
    display: flex;
    gap: 24px;
    padding: 6px 24px;
    background: var(--bg3);
    border-bottom: 1px solid var(--border);
    font-size: 11px;
    overflow: hidden;
  }
  .ticker-item { white-space: nowrap; }
  .ticker-item span { margin-left: 6px; }
  .tick-up { color: var(--green); }
  .tick-down { color: var(--red); }

  .scenario-badge {
    display: inline-block;
    padding: 3px 10px;
    border: 1px solid var(--amber);
    color: var(--amber);
    font-size: 10px;
    letter-spacing: 2px;
    margin-bottom: 16px;
    background: rgba(255,170,0,0.05);
  }

  .lag-indicator {
    background: var(--bg2);
    border: 1px solid rgba(0,170,255,0.3);
    padding: 8px 12px;
    margin-bottom: 8px;
    font-size: 10px;
    color: var(--blue);
    letter-spacing: 1px;
  }
  .lag-indicator strong { color: var(--cyan); }

  .win-meter {
    margin-bottom: 8px;
  }
  .win-meter-label { font-size: 9px; letter-spacing: 2px; color: var(--text2); margin-bottom: 3px; display: flex; justify-content: space-between; }
  .win-progress { height: 4px; background: var(--dim); }
  .win-progress-fill { height: 100%; background: var(--green); transition: width 1s ease; }
  .win-progress-fill.warn { background: var(--amber); }
  .win-progress-fill.bad { background: var(--red); }

  .score-display {
    font-family: 'Orbitron', monospace;
    font-size: 28px;
    color: var(--amber);
    text-align: center;
    text-shadow: var(--glow-amber);
    margin: 8px 0;
  }

  @media (max-width: 1100px) {
    .main { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<!-- SCENARIO SELECT MODAL -->
<div class="modal-overlay" id="scenarioModal">
  <div class="modal">
    <h2>FED CHAIR</h2>
    <div class="subtitle">MONETARY POLICY SIMULATOR — SELECT YOUR CRISIS</div>
    <div class="scenario-grid" id="scenarioGrid"></div>
    <button class="start-btn" onclick="startGame()">▶ ASSUME COMMAND</button>
  </div>
</div>

<!-- GAME OVER -->
<div class="gameover-overlay" id="gameoverOverlay" style="display:none">
  <div class="gameover-box" id="gameoverBox">
    <div class="gameover-title" id="gameoverTitle"></div>
    <div class="gameover-reason" id="gameoverReason"></div>
    <div class="gameover-score" id="gameoverScore"></div>
    <div class="gameover-sub" id="gameoverSub"></div>
    <button class="start-btn" onclick="location.reload()" style="margin-top:16px">↺ NEW TERM</button>
  </div>
</div>

<div class="header">
  <div>
    <div class="logo">FED CHAIR <span>MONETARY POLICY SIMULATOR</span></div>
  </div>
  <div class="header-center">
    <div class="quarter-display" id="quarterDisplay">Q1 2024</div>
    <div class="date-sub">FEDERAL OPEN MARKET COMMITTEE</div>
  </div>
  <div class="header-right">
    <div class="status-pill status-normal" id="economyStatus">STABLE</div>
    <div style="font-size:11px; color:var(--text2)">SCORE: <span style="color:var(--amber); font-family: Orbitron, monospace" id="scoreDisplay">0</span></div>
  </div>
</div>

<!-- TICKER -->
<div class="ticker" id="ticker"></div>

<div class="main">

  <!-- LEFT: CONTROLS -->
  <div class="panel">
    <div class="panel-title">⚡ POLICY CONTROLS</div>

    <div class="scenario-badge" id="scenarioBadge">SCENARIO LOADING</div>

    <div class="control-section">
      <div class="control-label">
        FEDERAL FUNDS RATE
        <span class="control-value" id="rateDisplay">5.25%</span>
      </div>
      <div class="btn-group">
        <button class="btn raise" onclick="adjustRate(0.5)">▲ +0.50%</button>
        <button class="btn raise" onclick="adjustRate(0.25)">▲ +0.25%</button>
        <button class="btn hold" onclick="adjustRate(0)">■ HOLD</button>
        <button class="btn cut" onclick="adjustRate(-0.25)">▼ -0.25%</button>
        <button class="btn cut" onclick="adjustRate(-0.5)">▼ -0.50%</button>
      </div>
      <div style="font-size:9px; color:var(--text2); margin-top:6px; letter-spacing:1px;">
        NEXT FOMC: <span id="nextFomc" style="color:var(--amber)">NEXT QUARTER</span>
      </div>
    </div>

    <div class="separator"></div>

    <div class="control-section">
      <div class="control-label">
        QUANTITATIVE POLICY
        <span class="control-value" id="qeDisplay">NEUTRAL</span>
      </div>
      <div class="btn-group">
        <button class="btn raise" onclick="setQE('QT_AGGRESSIVE')" id="btn-qt2">QT $120B/MO</button>
        <button class="btn raise" onclick="setQE('QT')" id="btn-qt1">QT $60B/MO</button>
        <button class="btn hold active-btn" onclick="setQE('NEUTRAL')" id="btn-neutral">NEUTRAL</button>
        <button class="btn cut" onclick="setQE('QE')" id="btn-qe1">QE $60B/MO</button>
        <button class="btn cut" onclick="setQE('QE_AGGRESSIVE')" id="btn-qe2">QE $120B/MO</button>
      </div>
    </div>

    <div class="separator"></div>

    <div class="control-section">
      <div class="control-label">EMERGENCY TOOLS</div>
      <div class="btn-group">
        <button class="btn action tooltip" data-tip="Inject $500B liquidity to banks" onclick="bankBailout()">🏦 BANK BAILOUT</button>
        <button class="btn action tooltip" data-tip="Buy USD to defend currency" onclick="currencyDefense()">💱 FX DEFENSE</button>
        <button class="btn danger-btn tooltip" data-tip="Shock the market — last resort" onclick="emergencyHike()">⚡ EMERGENCY HIKE</button>
      </div>
    </div>

    <div class="separator"></div>

    <div class="control-section">
      <div class="control-label">FORWARD GUIDANCE</div>
      <div class="btn-group">
        <button class="btn cut" onclick="setGuidance('dovish')">🕊 DOVISH</button>
        <button class="btn hold active-btn" onclick="setGuidance('neutral')" id="guidance-neutral">◆ NEUTRAL</button>
        <button class="btn raise" onclick="setGuidance('hawkish')">🦅 HAWKISH</button>
      </div>
      <div style="font-size:9px; color:var(--text2); margin-top:6px; letter-spacing:1px;">
        MARKET READS YOUR WORDS — MOVES BEFORE YOU ACT
      </div>
    </div>

    <div class="separator"></div>

    <div class="lag-indicator">
      ⏳ <strong>LAG EFFECT:</strong> Rate changes hit economy in <strong>3-6 quarters</strong>. You're flying on delayed data.
    </div>

    <button class="advance-btn" onclick="advanceQuarter()">▶ ADVANCE QUARTER</button>

    <div style="margin-top:12px;">
      <div class="control-label">TERM PROGRESS</div>
      <div class="win-meter">
        <div class="win-meter-label"><span>QUARTERS SERVED</span><span id="termProgress">0 / 32</span></div>
        <div class="win-progress"><div class="win-progress-fill" id="termBar" style="width:0%"></div></div>
      </div>
    </div>
  </div>

  <!-- CENTER: DASHBOARD -->
  <div class="panel">
    <div class="panel-title">📊 ECONOMIC DASHBOARD</div>

    <div class="kpi-grid" id="kpiGrid"></div>

    <div class="chart-area">
      <div class="chart-title">ECONOMIC INDICATORS — 12 QUARTER TREND</div>
      <canvas id="mainChart" height="180"></canvas>
    </div>

    <div class="chart-area">
      <div class="chart-title">BOND YIELD CURVE (3M → 10Y)</div>
      <canvas id="yieldChart" height="100"></canvas>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:8px;">
      <div class="chart-area" style="margin-bottom:0">
        <div class="chart-title">UNEMPLOYMENT TREND</div>
        <canvas id="unempChart" height="80"></canvas>
      </div>
      <div class="chart-area" style="margin-bottom:0">
        <div class="chart-title">GDP GROWTH TREND</div>
        <canvas id="gdpChart" height="80"></canvas>
      </div>
    </div>
  </div>

  <!-- RIGHT: LOGS & HEALTH -->
  <div class="panel">
    <div class="panel-title">🏥 SYSTEM HEALTH</div>

    <div class="score-display" id="scoreDisplayRight">0</div>
    <div style="font-size:9px; text-align:center; color:var(--text2); letter-spacing:2px; margin-bottom:12px;">CHAIRMAN SCORE</div>

    <div id="healthBars"></div>

    <div class="separator"></div>

    <div class="panel-title" style="margin-top:0">📡 FOMC INTEL FEED</div>
    <div id="eventLog"></div>
  </div>

</div>

<script>
// ============================================================
// GAME STATE
// ============================================================
const SCENARIOS = [
  {
    id: 'soft_landing',
    name: '2022 SOFT LANDING',
    desc: 'Inflation at 8.5% post-COVID stimulus. Tame it without triggering recession. The Powell challenge.',
    difficulty: 'MEDIUM',
    diffClass: 'd-med',
    initial: { rate: 0.25, cpi: 8.5, pce: 7.8, unemployment: 3.6, gdp: 3.2, debt_gdp: 95, deficit: 5.5, bondYield10y: 2.8, dxy: 96, tradeBalance: -80, bankStability: 85, publicTrust: 75, marketConf: 80, qeMode: 'NEUTRAL', guidance: 'hawkish', year: 2022, quarter: 1 }
  },
  {
    id: 'stagflation',
    name: '1970s STAGFLATION',
    desc: 'Inflation AND unemployment both rising. Supply shock. No good moves — only tradeoffs.',
    difficulty: 'HARD',
    diffClass: 'd-hard',
    initial: { rate: 5.5, cpi: 11.0, pce: 10.2, unemployment: 8.5, gdp: -0.5, debt_gdp: 35, deficit: 3.5, bondYield10y: 8.5, dxy: 85, tradeBalance: -15, bankStability: 70, publicTrust: 55, marketConf: 50, qeMode: 'NEUTRAL', guidance: 'neutral', year: 1975, quarter: 1 }
  },
  {
    id: 'financial_crisis',
    name: '2008 COLLAPSE',
    desc: 'Banks failing. Credit frozen. Unemployment skyrocketing. Prevent a second Great Depression.',
    difficulty: 'HARD',
    diffClass: 'd-hard',
    initial: { rate: 4.5, cpi: 4.2, pce: 3.8, unemployment: 6.5, gdp: -2.5, debt_gdp: 65, deficit: 8.0, bondYield10y: 4.2, dxy: 82, tradeBalance: -55, bankStability: 30, publicTrust: 45, marketConf: 25, qeMode: 'NEUTRAL', guidance: 'neutral', year: 2008, quarter: 3 }
  },
  {
    id: 'stable_growth',
    name: 'GOLDILOCKS ERA',
    desc: 'Economy running hot. Keep inflation at bay without cooling this perfect expansion.',
    difficulty: 'EASY',
    diffClass: 'd-easy',
    initial: { rate: 2.0, cpi: 2.8, pce: 2.4, unemployment: 4.2, gdp: 2.8, debt_gdp: 78, deficit: 4.0, bondYield10y: 3.2, dxy: 96, tradeBalance: -45, bankStability: 88, publicTrust: 82, marketConf: 85, qeMode: 'NEUTRAL', guidance: 'neutral', year: 2018, quarter: 1 }
  },
  {
    id: 'debt_spiral',
    name: 'DEBT SPIRAL',
    desc: '$40T debt. Yields spiking. Markets losing faith. Can you restore confidence before the bond revolt?',
    difficulty: 'HARD',
    diffClass: 'd-hard',
    initial: { rate: 6.5, cpi: 5.8, pce: 5.2, unemployment: 5.8, gdp: 0.5, debt_gdp: 145, deficit: 12.0, bondYield10y: 7.8, dxy: 78, tradeBalance: -110, bankStability: 55, publicTrust: 35, marketConf: 30, qeMode: 'NEUTRAL', guidance: 'hawkish', year: 2026, quarter: 1 }
  },
  {
    id: 'emerging_crisis',
    name: 'CURRENCY COLLAPSE',
    desc: 'Dollar surging from rate hikes is destroying emerging markets. Global contagion risk rising fast.',
    difficulty: 'MEDIUM',
    diffClass: 'd-med',
    initial: { rate: 7.0, cpi: 3.2, pce: 2.8, unemployment: 4.8, gdp: 1.8, debt_gdp: 105, deficit: 6.5, bondYield10y: 5.8, dxy: 118, tradeBalance: -95, bankStability: 65, publicTrust: 60, marketConf: 55, qeMode: 'QT', guidance: 'hawkish', year: 2025, quarter: 2 }
  }
];

let selectedScenario = SCENARIOS[0];
let G = {}; // game state
let history = { cpi:[], gdp:[], unemployment:[], rate:[], yield10y:[], quarters:[] };
let eventLog = [];
let pendingActions = []; // lag effect queue
let quarterCount = 0;
let score = 0;
let gameOver = false;
let guidance = 'neutral';
let qeMode = 'NEUTRAL';

// ============================================================
// SCENARIO SELECTION
// ============================================================
function renderScenarios() {
  const grid = document.getElementById('scenarioGrid');
  grid.innerHTML = SCENARIOS.map((s,i) => `
    <div class="scenario-card ${i===0?'selected':''}" onclick="selectScenario(${i})" id="sc-${i}">
      <h3>${s.name}</h3>
      <p>${s.desc}</p>
      <span class="difficulty ${s.diffClass}">${s.difficulty}</span>
    </div>
  `).join('');
}

function selectScenario(i) {
  selectedScenario = SCENARIOS[i];
  document.querySelectorAll('.scenario-card').forEach((el,j) => {
    el.classList.toggle('selected', i===j);
  });
}

function startGame() {
  document.getElementById('scenarioModal').style.display = 'none';
  initGame();
}

// ============================================================
// INIT
// ============================================================
function initGame() {
  G = { ...selectedScenario.initial };
  G.qeMode = G.qeMode || 'NEUTRAL';
  guidance = G.guidance || 'neutral';
  qeMode = G.qeMode;
  history = { cpi:[], gdp:[], unemployment:[], rate:[], yield10y:[], quarters:[] };
  pendingActions = [];
  quarterCount = 0;
  score = 0;
  eventLog = [];
  gameOver = false;

  document.getElementById('scenarioBadge').textContent = selectedScenario.name;
  updateQEButtons();
  updateGuidanceButtons();
  updateDisplays();
  addLog(`CHAIRMAN CONFIRMED — ${selectedScenario.name} begins. Target: 2% inflation, ~4% unemployment.`, 'new');
  addLog(`Initial conditions: CPI ${G.cpi.toFixed(1)}% | Unemployment ${G.unemployment.toFixed(1)}% | Rate ${G.rate.toFixed(2)}%`, 'warn');

  setTimeout(() => renderCharts(), 100);
}

// ============================================================
// CONTROLS
// ============================================================
function adjustRate(delta) {
  if (gameOver) return;
  const oldRate = G.rate;
  G.rate = Math.max(0, Math.min(20, G.rate + delta));
  if (delta === 0) {
    addLog(`FOMC DECISION: Rates held at ${G.rate.toFixed(2)}%. ${guidance === 'dovish' ? 'Dovish tone — markets rally.' : guidance === 'hawkish' ? 'Hawkish stance maintained.' : 'Committee monitors incoming data.'}`, 'new');
  } else if (delta > 0) {
    addLog(`🔺 RATE HIKE: +${delta.toFixed(2)}% → ${G.rate.toFixed(2)}%. Markets price in tighter conditions. Mortgage rates to follow in 1-2 quarters.`, delta >= 0.5 ? 'crisis' : 'warn');
    score -= delta > 0.25 ? 5 : 2;
  } else {
    addLog(`🔻 RATE CUT: ${delta.toFixed(2)}% → ${G.rate.toFixed(2)}%. Stimulus injected. Dollar weakens. Borrowing costs ease.`, 'new');
  }

  // Queue lag effects
  pendingActions.push({ type: 'rate_change', delta, quartersLeft: 3, original: oldRate });
  updateDisplays();
}

function setQE(mode) {
  if (gameOver) return;
  qeMode = mode;
  G.qeMode = mode;
  const labels = { QT_AGGRESSIVE:'QT $120B/MO', QT:'QT $60B/MO', NEUTRAL:'NEUTRAL', QE:'QE $60B/MO', QE_AGGRESSIVE:'QE $120B/MO' };
  const msgs = {
    QT_AGGRESSIVE: '⚡ AGGRESSIVE QT: Fed draining $120B/month. Bond market tightening. Liquidity shrinking.',
    QT: 'QT ACTIVE: Reducing balance sheet $60B/month. Gradual tightening.',
    NEUTRAL: 'Balance sheet policy neutral. No active buying or selling.',
    QE: 'QE ACTIVE: $60B/month bond purchases. Liquidity injected into system.',
    QE_AGGRESSIVE: '💰 AGGRESSIVE QE: $120B/month. Flood of liquidity. Inflation risk elevated.'
  };
  addLog(msgs[mode], mode.includes('QE') ? 'warn' : 'new');
  updateQEButtons();
  updateDisplays();
}

function setGuidance(g) {
  if (gameOver) return;
  guidance = g;
  const msgs = {
    dovish: "🕊 DOVISH GUIDANCE issued. Markets immediately price in cuts. Bond yields drop. Risk assets rally.",
    neutral: "◆ NEUTRAL GUIDANCE. Data-dependent stance. Markets await next CPI print.",
    hawkish: "🦅 HAWKISH GUIDANCE. Markets price in further hikes. Dollar strengthens. Tech stocks drop."
  };
  addLog(msgs[g], g === 'hawkish' ? 'warn' : 'new');
  updateGuidanceButtons();
}

function bankBailout() {
  if (gameOver) return;
  G.bankStability = Math.min(100, G.bankStability + 25);
  G.marketConf = Math.min(100, G.marketConf + 10);
  G.cpi = G.cpi + 0.8; // inflationary
  score -= 15;
  addLog('🏦 EMERGENCY: $500B bank bailout authorized. Bank stability restored. Moral hazard risk. Inflationary pressure added.', 'crisis');
  updateDisplays();
}

function currencyDefense() {
  if (gameOver) return;
  G.dxy = Math.min(130, G.dxy + 5);
  G.publicTrust = Math.min(100, G.publicTrust + 5);
  score -= 8;
  addLog('💱 FX INTERVENTION: USD support operation deployed. $200B reserves committed. Short term DXY stabilization.', 'warn');
  updateDisplays();
}

function emergencyHike() {
  if (gameOver) return;
  G.rate = Math.min(20, G.rate + 1.0);
  G.cpi = Math.max(0, G.cpi - 1.5);
  G.marketConf = Math.max(0, G.marketConf - 15);
  G.unemployment = G.unemployment + 0.5;
  score -= 20;
  addLog('⚡ EMERGENCY HIKE +1.0%! Shock and awe tactic. Inflation expectations crushed. Markets in turmoil. Recession risk elevated.', 'crisis');
  updateDisplays();
}

// ============================================================
// ADVANCE QUARTER — CORE SIMULATION ENGINE
// ============================================================
function advanceQuarter() {
  if (gameOver) return;

  quarterCount++;
  const q = (G.quarter % 4) + 1;
  const yr = G.year + Math.floor(G.quarter / 4);
  G.quarter = (G.quarter % 4) + 1;
  if (G.quarter === 1) G.year++;

  // ---- ECONOMIC SIMULATION ENGINE ----

  // 1. RATE EFFECTS (with lag)
  const effectiveRateChange = G.rate - (history.rate[history.rate.length-3] || G.rate);

  // 2. INFLATION DYNAMICS
  let cpiDelta = 0;
  cpiDelta -= effectiveRateChange * 0.4; // rate hikes cool inflation (lagged)
  if (qeMode === 'QE') cpiDelta += 0.4;
  if (qeMode === 'QE_AGGRESSIVE') cpiDelta += 0.9;
  if (qeMode === 'QT') cpiDelta -= 0.25;
  if (qeMode === 'QT_AGGRESSIVE') cpiDelta -= 0.5;
  if (guidance === 'dovish') cpiDelta += 0.2; // expectations
  if (guidance === 'hawkish') cpiDelta -= 0.2;
  cpiDelta += (Math.random() - 0.48) * 0.5; // supply shock noise
  if (G.unemployment < 3.5) cpiDelta += 0.3; // wage pressure
  G.cpi = Math.max(0.1, G.cpi + cpiDelta);

  // 3. UNEMPLOYMENT DYNAMICS
  let unempDelta = 0;
  unempDelta += effectiveRateChange * 0.3;
  if (G.gdp < 0) unempDelta += 0.4;
  if (G.gdp > 3) unempDelta -= 0.3;
  if (qeMode === 'QE_AGGRESSIVE') unempDelta -= 0.2;
  if (qeMode === 'QT_AGGRESSIVE') unempDelta += 0.2;
  unempDelta += (Math.random() - 0.5) * 0.2;
  G.unemployment = Math.max(2, Math.min(25, G.unemployment + unempDelta));

  // 4. GDP DYNAMICS
  let gdpDelta = 0;
  gdpDelta -= effectiveRateChange * 0.5;
  if (qeMode === 'QE') gdpDelta += 0.4;
  if (qeMode === 'QE_AGGRESSIVE') gdpDelta += 0.8;
  if (qeMode === 'QT') gdpDelta -= 0.2;
  if (qeMode === 'QT_AGGRESSIVE') gdpDelta -= 0.4;
  if (guidance === 'dovish') gdpDelta += 0.15;
  if (guidance === 'hawkish') gdpDelta -= 0.1;
  gdpDelta += (Math.random() - 0.5) * 0.4;
  if (G.bankStability < 40) gdpDelta -= 0.8;
  G.gdp = Math.max(-8, Math.min(8, G.gdp + gdpDelta));

  // 5. BOND YIELD
  let yieldDelta = 0;
  yieldDelta += (G.rate - G.bondYield10y) * 0.15;
  if (G.cpi > 5) yieldDelta += 0.2;
  if (G.debt_gdp > 120) yieldDelta += 0.15;
  if (G.publicTrust < 40) yieldDelta += 0.3;
  if (qeMode === 'QE' || qeMode === 'QE_AGGRESSIVE') yieldDelta -= 0.2;
  yieldDelta += (Math.random() - 0.5) * 0.15;
  G.bondYield10y = Math.max(0.1, Math.min(15, G.bondYield10y + yieldDelta));

  // 6. DXY
  const dxyDelta = (G.rate - 3) * 0.5 - (G.cpi - 2) * 0.2 + (Math.random()-0.5)*1.5;
  G.dxy = Math.max(60, Math.min(140, G.dxy + dxyDelta));

  // 7. DEBT
  G.deficit = Math.max(0, G.deficit + (G.rate > 5 ? 0.3 : -0.1) + (G.gdp < 0 ? 0.5 : -0.2));
  G.debt_gdp = G.debt_gdp + (G.deficit/4) - (G.gdp * 0.15);

  // 8. BANK STABILITY
  if (G.gdp < -2) G.bankStability = Math.max(0, G.bankStability - 8);
  if (G.bondYield10y > 8) G.bankStability = Math.max(0, G.bankStability - 5);
  if (qeMode === 'QE' || qeMode === 'QE_AGGRESSIVE') G.bankStability = Math.min(100, G.bankStability + 2);

  // 9. TRUST & CONFIDENCE
  const trustDelta = 
    (G.cpi < 3 ? 3 : G.cpi > 6 ? -4 : -1) +
    (G.unemployment < 4.5 ? 2 : G.unemployment > 7 ? -3 : 0) +
    (G.gdp > 2 ? 2 : G.gdp < 0 ? -3 : 0) +
    (Math.random() - 0.5) * 3;
  G.publicTrust = Math.max(0, Math.min(100, G.publicTrust + trustDelta));
  G.marketConf = Math.max(0, Math.min(100, G.marketConf + trustDelta * 0.8 + (Math.random()-0.5)*4));

  // ---- RECORD HISTORY ----
  const qLabel = `Q${G.quarter} ${G.year}`;
  history.cpi.push(G.cpi);
  history.gdp.push(G.gdp);
  history.unemployment.push(G.unemployment);
  history.rate.push(G.rate);
  history.yield10y.push(G.bondYield10y);
  history.quarters.push(qLabel);
  if (history.quarters.length > 16) {
    Object.keys(history).forEach(k => { if(history[k].length > 16) history[k].shift(); });
  }

  // ---- SCORE ----
  const cpiScore = Math.max(0, 20 - Math.abs(G.cpi - 2) * 5);
  const unempScore = Math.max(0, 15 - Math.abs(G.unemployment - 4) * 3);
  const gdpScore = Math.max(0, G.gdp > 0 ? 10 : 0);
  const trustScore = G.publicTrust / 20;
  score += Math.round(cpiScore + unempScore + gdpScore + trustScore);

  // ---- EVENTS ----
  generateEvents();

  // ---- CHECK WIN/LOSE ----
  checkGameConditions();

  document.getElementById('quarterDisplay').textContent = `Q${G.quarter} ${G.year}`;
  document.getElementById('termProgress').textContent = `${quarterCount} / 32`;
  document.getElementById('termBar').style.width = `${(quarterCount/32)*100}%`;

  updateDisplays();
  renderCharts();

  if (quarterCount >= 32 && !gameOver) {
    triggerWin();
  }
}

// ============================================================
// EVENTS GENERATOR
// ============================================================
function generateEvents() {
  const events = [];

  if (G.cpi > 8) events.push({ msg: `⚠️ CPI surges to ${G.cpi.toFixed(1)}%. Congressional pressure mounting. "Fed behind the curve" headlines dominate.`, type:'crisis' });
  else if (G.cpi > 5) events.push({ msg: `📈 Inflation at ${G.cpi.toFixed(1)}% — above target. Markets expect tighter policy.`, type:'warn' });
  else if (G.cpi < 1.5) events.push({ msg: `📉 Deflation risk: CPI at ${G.cpi.toFixed(1)}%. Consider easing.`, type:'warn' });
  else events.push({ msg: `✅ CPI at ${G.cpi.toFixed(1)}%. ${Math.abs(G.cpi-2) < 0.5 ? 'On target. Credibility intact.' : 'Slowly converging to target.'}`, type:'new' });

  if (G.unemployment > 8) events.push({ msg: `🚨 UNEMPLOYMENT ${G.unemployment.toFixed(1)}% — recessionary levels. Political pressure intense. Dual mandate failing.`, type:'crisis' });
  else if (G.gdp < -1) events.push({ msg: `📉 GDP contraction ${G.gdp.toFixed(1)}%. Two consecutive negative quarters = recession confirmed.`, type:'crisis' });
  else if (G.gdp > 3) events.push({ msg: `🚀 GDP ${G.gdp.toFixed(1)}% — strong growth. Watch for overheating.`, type:'new' });

  if (G.bankStability < 40) events.push({ msg: `🏦 BANK STRESS ELEVATED. Credit markets tightening. Consider emergency liquidity operations.`, type:'crisis' });
  if (G.bondYield10y > 7) events.push({ msg: `💸 10Y YIELD ${G.bondYield10y.toFixed(2)}% — BOND MARKET REVOLT signals. Government borrowing costs exploding.`, type:'crisis' });
  if (G.debt_gdp > 130) events.push({ msg: `📊 Debt/GDP at ${G.debt_gdp.toFixed(0)}%. Credit rating agencies issuing warnings.`, type:'warn' });
  if (G.publicTrust < 30) events.push({ msg: `⚠️ PUBLIC TRUST CRITICAL at ${G.publicTrust.toFixed(0)}. Fed independence under attack.`, type:'crisis' });
  if (G.dxy > 115) events.push({ msg: `💱 DXY at ${G.dxy.toFixed(0)} — dollar TOO strong. EM debt crisis signals. Exports crushed.`, type:'warn' });

  // Random macro events
  const rand = Math.random();
  if (rand < 0.08) events.push({ msg: `🛢 OIL SHOCK: Supply disruption adds +1.2% to inflation expectations. External shock outside Fed control.`, type:'warn' });
  else if (rand < 0.12) events.push({ msg: `🌍 GEOPOLITICAL: Regional conflict disrupts supply chains. Core goods inflation ticking up.`, type:'warn' });
  else if (rand < 0.15) events.push({ msg: `🤖 PRODUCTIVITY SURGE: Tech sector boom. GDP upside surprise. Goldilocks conditions possible.`, type:'new' });
  else if (rand < 0.17) events.push({ msg: `🏠 HOUSING MARKET: Mortgage rates crushing homebuyers. Construction permits at 5-year low. Real economy cooling.`, type:'warn' });

  events.forEach(e => addLog(e.msg, e.type));
}

// ============================================================
// WIN / LOSE CONDITIONS
// ============================================================
function checkGameConditions() {
  if (gameOver) return;

  if (G.cpi > 18) triggerLose('HYPERINFLATION', `CPI reached ${G.cpi.toFixed(1)}%. The currency is collapsing. Citizens can't afford basic necessities. The Fed has lost all credibility.`);
  else if (G.unemployment > 18) triggerLose('GREAT DEPRESSION', `Unemployment at ${G.unemployment.toFixed(1)}%. Mass unemployment, social unrest, breadlines. History will judge this policy failure.`);
  else if (G.bankStability < 5) triggerLose('FINANCIAL SYSTEM COLLAPSE', `Bank stability at ${G.bankStability.toFixed(0)}%. Credit completely frozen. The 2008 crisis looks mild by comparison.`);
  else if (G.publicTrust < 5) triggerLose('FED INDEPENDENCE DESTROYED', `Public trust at ${G.publicTrust.toFixed(0)}%. Congress has voted to abolish the Federal Reserve. Policy credibility is gone forever.`);
  else if (G.bondYield10y > 12) triggerLose('BOND MARKET REVOLT', `10Y yields hit ${G.bondYield10y.toFixed(1)}%. The US can no longer service its debt. The dollar is losing reserve currency status.`);
  else if (G.debt_gdp > 180) triggerLose('SOVEREIGN DEBT CRISIS', `Debt/GDP at ${G.debt_gdp.toFixed(0)}%. The US is technically insolvent. IMF intervention requested.`);
}

function triggerLose(reason, detail) {
  gameOver = true;
  const box = document.getElementById('gameoverBox');
  box.className = 'gameover-box lose';
  document.getElementById('gameoverTitle').textContent = reason;
  document.getElementById('gameoverReason').textContent = detail;
  document.getElementById('gameoverScore').textContent = score.toLocaleString();
  document.getElementById('gameoverSub').textContent = `${quarterCount} QUARTERS SERVED — TERM ENDED EARLY`;
  document.getElementById('gameoverOverlay').style.display = 'flex';
}

function triggerWin() {
  gameOver = true;
  const avgCpi = history.cpi.reduce((a,b)=>a+b,0)/history.cpi.length;
  const avgUnemp = history.unemployment.reduce((a,b)=>a+b,0)/history.unemployment.length;
  const grade = score > 1500 ? 'LEGENDARY' : score > 1000 ? 'EXCELLENT' : score > 600 ? 'COMPETENT' : 'MEDIOCRE';
  const box = document.getElementById('gameoverBox');
  box.className = 'gameover-box win';
  document.getElementById('gameoverTitle').textContent = '8-YEAR TERM COMPLETE';
  document.getElementById('gameoverReason').textContent = `Avg CPI: ${avgCpi.toFixed(1)}% | Avg Unemployment: ${avgUnemp.toFixed(1)}% | Scenario: ${selectedScenario.name}\nRating: ${grade}`;
  document.getElementById('gameoverScore').textContent = score.toLocaleString();
  document.getElementById('gameoverSub').textContent = `CHAIRMAN RATING: ${grade}`;
  document.getElementById('gameoverOverlay').style.display = 'flex';
}

// ============================================================
// DISPLAY UPDATES
// ============================================================
function updateDisplays() {
  document.getElementById('rateDisplay').textContent = G.rate.toFixed(2) + '%';
  document.getElementById('qeDisplay').textContent = { QT_AGGRESSIVE:'QT AGGRESSIVE', QT:'QT ACTIVE', NEUTRAL:'NEUTRAL', QE:'QE ACTIVE', QE_AGGRESSIVE:'QE AGGRESSIVE' }[qeMode];
  document.getElementById('scoreDisplay').textContent = score.toLocaleString();
  document.getElementById('scoreDisplayRight').textContent = score.toLocaleString();

  // Economy status
  const statusEl = document.getElementById('economyStatus');
  if (G.cpi > 8 || G.unemployment > 10 || G.bankStability < 30 || G.publicTrust < 20) {
    statusEl.textContent = 'CRITICAL'; statusEl.className = 'status-pill status-critical';
  } else if (G.cpi > 4 || G.unemployment > 6 || G.gdp < 0 || G.publicTrust < 50) {
    statusEl.textContent = 'WARNING'; statusEl.className = 'status-pill status-warning';
  } else {
    statusEl.textContent = 'STABLE'; statusEl.className = 'status-pill status-normal';
  }

  renderKPIs();
  renderHealthBars();
  renderTicker();
}

function getKpiClass(value, target, good, warn) {
  const diff = Math.abs(value - target);
  if (diff <= good) return 'green';
  if (diff <= warn) return 'amber';
  return 'red';
}

function renderKPIs() {
  const kpis = [
    { label:'CPI INFLATION', value: G.cpi.toFixed(1)+'%', color: getKpiClass(G.cpi,2,0.5,2), delta: history.cpi.length>1 ? (G.cpi-history.cpi[history.cpi.length-2]).toFixed(1) : '0', target:'TARGET: 2%', higherBad:true },
    { label:'PCE INFLATION', value: G.pce.toFixed(1)+'%', color: getKpiClass(G.pce,2,0.5,2), delta:'0', target:'FED PREFERRED', higherBad:true },
    { label:'UNEMPLOYMENT', value: G.unemployment.toFixed(1)+'%', color: getKpiClass(G.unemployment,4,0.5,2), delta: history.unemployment.length>1?(G.unemployment-history.unemployment[history.unemployment.length-2]).toFixed(1):'0', target:'TARGET: ~4%', higherBad:true },
    { label:'GDP GROWTH', value: G.gdp.toFixed(1)+'%', color: G.gdp > 2 ? 'green' : G.gdp > 0 ? 'amber' : 'red', delta: history.gdp.length>1?(G.gdp-history.gdp[history.gdp.length-2]).toFixed(1):'0', target:'TARGET: ~2%', higherBad:false },
    { label:'FED FUNDS RATE', value: G.rate.toFixed(2)+'%', color:'amber', delta:'0', target:'POLICY RATE', higherBad:false },
    { label:'10Y BOND YIELD', value: G.bondYield10y.toFixed(2)+'%', color: G.bondYield10y > 7 ? 'red' : G.bondYield10y > 5 ? 'amber' : 'green', delta: history.yield10y.length>1?(G.bondYield10y-history.yield10y[history.yield10y.length-2]).toFixed(2):'0', target:'TRUST GAUGE', higherBad:true },
    { label:'DOLLAR INDEX', value: G.dxy.toFixed(0), color: G.dxy > 115 ? 'red' : G.dxy < 80 ? 'red' : 'green', delta:'0', target:'CURRENCY STRENGTH', higherBad:false },
    { label:'DEBT / GDP', value: G.debt_gdp.toFixed(0)+'%', color: G.debt_gdp > 140 ? 'red' : G.debt_gdp > 110 ? 'amber' : 'green', delta:'0', target:'DANGER: >130%', higherBad:true },
  ];

  // PCE tracks CPI roughly
  G.pce = G.cpi * 0.88;

  document.getElementById('kpiGrid').innerHTML = kpis.map(k => {
    const dval = parseFloat(k.delta);
    const dclass = k.higherBad ? (dval > 0 ? 'up' : 'down') : (dval > 0 ? 'upg' : 'downd');
    const dsym = dval > 0 ? '▲' : dval < 0 ? '▼' : '—';
    const cardClass = k.color === 'red' ? 'danger' : k.color === 'amber' ? 'warn' : '';
    return `<div class="kpi-card ${cardClass}">
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value ${k.color}">${k.value}</div>
      <div class="kpi-delta ${dclass}">${dsym} ${Math.abs(dval).toFixed(1)} QoQ</div>
      <div class="kpi-target">${k.target}</div>
    </div>`;
  }).join('');
}

function renderHealthBars() {
  const bars = [
    { label:'PUBLIC TRUST', value: G.publicTrust },
    { label:'MARKET CONFIDENCE', value: G.marketConf },
    { label:'BANK STABILITY', value: G.bankStability },
    { label:'FED CREDIBILITY', value: Math.max(0, 100 - Math.abs(G.cpi-2)*8 - (G.unemployment>6?(G.unemployment-6)*5:0)) },
  ];

  document.getElementById('healthBars').innerHTML = bars.map(b => {
    const fillClass = b.value > 60 ? '' : b.value > 30 ? 'warn' : 'bad';
    const color = b.value > 60 ? 'var(--green)' : b.value > 30 ? 'var(--amber)' : 'var(--red)';
    return `<div class="health-bar-wrap">
      <div class="health-bar-label"><span>${b.label}</span><span style="color:${color}">${b.value.toFixed(0)}%</span></div>
      <div class="health-bar-track"><div class="health-bar-fill ${fillClass}" style="width:${b.value}%;background:${color}"></div></div>
    </div>`;
  }).join('');
}

function renderTicker() {
  const items = [
    `FED RATE: ${G.rate.toFixed(2)}%`,
    `CPI: <span class="${G.cpi>4?'tick-down':'tick-up'}">${G.cpi.toFixed(1)}%</span>`,
    `UNEMPLOYMENT: <span class="${G.unemployment>5?'tick-down':'tick-up'}">${G.unemployment.toFixed(1)}%</span>`,
    `GDP: <span class="${G.gdp>0?'tick-up':'tick-down'}">${G.gdp.toFixed(1)}%</span>`,
    `10Y YIELD: ${G.bondYield10y.toFixed(2)}%`,
    `DXY: ${G.dxy.toFixed(0)}`,
    `DEBT/GDP: ${G.debt_gdp.toFixed(0)}%`,
    `SCORE: ${score.toLocaleString()}`
  ];
  document.getElementById('ticker').innerHTML = items.map(i => `<div class="ticker-item">${i}</div>`).join('');
}

function addLog(msg, type='new') {
  const q = `Q${G.quarter} ${G.year}`;
  eventLog.unshift({ msg, type, q });
  if (eventLog.length > 20) eventLog.pop();
  const logEl = document.getElementById('eventLog');
  logEl.innerHTML = eventLog.slice(0,12).map(e =>
    `<div class="log-entry ${e.type}">
      <div class="log-entry-time">${e.q}</div>
      ${e.msg}
    </div>`
  ).join('');
}

function updateQEButtons() {
  ['qt2','qt1','neutral','qe1','qe2'].forEach(id => {
    const map = { qt2:'QT_AGGRESSIVE', qt1:'QT', neutral:'NEUTRAL', qe1:'QE', qe2:'QE_AGGRESSIVE' };
    const btn = document.getElementById('btn-'+id);
    if (btn) btn.classList.toggle('active-btn', map[id] === qeMode);
  });
}

function updateGuidanceButtons() {
  ['dovish','neutral','hawkish'].forEach(g => {
    const btn = document.getElementById('guidance-'+g);
    if(btn) btn.classList.toggle('active-btn', g === guidance);
  });
  // re-render guidance buttons
  const btns = document.querySelectorAll('[onclick*="setGuidance"]');
  btns.forEach(b => {
    const g = b.getAttribute('onclick').match(/setGuidance\('(\w+)'\)/)[1];
    b.classList.toggle('active-btn', g === guidance);
  });
}

// ============================================================
// CHARTS
// ============================================================
let charts = {};

function renderCharts() {
  const qs = history.quarters;
  const cpiData = history.cpi;
  const gdpData = history.gdp;
  const unempData = history.unemployment;
  const rateData = history.rate;
  const yieldData = history.yield10y;

  // Main multi-line chart
  drawLineChart('mainChart', qs, [
    { label:'CPI %', data: cpiData, color:'#ff3355' },
    { label:'GDP %', data: gdpData, color:'#00ff88' },
    { label:'RATE %', data: rateData, color:'#ffaa00' },
  ]);

  // Yield curve (simulated)
  const yieldCurve = [G.rate*0.6, G.rate*0.75, G.rate*0.85, G.rate*0.92, G.rate*0.96, G.rate, G.bondYield10y*0.95, G.bondYield10y];
  drawBarChart('yieldChart', ['3M','6M','1Y','2Y','3Y','5Y','7Y','10Y'], yieldCurve, 'yield');

  // Unemployment trend
  drawLineChart('unempChart', qs, [
    { label:'Unemployment %', data: unempData, color:'#00aaff' }
  ]);

  // GDP trend
  drawLineChart('gdpChart', qs, [
    { label:'GDP Growth %', data: gdpData, color:'#00ff88' }
  ]);
}

function drawLineChart(canvasId, labels, datasets, options={}) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.offsetWidth || 600;
  const H = canvas.height;
  canvas.width = W;

  ctx.clearRect(0,0,W,H);

  const pad = { top:10, right:10, bottom:20, left:35 };
  const chartW = W - pad.left - pad.right;
  const chartH = H - pad.top - pad.bottom;

  if (!labels.length) return;

  // Find range
  let allVals = datasets.flatMap(d=>d.data);
  let minV = Math.min(...allVals, 0) - 0.5;
  let maxV = Math.max(...allVals, 5) + 0.5;

  // Grid
  ctx.strokeStyle = 'rgba(26,64,96,0.5)';
  ctx.lineWidth = 1;
  for (let i=0;i<=4;i++) {
    const y = pad.top + (i/4)*chartH;
    ctx.beginPath(); ctx.moveTo(pad.left,y); ctx.lineTo(pad.left+chartW,y); ctx.stroke();
    const val = maxV - (i/4)*(maxV-minV);
    ctx.fillStyle = 'rgba(106,154,176,0.7)';
    ctx.font = '9px IBM Plex Mono';
    ctx.textAlign = 'right';
    ctx.fillText(val.toFixed(1), pad.left-3, y+3);
  }

  // Zero line
  if (minV < 0) {
    const zy = pad.top + ((maxV)/(maxV-minV))*chartH;
    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.beginPath(); ctx.moveTo(pad.left,zy); ctx.lineTo(pad.left+chartW,zy); ctx.stroke();
  }

  // Lines
  datasets.forEach(ds => {
    if (ds.data.length < 2) return;
    ctx.strokeStyle = ds.color;
    ctx.lineWidth = 1.5;
    ctx.shadowColor = ds.color;
    ctx.shadowBlur = 4;
    ctx.beginPath();
    ds.data.forEach((v,i) => {
      const x = pad.left + (i/(Math.max(ds.data.length-1,1)))*chartW;
      const y = pad.top + ((maxV-v)/(maxV-minV))*chartH;
      i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
    });
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Dot at end
    if (ds.data.length > 0) {
      const lv = ds.data[ds.data.length-1];
      const lx = pad.left + chartW;
      const ly = pad.top + ((maxV-lv)/(maxV-minV))*chartH;
      ctx.fillStyle = ds.color;
      ctx.beginPath(); ctx.arc(lx,ly,3,0,Math.PI*2); ctx.fill();
    }
  });

  // X labels
  ctx.fillStyle = 'rgba(106,154,176,0.7)';
  ctx.font = '8px IBM Plex Mono';
  ctx.textAlign = 'center';
  ctx.shadowBlur = 0;
  const step = Math.max(1, Math.floor(labels.length/4));
  labels.forEach((l,i) => {
    if (i % step === 0) {
      const x = pad.left + (i/Math.max(labels.length-1,1))*chartW;
      ctx.fillText(l, x, H-4);
    }
  });

  // Legend
  ctx.font = '8px IBM Plex Mono';
  ctx.textAlign = 'left';
  datasets.forEach((ds,i) => {
    ctx.fillStyle = ds.color;
    ctx.fillRect(pad.left + i*70, 2, 8, 2);
    ctx.fillText(ds.label, pad.left + i*70 + 11, 8);
  });
}

function drawBarChart(canvasId, labels, values, type='') {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.offsetWidth || 400;
  const H = canvas.height;
  canvas.width = W;
  ctx.clearRect(0,0,W,H);

  const pad = { top:8, right:8, bottom:18, left:28 };
  const chartW = W - pad.left - pad.right;
  const chartH = H - pad.top - pad.bottom;

  const maxV = Math.max(...values) * 1.2;
  const barW = chartW / labels.length - 3;

  // Detect inverted yield curve
  const isInverted = values[0] > values[values.length-1];

  labels.forEach((l,i) => {
    const x = pad.left + i*(barW+3);
    const barH = (values[i]/maxV)*chartH;
    const y = pad.top + chartH - barH;
    const color = isInverted ? '#ff3355' : '#00ff88';
    ctx.fillStyle = color + '33';
    ctx.fillRect(x, y, barW, barH);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, barW, barH);

    ctx.fillStyle = 'rgba(106,154,176,0.7)';
    ctx.font = '7px IBM Plex Mono';
    ctx.textAlign = 'center';
    ctx.fillText(l, x+barW/2, H-3);
  });

  if (isInverted) {
    ctx.fillStyle = '#ff3355';
    ctx.font = '8px IBM Plex Mono';
    ctx.textAlign = 'right';
    ctx.fillText('⚠ INVERTED — RECESSION SIGNAL', W-8, 16);
  }

  ctx.fillStyle = 'rgba(106,154,176,0.7)';
  ctx.font = '8px IBM Plex Mono';
  ctx.textAlign = 'right';
  for(let i=0;i<=3;i++) {
    const y = pad.top + (i/3)*chartH;
    const v = maxV*(1-i/3);
    ctx.fillText(v.toFixed(1), pad.left-2, y+3);
  }
}

// ============================================================
// BOOT
// ============================================================
renderScenarios();
</script>
</body>
</html>