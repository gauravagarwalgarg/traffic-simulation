"""
Web-based real-time 4-way intersection traffic visualization.
Backend: Python asyncio server + WebSocket (stdlib only).
Frontend: HTML5 Canvas with multi-tab UI, analytics, and manual controls.

Run: python -m engine --web
Open: http://localhost:8765
"""
from __future__ import annotations
import asyncio
import json
import random
import struct
import hashlib
import base64
from collections import deque

from engine.intersection import Intersection, Direction
from engine.analytics import TrafficStats, fit_arrival_distribution, predict_queue, compute_fundamental_diagram, recommend_green_time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Traffic Simulation Adaptive 4-Way Intersection</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#121212;--surface:#1e1e1e;--surface2:#2d2d2d;--primary:#bb86fc;--secondary:#03dac6;--error:#cf6679;--on-bg:#e0e0e0;--on-surface:#fff;--border:#3a3a3a;--green:#4caf50;--yellow:#ffeb3b;--red:#f44336}
body{background:var(--bg);color:var(--on-bg);font-family:'Inter',sans-serif;overflow:hidden;height:100vh;display:grid;grid-template-rows:48px 1fr}
.tabs{display:flex;background:var(--surface);border-bottom:1px solid var(--border);padding:0 16px;gap:4px;align-items:end}
.tab{padding:10px 20px;cursor:pointer;border-radius:8px 8px 0 0;font-size:13px;font-weight:500;color:#999;transition:all .2s}
.tab:hover{color:#ccc;background:var(--surface2)}
.tab.active{color:var(--secondary);background:var(--surface2);border-bottom:2px solid var(--secondary)}
.panel{display:none;height:calc(100vh - 48px);overflow:hidden}
.panel.active{display:grid}
/* Tab 1: Simulation */
#simPanel{grid-template-columns:1fr 320px;grid-template-rows:1fr;gap:0;height:100%}
#simCanvas{background:#0a0a0a;display:flex;align-items:center;justify-content:center;padding:4px;min-height:0}
#simCanvas canvas{border-radius:4px;max-width:100%;max-height:100%}
#controls{background:var(--surface);padding:16px;overflow-y:auto;border-left:1px solid var(--border)}
#controls{background:var(--surface);padding:16px;overflow-y:auto;border-left:1px solid var(--border)}
#controls h3{font-size:12px;text-transform:uppercase;letter-spacing:1px;color:var(--secondary);margin:16px 0 8px}
#controls h3:first-child{margin-top:0}
.btn{display:block;width:100%;padding:8px;margin:4px 0;border:1px solid var(--border);border-radius:6px;background:var(--surface2);color:var(--on-bg);font-size:12px;cursor:pointer;font-family:inherit;transition:all .15s}
.btn:hover{border-color:var(--secondary);color:var(--secondary)}
.btn.active{background:var(--secondary);color:#000;border-color:var(--secondary)}
.slider-row{display:flex;align-items:center;justify-content:space-between;margin:6px 0}
.slider-row label{font-size:11px;color:#aaa}
.slider-row span{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--secondary);min-width:30px;text-align:right}
input[type=range]{width:100px;accent-color:var(--secondary)}
#statsBar{background:var(--surface);border-top:1px solid var(--border);padding:8px 16px;display:flex;gap:20px;font-size:11px;font-family:'JetBrains Mono',monospace;grid-column:1/-1}
#statsBar .st{color:#777}
#statsBar .sv{color:var(--on-surface);margin-left:4px}
/* Tab 2: Config */
#cfgPanel{grid-template-columns:1fr 1fr;padding:24px;gap:24px;align-content:start}
.cfg-card{background:var(--surface);border-radius:12px;padding:20px;border:1px solid var(--border)}
.cfg-card h3{font-size:13px;color:var(--primary);margin-bottom:12px}
.cfg-row{display:flex;align-items:center;justify-content:space-between;margin:8px 0}
.cfg-row label{font-size:12px;color:#bbb}
.cfg-row span{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--secondary)}
select{background:var(--surface2);color:var(--on-bg);border:1px solid var(--border);padding:8px 12px;border-radius:6px;font-size:12px;width:100%}
#applyBtn{background:var(--primary);color:#000;border:none;padding:12px 24px;border-radius:8px;font-weight:600;cursor:pointer;font-size:13px;margin-top:16px;grid-column:1/-1;justify-self:start}
#applyBtn:hover{opacity:.85}
/* Tab 3: Analytics */
#anaPanel{grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;padding:16px;gap:16px}
.chart-box{background:var(--surface);border-radius:12px;padding:12px;border:1px solid var(--border);position:relative;min-height:250px}
.chart-box h4{font-size:11px;color:#888;margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px}
/* Tab 4: Data Explorer */
#dataPanel{grid-template-rows:auto 1fr auto;padding:16px;gap:12px}
#dataPanel.active{display:grid}
#dataSummary{display:flex;gap:16px;font-family:'JetBrains Mono',monospace;font-size:12px}
#dataSummary .metric{background:var(--surface);padding:10px 16px;border-radius:8px;border:1px solid var(--border)}
#dataSummary .metric .val{font-size:18px;color:var(--secondary);display:block;margin-top:4px}
#dataTable{overflow-y:auto;background:var(--surface);border-radius:8px;border:1px solid var(--border)}
table{width:100%;border-collapse:collapse;font-size:11px;font-family:'JetBrains Mono',monospace}
th{position:sticky;top:0;background:var(--surface2);padding:8px;text-align:left;color:var(--primary)}
td{padding:6px 8px;border-top:1px solid var(--border);color:#ccc}
#exportBtn{background:var(--surface2);color:var(--on-bg);border:1px solid var(--border);padding:10px 20px;border-radius:6px;cursor:pointer;font-size:12px;justify-self:start}
/* Tab 5: About */
#aboutPanel{padding:32px;max-width:800px;line-height:1.7}
#aboutPanel.active{display:block}
#aboutPanel h2{color:var(--primary);margin:20px 0 8px;font-size:16px}
#aboutPanel p{font-size:13px;color:#bbb;margin:8px 0}
#aboutPanel code{font-family:'JetBrains Mono',monospace;background:var(--surface2);padding:2px 6px;border-radius:4px;font-size:12px}
.arch-box{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:16px 0}
.arch-node{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center;font-size:11px;color:var(--secondary)}
</style>
</head>
<body>
<div class="tabs">
  <div class="tab active" data-tab="simPanel">Simulation</div>
  <div class="tab" data-tab="cfgPanel">Configuration</div>
  <div class="tab" data-tab="anaPanel">Analytics</div>
  <div class="tab" data-tab="dataPanel">Data Explorer</div>
  <div class="tab" data-tab="aboutPanel">About</div>
</div>

<!-- Tab 1: Simulation -->
<div id="simPanel" class="panel active">
  <div id="simCanvas"><canvas id="c" width="600" height="600"></canvas></div>
  <div id="controls">
    <h3>Live Stats</h3>
    <div style="font-family:'JetBrains Mono',monospace;font-size:11px;line-height:2;color:#ccc">
      N:<span id="cn" style="color:var(--secondary)">0</span> &nbsp; S:<span id="cs" style="color:var(--secondary)">0</span> &nbsp; E:<span id="ce" style="color:var(--secondary)">0</span> &nbsp; W:<span id="cw" style="color:var(--secondary)">0</span><br>
      Departed:<span id="dep" style="color:var(--secondary)">0</span> &nbsp; Speed:<span id="avgSpd" style="color:var(--secondary)">0</span> m/s<br>
      Time:<span id="tm" style="color:var(--secondary)">0</span>s
    </div>
    <h3>Distribution Mode</h3>
    <select id="liveDistMode" onchange="liveDistChange()" style="width:100%;background:var(--surface2);color:var(--on-bg);border:1px solid var(--border);padding:6px;border-radius:6px;font-size:11px">
      <option value="standard">Standard (45/20/25/10)</option>
      <option value="peak">Peak Hour (70/10/15/5)</option>
      <option value="highway">Highway (10/10/60/20)</option>
      <option value="night">Night (20/5/50/25)</option>
      <option value="festival">Festival Rush (60/25/10/5)</option>
    </select>
    <h3>Traffic Lights</h3>
    <button class="btn" onclick="overrideLight('north')">Force N Green</button>
    <button class="btn" onclick="overrideLight('south')">Force S Green</button>
    <button class="btn" onclick="overrideLight('east')">Force E Green</button>
    <button class="btn" onclick="overrideLight('west')">Force W Green</button>
    <button class="btn" id="autoBtn" onclick="toggleAuto()">Auto Mode: ON</button>
    <h3>Spawn Rate</h3>
    <div class="slider-row"><label>Vehicles/sec</label><input type="range" min="1" max="10" value="2" id="spawnSlider" oninput="updateSpawn()"><span id="spawnVal">2</span></div>
    <h3>Sim Speed</h3>
    <div class="slider-row"><label>Multiplier</label><input type="range" min="5" max="50" value="10" id="speedSlider" oninput="updateSpeed()"><span id="speedVal">1.0x</span></div>
    <h3>ML Insight</h3>
    <div id="mlBox" style="font-size:10px;font-family:'JetBrains Mono',monospace;color:#888;line-height:1.8">
      <div>Arrival: <span id="mlDist" style="color:var(--primary)">—</span></div>
      <div>N trend: <span id="mlTrendN" style="color:#42a5f5">—</span></div>
      <div>S trend: <span id="mlTrendS" style="color:#ef5350">—</span></div>
      <div>E trend: <span id="mlTrendE" style="color:#66bb6a">—</span></div>
      <div>W trend: <span id="mlTrendW" style="color:#ffd54f">—</span></div>
      <div>Recommended: NS <span id="mlRecNS" style="color:var(--secondary)">50</span>% EW <span id="mlRecEW" style="color:var(--secondary)">50</span>%</div>
    </div>
  </div>
</div>

<!-- Tab 2: Configuration -->
<div id="cfgPanel" class="panel">
  <div class="cfg-card">
    <h3>Vehicle Distribution</h3>
    <div class="cfg-row"><label>Mode</label><select id="distMode" onchange="distModeChange()">
      <option value="standard">Standard (45/20/25/10)</option>
      <option value="peak">Peak Hour (70/10/15/5)</option>
      <option value="highway">Highway (10/10/60/20)</option>
      <option value="custom">Custom</option>
    </select></div>
    <div id="customDist" style="display:none">
      <div class="cfg-row"><label>Two-Wheeler %</label><input type="range" min="0" max="100" value="45" id="d0" oninput="distUpdate()"><span id="d0v">45</span></div>
      <div class="cfg-row"><label>Auto %</label><input type="range" min="0" max="100" value="20" id="d1" oninput="distUpdate()"><span id="d1v">20</span></div>
      <div class="cfg-row"><label>Sedan %</label><input type="range" min="0" max="100" value="25" id="d2" oninput="distUpdate()"><span id="d2v">25</span></div>
      <div class="cfg-row"><label>Truck %</label><input type="range" min="0" max="100" value="10" id="d3" oninput="distUpdate()"><span id="d3v">10</span></div>
      <div class="cfg-row"><label>Sum</label><span id="distSum" style="color:var(--error)">100%</span></div>
    </div>
  </div>
  <div class="cfg-card">
    <h3>Per-Arm Spawn Rate</h3>
    <div class="cfg-row"><label>North</label><input type="range" min="1" max="10" value="3" id="srN"><span id="srNv">3</span></div>
    <div class="cfg-row"><label>South</label><input type="range" min="1" max="10" value="3" id="srS"><span id="srSv">3</span></div>
    <div class="cfg-row"><label>East</label><input type="range" min="1" max="10" value="3" id="srE"><span id="srEv">3</span></div>
    <div class="cfg-row"><label>West</label><input type="range" min="1" max="10" value="3" id="srW"><span id="srWv">3</span></div>
  </div>
  <div class="cfg-card">
    <h3>IDM Parameters</h3>
    <div class="cfg-row"><label>Delta (accel exp)</label><input type="range" min="2" max="6" step="0.5" value="3" id="idmDelta"><span id="idmDv">3</span></div>
    <div class="cfg-row"><label>Min Gap Mult</label><input type="range" min="5" max="20" value="10" id="idmGap"><span id="idmGv">1.0x</span></div>
    <div class="cfg-row"><label>Headway Mult</label><input type="range" min="5" max="20" value="10" id="idmHw"><span id="idmHv">1.0x</span></div>
  </div>
  <button id="applyBtn" onclick="applyConfig()">Apply Configuration</button>
</div>

<!-- Tab 3: Analytics -->
<div id="anaPanel" class="panel">
  <div class="chart-box"><h4>Queue Length Over Time</h4><canvas id="chartQueue"></canvas></div>
  <div class="chart-box"><h4>Average Speed by Type</h4><canvas id="chartSpeed"></canvas></div>
  <div class="chart-box"><h4>Throughput per Cycle</h4><canvas id="chartThru"></canvas></div>
  <div class="chart-box"><h4>Green Time Allocation</h4><canvas id="chartPie"></canvas></div>
</div>

<!-- Tab 4: Data Explorer -->
<div id="dataPanel" class="panel">
  <div id="dataSummary">
    <div class="metric"><span class="st">Spawned</span><span class="val" id="mSpawned">0</span></div>
    <div class="metric"><span class="st">Departed</span><span class="val" id="mDeparted">0</span></div>
    <div class="metric"><span class="st">Avg Wait</span><span class="val" id="mWait">0s</span></div>
  </div>
  <div id="dataTable"><table><thead><tr><th>Time</th><th>N</th><th>S</th><th>E</th><th>W</th><th>Departed</th><th>Lights</th></tr></thead><tbody id="dtBody"></tbody></table></div>
  <button id="exportBtn" onclick="exportCSV()">Export CSV</button>
</div>

<!-- Tab 5: About -->
<div id="aboutPanel" class="panel">
  <h2>Intelligent Driver Model (IDM)</h2>
  <p>Vehicles follow a continuous car-following model where acceleration depends on current speed, desired speed, gap to leader, and relative velocity. Parameters: <code>a</code> max accel, <code>b</code> comfortable decel, <code>s0</code> min gap, <code>T</code> desired headway, <code>δ</code> acceleration exponent.</p>
  <h2>Adaptive Signal Controller</h2>
  <p>Green time is allocated proportionally to queue demand each cycle. NS and EW phases get green time based on their combined vehicle counts (clamped between 15s–60s). Yellow clearance of 3s separates phases.</p>
  <h2>Architecture</h2>
  <div class="arch-box">
    <div class="arch-node">IDM Engine<br><small>car-following</small></div>
    <div class="arch-node">Intersection<br><small>4-arm queues</small></div>
    <div class="arch-node">Adaptive Controller<br><small>signal timing</small></div>
    <div class="arch-node">WebSocket Server<br><small>asyncio</small></div>
    <div class="arch-node">Canvas Renderer<br><small>60fps client</small></div>
    <div class="arch-node">Chart.js Analytics<br><small>real-time</small></div>
  </div>
  <h2>References</h2>
  <p>Treiber, Hennecke, Helbing "Congested traffic states in empirical observations and microscopic simulations" (2000)</p>
  <p>Kesting, Treiber, Helbing "General Lane-Changing Model MOBIL" (2007)</p>
</div>

<script>
// Tabs
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
  t.classList.add('active');document.getElementById(t.dataset.tab).classList.add('active');resizeCanvas();
});

// Canvas
const canvas=document.getElementById('c'),ctx=canvas.getContext('2d');
function resizeCanvas(){const p=document.getElementById('simCanvas');if(!p)return;const rect=p.getBoundingClientRect();const w=rect.width-8,h=rect.height-8;const s=Math.max(200,Math.min(w,h));if(s>200){canvas.width=s;canvas.height=s;}}
window.onresize=resizeCanvas;setInterval(()=>{if(canvas.width<200)resizeCanvas();},300);setTimeout(resizeCanvas,200);setTimeout(resizeCanvas,500);

const COLORS={two_wheeler:'#ffd54f',auto_rickshaw:'#66bb6a',sedan:'#42a5f5',heavy_truck:'#ef5350'};
const SIZES={two_wheeler:[6,3],auto_rickshaw:[9,6],sedan:[14,7],heavy_truck:[20,9]};
const ARM_LEN=300;

function mapV(dir,x,y){
  const S=canvas.width,center=S/2,roadW=S*0.22,scale=(S*0.36)/ARM_LEN;
  const offset=x*scale,lat=((y/7)-0.5)*roadW;
  switch(dir){
    case'north':return[center+lat,center-roadW/2-offset];
    case'south':return[center-lat,center+roadW/2+offset];
    case'east':return[center+roadW/2+offset,center+lat];
    case'west':return[center-roadW/2-offset,center-lat];
  }return[center,center];
}

function roundRect(x,y,w,h,r){ctx.beginPath();ctx.moveTo(x+r,y);ctx.lineTo(x+w-r,y);ctx.quadraticCurveTo(x+w,y,x+w,y+r);ctx.lineTo(x+w,y+h-r);ctx.quadraticCurveTo(x+w,y+h,x+w-r,y+h);ctx.lineTo(x+r,y+h);ctx.quadraticCurveTo(x,y+h,x,y+h-r);ctx.lineTo(x,y+r);ctx.quadraticCurveTo(x,y,x+r,y);ctx.closePath();ctx.fill();}

function render(data){
  try{
  const S=canvas.width;if(!S)return;
  ctx.clearRect(0,0,S,S);
  const center=S/2,roadW=S*0.22;
  // Roads
  ctx.fillStyle='#1a1a2e';ctx.fillRect(center-roadW/2,0,roadW,S);ctx.fillRect(0,center-roadW/2,S,roadW);
  ctx.fillStyle='#252540';ctx.fillRect(center-roadW/2,center-roadW/2,roadW,roadW);
  // Lane marks
  ctx.strokeStyle='#333';ctx.setLineDash([6,10]);ctx.lineWidth=1;ctx.beginPath();
  ctx.moveTo(center,0);ctx.lineTo(center,center-roadW/2);ctx.moveTo(center,center+roadW/2);ctx.lineTo(center,S);
  ctx.moveTo(0,center);ctx.lineTo(center-roadW/2,center);ctx.moveTo(center+roadW/2,center);ctx.lineTo(S,center);
  ctx.stroke();ctx.setLineDash([]);
  // Stop lines
  ctx.strokeStyle='#666';ctx.lineWidth=2;ctx.beginPath();
  ctx.moveTo(center-roadW/2,center-roadW/2);ctx.lineTo(center+roadW/2,center-roadW/2);
  ctx.moveTo(center-roadW/2,center+roadW/2);ctx.lineTo(center+roadW/2,center+roadW/2);
  ctx.moveTo(center-roadW/2,center-roadW/2);ctx.lineTo(center-roadW/2,center+roadW/2);
  ctx.moveTo(center+roadW/2,center-roadW/2);ctx.lineTo(center+roadW/2,center+roadW/2);
  ctx.stroke();ctx.lineWidth=1;

  // Traffic lights with 3 bulbs + label + timer
  if(data.lights){
    const positions={north:[center+roadW/2+20,center-roadW/2-30],south:[center-roadW/2-20,center+roadW/2+30],east:[center+roadW/2+30,center+roadW/2+20],west:[center-roadW/2-30,center-roadW/2-20]};
    const labels={north:'N',south:'S',east:'E',west:'W'};
    for(const[dir,st]of Object.entries(data.lights)){
      const[lx,ly]=positions[dir];
      // Background box
      ctx.fillStyle='#111';ctx.fillRect(lx-12,ly-18,24,52);
      ctx.strokeStyle='#444';ctx.lineWidth=1;ctx.stroke();
      // 3 bulbs: R, Y, G (vertical)
      const bulbs=[{c:'#f44336',on:st==='red'},{c:'#ff9800',on:st==='yellow'},{c:'#4caf50',on:st==='green'}];
      bulbs.forEach((b,i)=>{ctx.beginPath();ctx.arc(lx,ly-10+i*14,5,0,Math.PI*2);ctx.fillStyle=b.on?b.c:'#333';ctx.fill();if(b.on){ctx.shadowColor=b.c;ctx.shadowBlur=8;ctx.fill();ctx.shadowBlur=0;}});
      // Direction label
      ctx.fillStyle='#fff';ctx.font='bold 9px Inter';ctx.textAlign='center';ctx.fillText(labels[dir],lx,ly+38);
      // Timer
      if(data.timers&&data.timers[dir]!==undefined){ctx.fillStyle='var(--secondary)';ctx.fillStyle='#03dac6';ctx.font='bold 10px JetBrains Mono';ctx.fillText(data.timers[dir]+'s',lx,ly+50);}
    }
  }

  // Vehicles oriented by direction
  for(const v of(data.vehicles||[])){
    const[vx,vy]=mapV(v.direction,v.x,v.y);
    if(vx<-10||vx>S+10||vy<-10||vy>S+10)continue;
    let[w,h]=SIZES[v.type]||[6,3];
    // Vertical vehicles for N/S, horizontal for E/W
    if(v.direction==='north'||v.direction==='south')[w,h]=[h,w];
    ctx.fillStyle=COLORS[v.type]||'#fff';
    roundRect(vx-w/2,vy-h/2,w,h,1.5);
  }

  // Stats update
  if(data.counts){document.getElementById('cn').textContent=data.counts.north||0;document.getElementById('cs').textContent=data.counts.south||0;document.getElementById('ce').textContent=data.counts.east||0;document.getElementById('cw').textContent=data.counts.west||0;}
  document.getElementById('dep').textContent=data.total_departed||0;
  document.getElementById('tm').textContent=(data.time||0).toFixed(1);
  const speeds=(data.vehicles||[]).map(v=>v.speed);
  document.getElementById('avgSpd').textContent=speeds.length?(speeds.reduce((a,b)=>a+b,0)/speeds.length).toFixed(1):'0';
  }catch(e){console.error('Render error:',e);}
}

// Controls
let autoMode=true;
function liveDistChange(){const mode=document.getElementById('liveDistMode').value;let dist;switch(mode){case'peak':dist=[70,10,15,5];break;case'highway':dist=[10,10,60,20];break;case'night':dist=[20,5,50,25];break;case'festival':dist=[60,25,10,5];break;default:dist=[45,20,25,10];}if(ws&&ws.readyState===1)ws.send(JSON.stringify({cmd:'config',distribution:dist}));}
function overrideLight(dir){if(ws&&ws.readyState===1)ws.send(JSON.stringify({cmd:'override_light',direction:dir,state:'green'}));}
function toggleAuto(){autoMode=!autoMode;document.getElementById('autoBtn').textContent='Auto Mode: '+(autoMode?'ON':'OFF');document.getElementById('autoBtn').classList.toggle('active',!autoMode);if(ws&&ws.readyState===1)ws.send(JSON.stringify({cmd:'auto_mode',enabled:autoMode}));}
function updateSpawn(){const v=document.getElementById('spawnSlider').value;document.getElementById('spawnVal').textContent=v;if(ws&&ws.readyState===1)ws.send(JSON.stringify({cmd:'config',spawn_rate:+v}));}
function updateSpeed(){const v=document.getElementById('speedSlider').value/10;document.getElementById('speedVal').textContent=v.toFixed(1)+'x';if(ws&&ws.readyState===1)ws.send(JSON.stringify({cmd:'config',sim_speed:v}));}

// Config panel
function distModeChange(){document.getElementById('customDist').style.display=document.getElementById('distMode').value==='custom'?'block':'none';}
function distUpdate(){['d0','d1','d2','d3'].forEach(id=>{document.getElementById(id+'v').textContent=document.getElementById(id).value;});const s=[0,1,2,3].map(i=>+document.getElementById('d'+i).value).reduce((a,b)=>a+b,0);document.getElementById('distSum').textContent=s+'%';document.getElementById('distSum').style.color=s===100?'var(--secondary)':'var(--error)';}
['srN','srS','srE','srW'].forEach(id=>{document.getElementById(id).oninput=()=>{document.getElementById(id+'v').textContent=document.getElementById(id).value;};});
['idmDelta','idmGap','idmHw'].forEach(id=>{document.getElementById(id).oninput=()=>{if(id==='idmDelta')document.getElementById('idmDv').textContent=document.getElementById(id).value;else{const v=(document.getElementById(id).value/10).toFixed(1);document.getElementById(id==='idmGap'?'idmGv':'idmHv').textContent=v+'x';}};});

function applyConfig(){
  const mode=document.getElementById('distMode').value;
  let dist;
  if(mode==='peak')dist=[70,10,15,5];else if(mode==='highway')dist=[10,10,60,20];else if(mode==='custom')dist=[0,1,2,3].map(i=>+document.getElementById('d'+i).value);else dist=[45,20,25,10];
  const cfg={cmd:'config',distribution:dist,spawn_rates:{north:+document.getElementById('srN').value,south:+document.getElementById('srS').value,east:+document.getElementById('srE').value,west:+document.getElementById('srW').value},idm:{delta:+document.getElementById('idmDelta').value,min_gap_mult:document.getElementById('idmGap').value/10,headway_mult:document.getElementById('idmHw').value/10}};
  if(ws&&ws.readyState===1)ws.send(JSON.stringify(cfg));
  // Switch to Simulation tab
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
  document.querySelector('[data-tab="simPanel"]').classList.add('active');
  document.getElementById('simPanel').classList.add('active');
  resizeCanvas();
}

// Charts
const chartOpts={responsive:true,maintainAspectRatio:false,animation:false,scales:{x:{display:false},y:{ticks:{color:'#666',font:{size:10}},grid:{color:'#2a2a2a'}}},plugins:{legend:{labels:{color:'#999',font:{size:10}}}}};
const queueChart=new Chart(document.getElementById('chartQueue'),{type:'line',data:{labels:[],datasets:[{label:'N',data:[],borderColor:'#42a5f5',borderWidth:1.5,pointRadius:0,tension:0.3},{label:'S',data:[],borderColor:'#ef5350',borderWidth:1.5,pointRadius:0,tension:0.3},{label:'E',data:[],borderColor:'#66bb6a',borderWidth:1.5,pointRadius:0,tension:0.3},{label:'W',data:[],borderColor:'#ffd54f',borderWidth:1.5,pointRadius:0,tension:0.3}]},options:chartOpts});
const speedChart=new Chart(document.getElementById('chartSpeed'),{type:'line',data:{labels:[],datasets:[{label:'2W',data:[],borderColor:'#ffd54f',borderWidth:1.5,pointRadius:0,tension:0.3},{label:'Auto',data:[],borderColor:'#66bb6a',borderWidth:1.5,pointRadius:0,tension:0.3},{label:'Sedan',data:[],borderColor:'#42a5f5',borderWidth:1.5,pointRadius:0,tension:0.3},{label:'Truck',data:[],borderColor:'#ef5350',borderWidth:1.5,pointRadius:0,tension:0.3}]},options:chartOpts});
const thruChart=new Chart(document.getElementById('chartThru'),{type:'bar',data:{labels:[],datasets:[{label:'Departed/cycle',data:[],backgroundColor:'rgba(187,134,252,0.6)',borderColor:'#bb86fc',borderWidth:1}]},options:{...chartOpts,scales:{...chartOpts.scales,x:{ticks:{color:'#666',font:{size:9}},grid:{color:'#2a2a2a'}}}}});
const pieChart=new Chart(document.getElementById('chartPie'),{type:'doughnut',data:{labels:['N/S','E/W'],datasets:[{data:[50,50],backgroundColor:['#42a5f5','#66bb6a'],borderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{labels:{color:'#999'}}}}});

function updateAnalytics(a){
  if(!a)return;
  if(a.queue_history){const q=a.queue_history;const lbls=q.map((_,i)=>i);queueChart.data.labels=lbls;queueChart.data.datasets[0].data=q.map(d=>d.north);queueChart.data.datasets[1].data=q.map(d=>d.south);queueChart.data.datasets[2].data=q.map(d=>d.east);queueChart.data.datasets[3].data=q.map(d=>d.west);queueChart.update();}
  if(a.speed_history){const s=a.speed_history;const lbls=s.map((_,i)=>i);speedChart.data.labels=lbls;speedChart.data.datasets[0].data=s.map(d=>d.two_wheeler);speedChart.data.datasets[1].data=s.map(d=>d.auto_rickshaw);speedChart.data.datasets[2].data=s.map(d=>d.sedan);speedChart.data.datasets[3].data=s.map(d=>d.heavy_truck);speedChart.update();}
  if(a.throughput){const t=a.throughput;thruChart.data.labels=t.map((_,i)=>'C'+(i+1));thruChart.data.datasets[0].data=t;thruChart.update();}
  if(a.green_split){pieChart.data.datasets[0].data=[a.green_split.ns,a.green_split.ew];pieChart.update();}
  // ML Insights
  if(a.ml){
    const ml=a.ml;
    if(ml.distribution)document.getElementById('mlDist').textContent=ml.distribution.best_fit+' (CV='+ml.distribution.cv+')';
    if(ml.predictions){
      document.getElementById('mlTrendN').textContent=ml.predictions.north?.trend||'—';
      document.getElementById('mlTrendS').textContent=ml.predictions.south?.trend||'—';
      document.getElementById('mlTrendE').textContent=ml.predictions.east?.trend||'—';
      document.getElementById('mlTrendW').textContent=ml.predictions.west?.trend||'—';
    }
    if(ml.recommendation){
      document.getElementById('mlRecNS').textContent=ml.recommendation.ns_pct;
      document.getElementById('mlRecEW').textContent=ml.recommendation.ew_pct;
    }
  }
}

// Data explorer
const telemetry=[];
function addTelemetry(data){
  telemetry.push({time:data.time,n:data.counts?.north||0,s:data.counts?.south||0,e:data.counts?.east||0,w:data.counts?.west||0,dep:data.total_departed||0,lights:data.lights?Object.values(data.lights).join('/'):''});
  if(telemetry.length>50)telemetry.shift();
  const tbody=document.getElementById('dtBody');
  tbody.innerHTML=telemetry.map(r=>`<tr><td>${r.time.toFixed(1)}</td><td>${r.n}</td><td>${r.s}</td><td>${r.e}</td><td>${r.w}</td><td>${r.dep}</td><td>${r.lights}</td></tr>`).join('');
  tbody.parentElement.parentElement.scrollTop=9999;
  document.getElementById('mSpawned').textContent=data.total_spawned||telemetry[telemetry.length-1]?.dep||0;
  document.getElementById('mDeparted').textContent=data.total_departed||0;
}
function exportCSV(){const hdr='Time,N,S,E,W,Departed,Lights\n';const rows=telemetry.map(r=>`${r.time},${r.n},${r.s},${r.e},${r.w},${r.dep},${r.lights}`).join('\n');const blob=new Blob([hdr+rows],{type:'text/csv'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='traffic_data.csv';a.click();}

// WebSocket
let ws;
function connect(){
  ws=new WebSocket('ws://'+location.host+'/ws');
  ws.onmessage=(e)=>{const msg=JSON.parse(e.data);if(msg.type==='state'){render(msg);addTelemetry(msg);}else if(msg.type==='analytics'){updateAnalytics(msg);}};
  ws.onclose=()=>setTimeout(connect,1000);
}
connect();
</script>
</body>
</html>"""


# --- Server ---

def _make_ws_accept(key: str) -> str:
    magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    return base64.b64encode(hashlib.sha1((key + magic).encode()).digest()).decode()


def _encode_ws_frame(data: bytes) -> bytes:
    length = len(data)
    if length < 126:
        return b"\x81" + bytes([length]) + data
    elif length < 65536:
        return b"\x81\x7e" + struct.pack(">H", length) + data
    else:
        return b"\x81\x7f" + struct.pack(">Q", length) + data


def _decode_ws_frame(data: bytes) -> bytes | None:
    if len(data) < 6:
        return None
    payload_len = data[1] & 0x7f
    if payload_len < 126:
        mask_start = 2
    elif payload_len == 126:
        payload_len = struct.unpack(">H", data[2:4])[0]
        mask_start = 4
    else:
        payload_len = struct.unpack(">Q", data[2:10])[0]
        mask_start = 10
    mask = data[mask_start:mask_start + 4]
    payload = data[mask_start + 4:mask_start + 4 + payload_len]
    return bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


async def run_webapp(host: str = "0.0.0.0", port: int = 8765) -> None:
    """Run the 4-way intersection simulation server with multi-tab UI."""
    sim = Intersection(arm_length=300.0, arm_width=7.0, dt=0.1)
    clients: set[asyncio.StreamWriter] = set()
    traffic_stats = TrafficStats()

    # Simulation config (mutable via WebSocket)
    config = {
        "spawn_rate": 2,
        "spawn_rates": {"north": 2, "south": 2, "east": 2, "west": 2},
        "distribution": [0.45, 0.20, 0.25, 0.10],
        "sim_speed": 1.0,
        "auto_mode": True,
    }

    # Analytics accumulators
    analytics = {
        "queue_history": deque(maxlen=60),
        "speed_history": deque(maxlen=60),
        "throughput": deque(maxlen=20),
        "last_departed": 0,
        "frame_count": 0,
    }

    def handle_command(msg: dict) -> None:
        cmd = msg.get("cmd")
        if cmd == "config":
            if "spawn_rate" in msg:
                config["spawn_rate"] = int(msg["spawn_rate"])
            if "spawn_rates" in msg:
                config["spawn_rates"].update(msg["spawn_rates"])
            if "distribution" in msg:
                d = msg["distribution"]
                total = sum(d)
                config["distribution"] = [x / total for x in d] if total > 0 else [0.25] * 4
            if "sim_speed" in msg:
                config["sim_speed"] = max(0.5, min(5.0, float(msg["sim_speed"])))
        elif cmd == "override_light" and not config["auto_mode"]:
            direction = msg.get("direction")
            # Force all red, then set requested green
            from engine.intersection import LightState
            for d in Direction:
                sim.controller.get_light_state = None  # will use manual
            # Simple override: reset cycle so requested direction gets green
            if direction in ("north", "south"):
                sim.cycle_elapsed = 0.0  # NS phase
            elif direction in ("east", "west"):
                ns_phase_len = sim.controller.phases[0][2] + sim.controller.phases[1][2]
                sim.cycle_elapsed = ns_phase_len  # EW phase
        elif cmd == "auto_mode":
            config["auto_mode"] = msg.get("enabled", True)

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        request = await reader.read(4096)
        request_str = request.decode(errors="ignore")

        if "Upgrade: websocket" in request_str:
            key = ""
            for line in request_str.split("\r\n"):
                if line.startswith("Sec-WebSocket-Key:"):
                    key = line.split(":")[1].strip()
            accept = _make_ws_accept(key)
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            )
            writer.write(response.encode())
            await writer.drain()
            clients.add(writer)
            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    decoded = _decode_ws_frame(data)
                    if decoded:
                        try:
                            msg = json.loads(decoded)
                            handle_command(msg)
                        except (json.JSONDecodeError, Exception):
                            pass
            except (ConnectionError, asyncio.IncompleteReadError):
                pass
            finally:
                clients.discard(writer)
                writer.close()
        else:
            body = HTML_PAGE.encode()
            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: text/html\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Connection: close\r\n\r\n"
            ).encode() + body
            writer.write(response)
            await writer.drain()
            writer.close()

    async def simulation_loop():
        from engine.models import VehicleType
        type_list = [VehicleType.TWO_WHEELER, VehicleType.AUTO_RICKSHAW, VehicleType.SEDAN, VehicleType.HEAVY_TRUCK]
        logging.info("Simulation loop started")

        while True:
          try:
            speed_mult = config["sim_speed"]
            # Spawn vehicles per arm
            for d in Direction:
                rate = config["spawn_rates"].get(d.value, config["spawn_rate"])
                if random.random() < rate * sim.dt * speed_mult:
                    vtype = random.choices(type_list, weights=config["distribution"], k=1)[0]
                    sim.spawn_vehicle(d, vtype)
                    traffic_stats.record_arrival(sim.time)

            state = sim.step()
            state["type"] = "state"
            state["total_spawned"] = sim.total_spawned

            # Broadcast state
            if clients:
                frame = _encode_ws_frame(json.dumps(state).encode())
                dead: set[asyncio.StreamWriter] = set()
                for client in clients:
                    try:
                        client.write(frame)
                        await client.drain()
                    except (ConnectionError, OSError):
                        dead.add(client)
                clients.difference_update(dead)

            # Analytics every 30 frames (~1 second)
            analytics["frame_count"] += 1
            if analytics["frame_count"] % 30 == 0:
                # Record stats for ML
                all_speeds = [v.speed for arm in sim.arms.values() for v in arm.vehicles]
                avg_spd = sum(all_speeds) / len(all_speeds) if all_speeds else 0
                counts_dict = {d.value: arm.count for d, arm in sim.arms.items()}
                traffic_stats.record(counts_dict, sim.total_departed, avg_spd, sim.time)

                # Queue snapshot
                analytics["queue_history"].append({d.value: arm.count for d, arm in sim.arms.items()})
                # Speed by type
                speed_by_type = {"two_wheeler": [], "auto_rickshaw": [], "sedan": [], "heavy_truck": []}
                for arm in sim.arms.values():
                    for v in arm.vehicles:
                        speed_by_type[v.vehicle_type.value].append(v.speed)
                avg_speeds = {k: round(sum(v) / len(v), 1) if v else 0 for k, v in speed_by_type.items()}
                analytics["speed_history"].append(avg_speeds)
                # Throughput
                departed_this = sim.total_departed - analytics["last_departed"]
                analytics["last_departed"] = sim.total_departed
                analytics["throughput"].append(departed_this)
                # Green split
                ns_green = sim.controller.phases[0][2]
                ew_green = sim.controller.phases[2][2]
                total_g = ns_green + ew_green
                green_split = {"ns": round(ns_green / total_g * 100, 1), "ew": round(ew_green / total_g * 100, 1)} if total_g > 0 else {"ns": 50, "ew": 50}

                ana_msg = {
                    "type": "analytics",
                    "queue_history": list(analytics["queue_history"]),
                    "speed_history": list(analytics["speed_history"]),
                    "throughput": list(analytics["throughput"]),
                    "green_split": green_split,
                    "ml": {
                        "distribution": fit_arrival_distribution(traffic_stats),
                        "predictions": predict_queue(traffic_stats),
                        "fundamental_diagram": compute_fundamental_diagram(traffic_stats),
                        "recommendation": recommend_green_time(traffic_stats),
                    },
                }
                if clients:
                    frame = _encode_ws_frame(json.dumps(ana_msg).encode())
                    dead = set()
                    for client in clients:
                        try:
                            client.write(frame)
                            await client.drain()
                        except (ConnectionError, OSError):
                            dead.add(client)
                    clients.difference_update(dead)

            await asyncio.sleep((1 / 30) / speed_mult)
          except Exception as e:
            logging.error(f"Simulation loop error: {e}", exc_info=True)
            await asyncio.sleep(1)

    server = await asyncio.start_server(handle_client, host, port)
    print(f"\n🚦 Traffic Simulation at http://localhost:{port}")
    print(f"   Multi-tab UI: Simulation | Configuration | Analytics | Data Explorer | About")
    print(f"   Press Ctrl+C to stop.\n")
    logging.info(f"Server started on {host}:{port}")

    asyncio.create_task(simulation_loop())
    async with server:
        await server.serve_forever()


def start_web() -> None:
    try:
        asyncio.run(run_webapp())
    except KeyboardInterrupt:
        print("\nServer stopped.")
