"""EggWise patient Companion: the full patient-facing experience.

You pick which demo patient you are; the Companion agent is given that identity in the
session context, so it never asks who you are. Tabs: Home (dashboard), Ask EggWise (chat),
Care (reminders, booking, daily check-in), Learn (clinic-approved answers). Clinical
questions hit the medical-safety guardrail and escalate. Reuses console.py's /api endpoints.
"""
from __future__ import annotations

from fastapi.responses import HTMLResponse

from .ui_common import ATTRIB, BASE_CSS, FONT_LINK, LOGO_SVG


def register_patient(app):
    @app.get("/patient", response_class=HTMLResponse)
    def patient_page():
        return HTMLResponse(PATIENT_HTML)


_PATIENT_CSS = r"""
  .psel{font:inherit;font-size:13px;font-weight:700;color:var(--ink);background:var(--card2);border:1px solid var(--line2);border-radius:9px;padding:7px 10px}
  .hero{font-family:'Poppins',sans-serif;font-weight:700;font-size:26px;margin:2px 0 2px}
  .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px;max-width:760px;margin-bottom:16px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:var(--shadow)}
  .card .lab{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-mute);font-weight:700}
  .card .big{font-family:'Poppins',sans-serif;font-weight:800;font-size:30px;line-height:1.1;margin-top:6px}
  .card .big.ok{color:var(--ok)} .card .big.warn{color:var(--warn)} .card .big.teal{color:var(--teal-lt)}
  .pill{display:inline-block;font-size:11px;font-weight:700;padding:4px 11px;border-radius:20px;margin-top:8px}
  .pill.ok{background:rgba(78,205,196,.15);color:var(--ok)} .pill.warn{background:rgba(233,185,73,.16);color:var(--warn)}
  .banner{max-width:760px;display:flex;justify-content:space-between;align-items:center;gap:12px;background:linear-gradient(135deg,rgba(116,160,160,.14),rgba(255,215,0,.08));border:1px solid var(--line);border-radius:16px;padding:16px 18px;margin-bottom:16px}
  .banner .bt{font-family:'Poppins',sans-serif;font-weight:700;font-size:15px}
  .banner .bs{font-size:13px;color:var(--ink-soft);margin-top:2px}
  .encourage{max-width:760px;color:var(--ink-soft);font-size:14px;margin-bottom:16px}
  .qa{display:flex;gap:10px;flex-wrap:wrap;max-width:760px}
  .lcards{display:flex;flex-direction:column;gap:10px;max-width:660px}
  .lcard{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
  .lcard h4{margin:0 0 5px;font-family:'Poppins',sans-serif;font-weight:700;font-size:14px;color:var(--teal-lt);text-transform:capitalize}
  .lcard p{margin:0;font-size:13.5px;color:var(--ink-soft);line-height:1.5}
  .seg{display:inline-flex;border:1px solid var(--line2);border-radius:10px;overflow:hidden}
  .seg button{border:0;background:var(--card2);font:inherit;font-size:12px;font-weight:700;color:var(--ink-mute);padding:8px 14px;cursor:pointer}
  .seg button.on{background:linear-gradient(135deg,var(--teal),var(--teal-deep));color:#fff}
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
      <button class="navbtn" data-view="chat"><span class="ico">&#128172;</span> Ask EggWise</button>
      <button class="navbtn" data-view="care"><span class="ico">&#128138;</span> Reminders &amp; visits</button>
      <button class="navbtn" data-view="learn"><span class="ico">&#128214;</span> Learn</button>
    </nav>
    <div class="work"><main id="main"></main></div>
  </div>

  <nav class="tabbar">
    <button class="navbtn active" data-view="home"><span class="ico">&#127968;</span>Home</button>
    <button class="navbtn" data-view="chat"><span class="ico">&#128172;</span>Ask</button>
    <button class="navbtn" data-view="care"><span class="ico">&#128138;</span>Care</button>
    <button class="navbtn" data-view="learn"><span class="ico">&#128214;</span>Learn</button>
  </nav>

  <div id="toast"></div>

<script>
const $=(s,r=document)=>r.querySelector(s);
const api=async(u,o)=>{const r=await fetch(u,o);return r.json();};
const jpost=(u,b)=>api(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});
const ATTRIB=`__ATTRIB__`;
let PID='', PNAME='', CHAT=[];
const SUGGEST=["How am I doing on my meds?","Set a reminder for 8pm","What should I bring to my appointment?","I have a question for my care team"];
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('on');setTimeout(()=>t.classList.remove('on'),2600);}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function firstName(n){return (n||'').replace(/\s*\(.*\)/,'').split(' ')[0];}
function setNav(v){document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===v));}
function go(v){setNav(v);render(v);}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>go(b.dataset.view));
function render(v){({home:renderHome,chat:renderChat,care:renderCare,learn:renderLearn}[v]||renderHome)();}

async function init(){
  const data=await api('/api/patients');const sel=$('#psel');
  data.patients.forEach(p=>{const o=document.createElement('option');o.value=p.id;o.textContent=firstName(p.name);sel.appendChild(o);});
  const def=data.patients.find(p=>p.id==='pt-jasmine')||data.patients[0];PID=def.id;PNAME=def.name;sel.value=PID;renderHome();
}
function pickPatient(id){PID=id;const s=$('#psel');PNAME=s.options[s.selectedIndex].text;CHAT=[];go('home');}

/* HOME dashboard */
async function renderHome(){
  $('#main').innerHTML=`<div class="hero">Hi ${esc(firstName(PNAME))} &#128075;</div>
   <p class="sub">Here's your EggWise summary. I can set reminders, help you book a visit, and answer questions. Anything medical, I loop in your care team.</p>
   <div id="ad"><div class="empty">Loading your summary <span class="spin"></span></div></div>`;
  const a=await api('/api/adherence?patient_id='+encodeURIComponent(PID));
  if(a.error||a.name===undefined){$('#ad').innerHTML='';return;}
  const days=a.days_reviewed||0;const pct=days?Math.round((days-a.doses_missed)/days*100):100;
  const mood=a.avg_mood==null?'&ndash;':a.avg_mood+'/5';
  $('#ad').innerHTML=`
   <div class="banner"><div><div class="bt">How are you today?</div><div class="bs">Take 10 seconds to log a quick check-in.</div></div><button class="btn teal" onclick="go('care')">Daily check-in</button></div>
   <div class="cards">
    <div class="card"><div class="lab">Adherence (${days}d)</div><div class="big ${a.on_track?'ok':'warn'}">${pct}%</div><span class="pill ${a.on_track?'ok':'warn'}">${a.on_track?'On track':a.doses_missed+' dose(s) missed'}</span></div>
    <div class="card"><div class="lab">Current streak</div><div class="big teal">${a.current_streak_days}<span style="font-size:14px;color:var(--ink-mute)"> days</span></div></div>
    <div class="card"><div class="lab">Avg mood</div><div class="big">${mood}</div></div>
    <div class="card"><div class="lab">Next visit</div><div class="big" style="font-size:18px;color:var(--ink-soft)">Not booked</div><button class="btn ghost" style="margin-top:8px" onclick="go('care')">Book a follow-up</button></div>
   </div>
   <div class="encourage">${a.on_track?"You're doing great. A steady routine really helps, want me to set a reminder so it stays easy?":"It's okay, missing a dose happens. Let's set a reminder together to make the next ones easier."}</div>
   <div class="qa"><button class="btn teal" onclick="go('chat')">Ask EggWise</button><button class="btn ghost" onclick="go('care')">Set a reminder</button><button class="btn ghost" onclick="go('learn')">Learn</button></div>
   ${ATTRIB}`;
}

/* CHAT */
function renderChat(){
  $('#main').innerHTML=`<div class="chatwrap"><div class="chips">${SUGGEST.map(s=>`<button class="chip2" data-q="${esc(s)}" onclick="ask(this.dataset.q)">${esc(s)}</button>`).join('')}</div>
    <div class="tx" id="tx"></div><form class="chatin" id="chatForm"><input id="ci" placeholder="Message EggWise..." autocomplete="off"><button class="btn teal" type="submit">Send</button></form></div>`;
  if(!CHAT.length)CHAT.push({role:'bot',html:esc(`Hi ${firstName(PNAME)}, I'm your EggWise companion. I can help with reminders, booking a visit, and everyday questions. How can I help today?`)});
  drawChat();$('#chatForm').addEventListener('submit',e=>{e.preventDefault();const v=$('#ci').value.trim();if(v){$('#ci').value='';ask(v);}});$('#ci').focus();
}
function drawChat(){const tx=$('#tx');if(!tx)return;tx.innerHTML=CHAT.map(m=>`<div class="msg ${m.role==='me'?'me':'bot'}">${m.role==='me'?esc(m.html):m.html}</div>`).join('');$('#main').scrollTop=$('#main').scrollHeight;}
async function ask(text){
  if(!$('#tx'))go('chat');
  CHAT.push({role:'me',html:text});const idx=CHAT.push({role:'bot',html:'<span class="spin"></span>'})-1;drawChat();
  const r=await jpost('/api/agent',{message:text,audience:'patient',patient_id:PID,patient_name:PNAME});
  CHAT[idx].html=r.error?`<span class="muted">Companion unavailable here (${esc(r.error)}). Reminders and booking still work.</span>`:mdToHtml(r.text||'(no response)');
  drawChat();
}

/* CARE */
function renderCare(){
  $('#main').innerHTML=`<h1>Reminders &amp; visits</h1><p class="sub">Set a reminder, request a follow-up, or log how today went.</p>
  <div class="panel"><h3>Medication reminder</h3><div class="row2"><div class="field"><label>Medication</label><input id="rMed" value="evening medication"></div><div class="field"><label>Time</label><input id="rTime" type="time" value="20:00"></div></div>
    <div class="field"><label>Repeat for (days)</label><input id="rDays" type="number" value="14"></div><button class="btn teal" onclick="doReminder()">Create reminder</button><div id="rOut"></div></div>
  <div class="panel"><h3>Book a follow-up</h3><div class="row2"><div class="field"><label>Preferred date</label><input id="bDate" type="date" value="2026-06-16"></div><div class="field"><label>Time</label><input id="bTime" type="time" value="10:00"></div></div>
    <button class="btn teal" onclick="doBook()">Request follow-up</button><div id="bOut"></div></div>
  <div class="panel"><h3>Daily check-in</h3><div class="field"><label>Did you take your medication today?</label><div class="seg"><button id="mYes" class="on" onclick="setMeds(true)">Yes</button><button id="mNo" onclick="setMeds(false)">Not yet</button></div></div>
    <div class="row2"><div class="field"><label>Mood (1 low - 5 great)</label><select id="cMood"><option>1</option><option>2</option><option selected>3</option><option>4</option><option>5</option></select></div><div class="field"><label>Note (optional)</label><input id="cNote" placeholder="Anything to remember"></div></div>
    <button class="btn teal" onclick="doCheckin()">Log check-in</button><div id="cOut"></div></div>${ATTRIB}`;
}
let MEDS=true;
function setMeds(v){MEDS=v;$('#mYes').classList.toggle('on',v);$('#mNo').classList.toggle('on',!v);}
async function doReminder(){const r=await jpost('/api/reminder',{patient_id:PID,medication:$('#rMed').value,time:$('#rTime').value,days:$('#rDays').value});$('#rOut').innerHTML=r.error?`<div class="result">${esc(r.error)}</div>`:`<div class="result"><b>${esc(r.medication)}</b> · ${esc(r.frequency)}<br><br><a class="btn gold" href="${r.google_calendar_link}" target="_blank">Add to Google Calendar</a></div>`;}
async function doBook(){const r=await jpost('/api/book',{patient_id:PID,date:$('#bDate').value,time:$('#bTime').value});$('#bOut').innerHTML=r.error?`<div class="result">${esc(r.error)}</div>`:`<div class="result"><b>${esc(r.title||'Follow-up')}</b><br>${esc(r.start||'')}<br><br><a class="btn gold" href="${r.google_calendar_link}" target="_blank">Add to Google Calendar</a></div>`;}
async function doCheckin(){const r=await jpost('/api/checkin',{patient_id:PID,meds_taken:MEDS,mood:$('#cMood').value,note:$('#cNote').value});$('#cOut').innerHTML=`<div class="result">${esc(r.message||'Logged.')}</div>`;toast('Check-in logged');}

/* LEARN */
async function renderLearn(){
  $('#main').innerHTML=`<h1>Learn</h1><p class="sub">Clinic-approved answers to common questions. For anything about your specific care, just ask and I'll loop in your team.</p><div class="lcards" id="lc"><div class="empty">Loading <span class="spin"></span></div></div><div id="att"></div>`;
  const data=await api('/api/info/topics');const lc=$('#lc');lc.innerHTML='';
  data.topics.forEach(t=>{const d=document.createElement('div');d.className='lcard';d.innerHTML=`<h4>${esc(t.topic.replace(/_/g,' '))}</h4><p>${esc(t.answer)}</p>`;lc.appendChild(d);});
  $('#att').innerHTML=ATTRIB;
}

function mdToHtml(md){const lines=(md||'').split('\n');let out='';let inList=false;const flush=()=>{if(inList){out+='</ul>';inList=false;}};
  for(let raw of lines){const ln=raw.replace(/\s+$/,'');const t=ln.trim();
    if(/^(\-\-\-|\*\*\*|___)$/.test(t)){flush();out+='<hr>';}
    else if(/^### /.test(t)){flush();out+='<h3>'+inl(t.slice(4))+'</h3>';}
    else if(/^## /.test(t)){flush();out+='<h2>'+inl(t.slice(3))+'</h2>';}
    else if(/^# /.test(t)){flush();out+='<h2>'+inl(t.slice(2))+'</h2>';}
    else if(/^[-*] /.test(t)){if(!inList){out+='<ul>';inList=true;}out+='<li>'+inl(t.slice(2))+'</li>';}
    else if(t===''){flush();}else{flush();out+='<p>'+inl(ln)+'</p>';}}
  flush();return out;}
function inl(s){return esc(s).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');}

init();
</script>
</body>
</html>""".replace("__FONT__", FONT_LINK).replace("__BASE__", BASE_CSS)
   .replace("__PATIENT__", _PATIENT_CSS).replace("__LOGO__", LOGO_SVG).replace("__ATTRIB__", ATTRIB))
