"""EggWise patient view: the patient-facing companion experience.

You pick which demo patient you are, and the Companion agent is given that identity in
the session context, so it never asks you to identify yourself. Home shows your adherence,
Care lets you set reminders and book follow-ups (real add-to-calendar links), and the chat
bar is the Companion. Clinical questions hit the medical-safety guardrail and escalate.
Reuses the JSON API registered by console.py.
"""
from __future__ import annotations

from fastapi.responses import HTMLResponse

from .ui_common import BASE_CSS, FONT_LINK, LOGO_SVG


def register_patient(app):
    @app.get("/patient", response_class=HTMLResponse)
    def patient_page():
        return HTMLResponse(PATIENT_HTML)


_PATIENT_CSS = r"""
  .psel{font:inherit;font-size:13px;font-weight:700;color:var(--ink);background:var(--card2);border:1px solid var(--line2);border-radius:9px;padding:7px 10px}
  .hero{font-family:'Poppins',sans-serif;font-weight:700;font-size:26px;margin:2px 0 2px}
  .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;max-width:720px;margin-bottom:18px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:var(--shadow)}
  .card .lab{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-mute);font-weight:700}
  .card .big{font-family:'Poppins',sans-serif;font-weight:800;font-size:30px;line-height:1.1;margin-top:6px}
  .card .big.ok{color:var(--ok)} .card .big.warn{color:var(--warn)}
  .pill{display:inline-block;font-size:11px;font-weight:700;padding:4px 11px;border-radius:20px;margin-top:8px}
  .pill.ok{background:rgba(78,205,196,.15);color:var(--ok)} .pill.warn{background:rgba(233,185,73,.16);color:var(--warn)}
  .qa{display:flex;gap:10px;flex-wrap:wrap;max-width:720px}
  .result a{margin-top:6px}
"""

PATIENT_HTML = (r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EggWise &mdash; My Companion</title>
__FONT__
<style>__BASE__
__PATIENT__</style>
</head>
<body>
  <header>
    <div class="brand">__LOGO__ EggWise<span class="dot">.</span></div>
    <div class="tag">Companion</div>
    <div class="spacer"></div>
    <div class="switch"><a href="/console">Clinic</a><a class="on" href="/patient">Patient</a></div>
    <select id="psel" class="psel" onchange="pickPatient(this.value)"></select>
    <a class="logout" href="/logout">Sign out</a>
  </header>

  <div class="shell">
    <nav class="side">
      <div class="ntitle">My EggWise</div>
      <button class="navbtn active" data-view="home"><span class="ico">&#127968;</span> Home</button>
      <button class="navbtn" data-view="care"><span class="ico">&#128138;</span> Reminders &amp; visits</button>
    </nav>
    <div class="work">
      <main id="main"></main>
      <div class="cmd">
        <div class="feed" id="feed"></div>
        <form id="cmdForm">
          <input id="cmdInput" placeholder="Ask EggWise (e.g. &quot;remind me to take my evening meds at 8pm&quot;)" autocomplete="off">
          <button class="btn teal" type="submit">Ask</button>
        </form>
      </div>
    </div>
  </div>

  <nav class="tabbar">
    <button class="navbtn active" data-view="home"><span class="ico">&#127968;</span>Home</button>
    <button class="navbtn" data-view="care"><span class="ico">&#128138;</span>Care</button>
  </nav>

  <div id="toast"></div>

<script>
const $=(s,r=document)=>r.querySelector(s);
const api=async(u,o)=>{const r=await fetch(u,o);return r.json();};
const jpost=(u,b)=>api(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});
let PID='', PNAME='';
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('on');setTimeout(()=>t.classList.remove('on'),2600);}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function firstName(n){return (n||'').replace(/\s*\(.*\)/,'').split(' ')[0];}
function setNav(v){document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===v));}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{setNav(b.dataset.view);render(b.dataset.view);});
function render(v){({home:renderHome,care:renderCare}[v]||renderHome)();}

async function init(){
  const data=await api('/api/patients');const sel=$('#psel');
  data.patients.forEach(p=>{const o=document.createElement('option');o.value=p.id;o.textContent=firstName(p.name);sel.appendChild(o);});
  const def=data.patients.find(p=>p.id==='pt-jasmine')||data.patients[0];
  PID=def.id;PNAME=def.name;sel.value=PID;renderHome();
}
function pickPatient(id){PID=id;const sel=$('#psel');PNAME=sel.options[sel.selectedIndex].text;$('#feed').innerHTML='';$('#feed').classList.remove('on');setNav('home');renderHome();}

async function renderHome(){
  $('#main').innerHTML=`<div class="hero">Hi ${esc(firstName(PNAME))} &#128075;</div><p class="sub">Here's your EggWise summary. I can set reminders, help you book a visit, and answer logistics. For anything medical I'll loop in your care team.</p><div id="ad"><div class="empty">Loading <span class="spin"></span></div></div>
   <div class="qa"><button class="btn teal" onclick="setNav('care');renderCare()">Set a medication reminder</button><button class="btn ghost" onclick="setNav('care');renderCare()">Book a follow-up</button><button class="btn ghost" onclick="$('#cmdInput').focus()">Ask EggWise</button></div>`;
  const a=await api('/api/adherence?patient_id='+encodeURIComponent(PID));
  if(a.error||a.name===undefined){$('#ad').innerHTML='';return;}
  const pct=a.days_reviewed?Math.round((a.days_reviewed-a.doses_missed)/a.days_reviewed*100):100;
  $('#ad').innerHTML=`<div class="cards">
    <div class="card"><div class="lab">Adherence (${a.days_reviewed}d)</div><div class="big ${a.on_track?'ok':'warn'}">${pct}%</div>
      <span class="pill ${a.on_track?'ok':'warn'}">${a.on_track?'On track':a.doses_missed+' dose(s) missed'}</span></div>
    <div class="card"><div class="lab">Doses missed</div><div class="big">${a.doses_missed}</div><span class="muted">${a.missed_dates&&a.missed_dates.length?esc(a.missed_dates.join(', ')):'none recently'}</span></div>
  </div>`;
}

function renderCare(){
  $('#main').innerHTML=`<h1>Reminders &amp; visits</h1><p class="sub">Set a daily medication reminder or request a follow-up. You'll get a one-tap add-to-calendar link.</p>
  <div class="panel"><h3>Medication reminder</h3>
    <div class="row2"><div class="field"><label>Medication</label><input id="rMed" value="evening medication"></div><div class="field"><label>Time</label><input id="rTime" type="time" value="20:00"></div></div>
    <div class="field"><label>Repeat for (days)</label><input id="rDays" type="number" value="14"></div>
    <button class="btn teal" onclick="doReminder()">Create reminder</button><div id="rOut"></div></div>
  <div class="panel"><h3>Book a follow-up</h3>
    <div class="row2"><div class="field"><label>Preferred date</label><input id="bDate" type="date" value="2026-06-16"></div><div class="field"><label>Time</label><input id="bTime" type="time" value="10:00"></div></div>
    <button class="btn teal" onclick="doBook()">Request follow-up</button><div id="bOut"></div></div>`;
}
async function doReminder(){const r=await jpost('/api/reminder',{patient_id:PID,medication:$('#rMed').value,time:$('#rTime').value,days:$('#rDays').value});
  $('#rOut').innerHTML=r.error?`<div class="result">${esc(r.error)}</div>`:`<div class="result"><b>${esc(r.medication)}</b> · ${esc(r.frequency)}<br><br><a class="btn gold" href="${r.google_calendar_link}" target="_blank">Add to Google Calendar</a><div class="muted" style="margin-top:8px">${esc(r.note)}</div></div>`;}
async function doBook(){const r=await jpost('/api/book',{patient_id:PID,date:$('#bDate').value,time:$('#bTime').value});
  $('#bOut').innerHTML=r.error?`<div class="result">${esc(r.error)}</div>`:`<div class="result"><b>${esc(r.title||'Follow-up')}</b><br>${esc(r.start||'')}<br><br><a class="btn gold" href="${r.google_calendar_link}" target="_blank">Add to Google Calendar</a><div class="muted" style="margin-top:8px">${esc(r.note||'')}</div></div>`;}

$('#cmdForm').addEventListener('submit',async e=>{
  e.preventDefault();const inp=$('#cmdInput');const text=inp.value.trim();if(!text)return;inp.value='';
  const feed=$('#feed');feed.classList.add('on');addTurn('me',firstName(PNAME)||'You',text);
  const t=addTurn('agent','EggWise','<span class="spin"></span>');
  const r=await jpost('/api/agent',{message:text,audience:'patient',patient_id:PID,patient_name:PNAME});
  if(r.error){t.querySelector('.body').innerHTML=`<span class="muted">Companion unavailable here (${esc(r.error)}). Reminders and booking still work.</span>`;}
  else{t.querySelector('.body').innerHTML=esc(r.text||'(no response)').replace(/\n/g,'<br>');}
  feed.scrollTop=feed.scrollHeight;
});
function addTurn(cls,who,html){const feed=$('#feed');const d=document.createElement('div');d.className='turn '+cls;d.innerHTML=`<div class="who2">${who}</div><div class="body">${html}</div>`;feed.appendChild(d);feed.scrollTop=feed.scrollHeight;return d;}

init();
</script>
</body>
</html>""".replace("__FONT__", FONT_LINK).replace("__BASE__", BASE_CSS)
   .replace("__PATIENT__", _PATIENT_CSS).replace("__LOGO__", LOGO_SVG))
