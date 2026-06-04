"""EggWise Agent CLINIC front desk: branded UI + shared JSON API over the agent tools.

This is the clinic-facing screen (the agent is told it is assisting clinic staff). It
wraps the same tools the agents use, plus a command bar that drives the live multi-agent
coordinator with a clinic session-context so it acts instead of interrogating the user.
The patient-facing screen lives in patient.py and reuses this module's /api endpoints.
All data is synthetic. Nothing is actually sent.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import calendar_tools, config, leads_data, outreach, patient_tools, tools
from .ui_common import BASE_CSS, FONT_LINK, LOGO_SVG

CLINIC = config.CLINIC_NAME

router = APIRouter()

# --------------------------------------------------------------------------
# Shared JSON API (used by both the clinic console and the patient view)
# --------------------------------------------------------------------------


@router.get("/api/leads")
def api_leads(specialty: str = "", location: str = ""):
    return {"clinic": CLINIC, "leads": leads_data.rank_leads(specialty, location)}


@router.get("/api/leads/{lead_id}")
def api_lead(lead_id: str):
    lead = leads_data.get_lead(lead_id)
    if not lead:
        return JSONResponse({"error": "lead not found"}, status_code=404)
    return leads_data.detail_view(lead)


@router.post("/api/leads/{lead_id}/draft")
async def api_draft(lead_id: str, request: Request):
    body = await request.json()
    lead = leads_data.get_lead(lead_id)
    if not lead:
        return JSONResponse({"error": "lead not found"}, status_code=404)
    return outreach.draft_outreach(
        lead, clinic=body.get("clinic") or CLINIC,
        specialty=body.get("specialty", ""), channel=body.get("channel", "email"),
    )


@router.post("/api/outreach/send")
async def api_send(request: Request):
    b = await request.json()
    return outreach.send_outreach(
        b.get("lead_id", ""), b.get("channel", "email"),
        b.get("subject", ""), b.get("body", ""), b.get("to", ""),
    )


@router.get("/api/outbox")
def api_outbox():
    return {"messages": outreach.list_outbox()}


@router.get("/api/patients")
def api_patients():
    return {"patients": tools.list_patients()}


@router.get("/api/triage")
def api_triage():
    return {"patients": tools.list_patients_with_risk()}


@router.post("/api/patients/{patient_id}/report")
def api_report(patient_id: str):
    return tools.generate_health_report(patient_id)


@router.get("/api/adherence")
def api_adherence(patient_id: str):
    return patient_tools.get_my_adherence(patient_id)


@router.post("/api/schedule")
async def api_schedule(request: Request):
    b = await request.json()
    return calendar_tools.schedule_followup(
        b.get("patient_id", ""), b.get("date", ""), b.get("time", "09:00"),
        b.get("reason", "follow-up consultation"), int(b.get("duration_minutes", 30)),
    )


@router.post("/api/book")
async def api_book(request: Request):
    b = await request.json()
    return patient_tools.book_followup(b.get("patient_id", ""), b.get("date", ""), b.get("time", "10:00"))


@router.post("/api/reminder")
async def api_reminder(request: Request):
    b = await request.json()
    return calendar_tools.set_medication_reminder(
        b.get("patient_id", ""), b.get("medication", ""), b.get("time", "20:00"),
        b.get("start_date", ""), int(b.get("days", 14)),
    )


def _context_preamble(audience: str, patient_id: str = "", patient_name: str = "") -> str:
    """Session context the coordinator trusts so it routes/acts without interrogating."""
    if audience == "patient":
        who = f"{patient_name} (patient id {patient_id})" if patient_id else "a patient"
        return (
            f"SESSION CONTEXT: You are speaking directly with {who}. Route to "
            f"patient_companion_agent. Use patient id {patient_id} for every tool call without "
            f"asking the patient to identify themselves. Be warm and concise.\n\n"
        )
    return (
        f"SESSION CONTEXT: You are assisting staff at {CLINIC}, a fertility clinic in "
        f"{config.CLINIC_LOCATION} specializing in {config.CLINIC_SPECIALTY}. The user is clinic "
        f"staff, not a patient. Route to growth_agent (leads, outreach, growth) or care_agent "
        f"(patients, daily logs, reports, triage, scheduling). Default the clinic's specialty and "
        f"location from this context. Do not ask whether the user is a clinician or a patient.\n\n"
    )


_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from google.adk.runners import InMemoryRunner
        from .agent import root_agent
        _runner = InMemoryRunner(agent=root_agent, app_name="console")
    return _runner


@router.post("/api/agent")
async def api_agent(request: Request):
    from google.genai import types

    b = await request.json()
    message = (b.get("message") or "").strip()
    if not message:
        return {"error": "empty message"}
    preamble = _context_preamble(b.get("audience", "clinic"), b.get("patient_id", ""), b.get("patient_name", ""))
    try:
        runner = _get_runner()
        session = await runner.session_service.create_session(app_name="console", user_id="console")
        msg = types.Content(role="user", parts=[types.Part(text=preamble + message)])
        route, used, final = None, [], ""
        async for event in runner.run_async(user_id="console", session_id=session.id, new_message=msg):
            if not (event.content and event.content.parts):
                continue
            for part in event.content.parts:
                fc = getattr(part, "function_call", None)
                if fc:
                    if fc.name == "transfer_to_agent":
                        route = (getattr(fc, "args", {}) or {}).get("agent_name", route)
                    else:
                        used.append(fc.name)
                if getattr(part, "text", None) and part.text.strip():
                    final = part.text.strip()
        return {"route": route, "tools": used, "text": final}
    except Exception as e:
        return {"error": "agent_unavailable", "detail": str(e)[:300]}


def register_console(app):
    """Mount the shared API + the clinic console page."""
    app.include_router(router)

    @app.get("/console", response_class=HTMLResponse)
    def console_page():
        return HTMLResponse(CONSOLE_HTML)


# --------------------------------------------------------------------------
# Clinic console page
# --------------------------------------------------------------------------

_CONSOLE_CSS = r"""
  .switchwrap{display:flex;gap:10px;align-items:center}
  .filters{max-width:680px;margin-bottom:16px}
  .frow{display:flex;gap:10px;margin-bottom:10px}
  .frow input{flex:1;min-width:0;font:inherit;font-size:14px;padding:11px 13px;border:1px solid var(--line2);border-radius:10px;background:var(--card2);color:var(--ink)}
  .frow input::placeholder{color:var(--ink-mute)}
  .frow input:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 3px var(--teal-tint)}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(244px,1fr));gap:14px}
  .lead{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;box-shadow:var(--shadow);cursor:pointer;transition:transform .12s,border-color .12s}
  .lead:hover{transform:translateY(-2px);border-color:var(--teal)}
  .lead .top{display:flex;justify-content:space-between;align-items:flex-start}
  .lead .alias{font-family:'Poppins',sans-serif;font-weight:700;font-size:18px}
  .lead .meta{font-size:12.5px;color:var(--ink-mute);margin-top:1px}
  .score{font-family:'Poppins',sans-serif;font-weight:800;font-size:23px;line-height:1}
  .score small{display:block;font-family:'Nunito Sans';font-weight:700;font-size:9px;letter-spacing:.12em;color:var(--ink-mute);text-transform:uppercase}
  .s-hi{color:var(--teal-lt)}.s-mid{color:var(--gold)}.s-lo{color:var(--ink-mute)}
  .goal{display:inline-block;margin-top:11px;font-size:11px;font-weight:700;color:var(--teal-lt);background:var(--teal-tint);padding:4px 10px;border-radius:20px}
  .reason{font-size:12px;color:var(--ink-soft);margin-top:9px;line-height:1.45}
  .lead .badge{margin-top:11px}
  .scrim{position:fixed;inset:0;background:rgba(5,8,16,.62);opacity:0;pointer-events:none;transition:opacity .2s;z-index:40}
  .scrim.on{opacity:1;pointer-events:auto}
  .drawer{position:fixed;top:0;right:0;height:100%;width:min(520px,96vw);background:var(--bg2);box-shadow:-26px 0 60px -24px rgba(0,0,0,.8);transform:translateX(102%);transition:transform .26s cubic-bezier(.2,.7,.2,1);z-index:50;display:flex;flex-direction:column}
  .drawer.on{transform:none}
  .drawer .dh{display:flex;justify-content:space-between;align-items:center;padding:18px 20px;border-bottom:1px solid var(--line);background:var(--card)}
  .drawer .dh .x{cursor:pointer;border:0;background:transparent;font-size:22px;color:var(--ink-mute);line-height:1}
  .drawer .db{padding:18px 20px;overflow:auto}
  .kv{font-size:13px;color:var(--ink-soft);margin:3px 0}.kv b{color:var(--ink)}
  .clin{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:12px 0}
  .clin h4{margin:0 0 7px;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--teal-lt)}
  .clin.locked{border-style:dashed;color:var(--ink-mute)}
  .seg{display:inline-flex;border:1px solid var(--line2);border-radius:10px;overflow:hidden;margin:10px 0}
  .seg button{border:0;background:var(--card);font:inherit;font-size:12px;font-weight:700;color:var(--ink-mute);padding:7px 14px;cursor:pointer}
  .seg button.on{background:linear-gradient(135deg,var(--teal),var(--teal-deep));color:#fff}
  .compose label{display:block;font-size:11px;color:var(--ink-mute);margin:10px 0 4px}
  .compose input,.compose textarea{width:100%;font:inherit;font-size:13px;padding:10px 12px;border:1px solid var(--line2);border-radius:10px;background:var(--card2);color:var(--ink);resize:vertical}
  .compose textarea{min-height:168px;line-height:1.55}
  .compose input:focus,.compose textarea:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 3px var(--teal-tint)}
  .crow{display:flex;gap:9px;margin-top:13px;align-items:center}
  .report{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:6px 24px 18px;box-shadow:var(--shadow);max-width:640px}
  .report h1{font-size:20px;margin-top:18px}.report h2{font-family:'Poppins',sans-serif;font-weight:700;font-size:15px;color:var(--teal-lt);margin:16px 0 6px}
  .report ul{margin:6px 0;padding-left:20px}.report li{font-size:13.5px;margin:3px 0}
  .report blockquote{border-left:3px solid var(--gold);margin:14px 0 0;padding:7px 14px;color:var(--ink-soft);font-size:12.5px;background:rgba(255,215,0,.06);border-radius:0 8px 8px 0}
  .report em{color:var(--ink-mute)}
  .plist{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:8px;max-width:560px}
  .plist li{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 15px;display:flex;justify-content:space-between;align-items:center;cursor:pointer;gap:12px}
  .plist li:hover{border-color:var(--teal)}
  .pmeta{font-size:12px;color:var(--ink-mute);margin-top:2px}
  .obx{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:10px;max-width:640px}
  .obx li{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:13px 16px}
  .obx .oh{display:flex;justify-content:space-between;font-size:12px;color:var(--ink-mute)}
  .obx .osub{font-weight:700;margin:3px 0}
  .obx .obody{font-size:12.5px;color:var(--ink-soft);white-space:pre-wrap;margin-top:5px;max-height:80px;overflow:hidden}
  .chan{font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;border-radius:6px;background:var(--teal-tint);color:var(--teal-lt)}
"""

CONSOLE_HTML = (r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EggWise Agent &mdash; Clinic Front Desk</title>
__FONT__
<style>__BASE__
__CONSOLE__</style>
</head>
<body>
  <header>
    <div class="brand">__LOGO__ EggWise<span class="dot">.</span></div>
    <div class="tag">Agent</div>
    <div class="spacer"></div>
    <div class="switch"><a class="on" href="/console">Clinic</a><a href="/patient">Patient</a></div>
    <div class="who">Clinic: <b>__CLINIC__</b></div>
    <a class="logout" href="/logout">Sign out</a>
  </header>

  <div class="shell">
    <nav class="side">
      <div class="ntitle">Front desk</div>
      <button class="navbtn active" data-view="leads"><span class="ico">&#9733;</span> Leads</button>
      <button class="navbtn" data-view="schedule"><span class="ico">&#128197;</span> Schedule</button>
      <button class="navbtn" data-view="patients"><span class="ico">&#129658;</span> Patients</button>
      <button class="navbtn" data-view="outbox"><span class="ico">&#9993;</span> Outbox</button>
      <div class="ntitle" style="margin-top:14px">Reference</div>
      <button class="navbtn" onclick="window.open('/dev-ui/','_blank')"><span class="ico">&#9881;</span> ADK console</button>
    </nav>
    <div class="work">
      <main id="main"></main>
      <div class="cmd">
        <div class="feed" id="feed"></div>
        <form id="cmdForm">
          <input id="cmdInput" placeholder="Ask the EggWise Agent (e.g. &quot;find egg-freezing patients in Las Vegas and draft outreach to the top one&quot;)" autocomplete="off">
          <button class="btn teal" type="submit">Send</button>
        </form>
      </div>
    </div>
  </div>

  <nav class="tabbar">
    <button class="navbtn active" data-view="leads"><span class="ico">&#9733;</span>Leads</button>
    <button class="navbtn" data-view="schedule"><span class="ico">&#128197;</span>Schedule</button>
    <button class="navbtn" data-view="patients"><span class="ico">&#129658;</span>Patients</button>
    <button class="navbtn" data-view="outbox"><span class="ico">&#9993;</span>Outbox</button>
  </nav>

  <div class="scrim" id="scrim" onclick="closeDrawer()"></div>
  <div class="drawer" id="drawer"><div class="dh"><div id="dTitle" style="font-family:'Poppins',sans-serif;font-weight:700;font-size:18px"></div><button class="x" onclick="closeDrawer()">&times;</button></div><div class="db" id="dBody"></div></div>
  <div id="toast"></div>

<script>
const $=(s,r=document)=>r.querySelector(s);
const api=async(u,o)=>{const r=await fetch(u,o);return r.json();};
const jpost=(u,b)=>api(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});
let CLINIC='__CLINIC__', SPECIALTY='', LOCATION='';
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('on');setTimeout(()=>t.classList.remove('on'),2600);}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function scoreClass(n){return n>=85?'s-hi':n>=70?'s-mid':'s-lo';}
function setNav(v){document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===v));}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{setNav(b.dataset.view);render(b.dataset.view);});
function render(v){({leads:renderLeads,schedule:renderSchedule,patients:renderPatients,outbox:renderOutbox}[v]||renderLeads)();}

async function renderLeads(){
  $('#main').innerHTML=`<h1>Prospective patients</h1><p class="sub">Lead generation for ${esc(CLINIC)}. Ranked by fit. Click a patient for detail and one-click outreach.</p>
   <div class="filters">
     <div class="frow">
       <input id="fSpec" placeholder="Clinic specialty (e.g. IVF, egg freezing)" value="${esc(SPECIALTY)}" onkeydown="if(event.key==='Enter')applyFilters()">
       <input id="fLoc" placeholder="Clinic location (e.g. Las Vegas, NV)" value="${esc(LOCATION)}" onkeydown="if(event.key==='Enter')applyFilters()">
     </div>
     <button class="btn teal" onclick="applyFilters()">Re-rank</button>
   </div><div class="grid" id="leadGrid"><div class="empty">Loading leads <span class="spin"></span></div></div>`;
  const data=await api(`/api/leads?specialty=${encodeURIComponent(SPECIALTY)}&location=${encodeURIComponent(LOCATION)}`);
  CLINIC=data.clinic||CLINIC;
  const g=$('#leadGrid');g.innerHTML='';
  data.leads.forEach(L=>{const cons=L.consented_to_share;const el=document.createElement('div');el.className='lead';el.onclick=()=>openLead(L.id);
    el.innerHTML=`<div class="top"><div><div class="alias">${esc(L.alias)}</div><div class="meta">${L.age}, ${esc(L.location)}</div></div>
      <div class="score ${scoreClass(L.fit_score)}">${L.fit_score}<small>fit</small></div></div>
      <span class="goal">${esc(L.goal)}</span><div class="reason">${esc(L.fit_reason)}</div>
      <span class="badge ${cons?'cons':'pend'}">${cons?'&#10003; Consented to share':'Consent pending'}</span>`;g.appendChild(el);});
}
function applyFilters(){SPECIALTY=$('#fSpec').value.trim();LOCATION=$('#fLoc').value.trim();renderLeads();}

let CHAN='email';
async function openLead(id){
  const d=await api(`/api/leads/${id}`);
  $('#dTitle').textContent=d.alias+' · '+d.goal;
  const clin=d.clinical_visible
    ? `<div class="clin"><h4>Clinical profile (consented)</h4>${Object.entries(d.clinical).map(([k,v])=>`<div class="kv"><b>${esc(k.toUpperCase())}</b>: ${esc(String(v))}</div>`).join('')}</div>`
    : `<div class="clin locked"><h4>Clinical profile</h4><div class="kv">${esc(d.clinical_note||'Locked')}</div></div>`;
  CHAN='email';
  $('#dBody').innerHTML=`<div class="kv"><b>Age</b>: ${d.age}</div><div class="kv"><b>Location</b>: ${esc(d.location)}</div>
    <div class="kv"><b>Goal</b>: ${esc(d.goal)}</div><div class="kv"><b>Wellness Score</b>: ${d.wellness_score}</div>
    <div class="kv"><b>Signals</b>: ${esc(d.signals||'')}</div><div class="kv"><b>Payment</b>: ${esc(d.payment||'')}</div>${clin}
    <div class="compose"><div class="seg"><button id="chEmail" class="on" onclick="setChan('email')">Email</button><button id="chApp" onclick="setChan('in-app')">In-app message</button></div>
      <button class="btn gold" onclick="genDraft('${d.id}')">&#10024; Draft with EggWise Agent</button>
      <label id="lSub">Subject</label><input id="oSubject" placeholder="(generated)">
      <label>Message</label><textarea id="oBody" placeholder="Click Draft to generate a personalized, consent-safe message, then edit and send."></textarea>
      <div class="crow"><button class="btn teal" id="sendBtn" onclick="sendOutreach('${d.id}')">Send</button>
      <span class="muted">Demo: records to the Outbox. No PHI is ever included in outreach.</span></div></div>`;
  openDrawer();
}
function setChan(c){CHAN=c;$('#chEmail').classList.toggle('on',c==='email');$('#chApp').classList.toggle('on',c==='in-app');
  const show=(c!=='in-app');$('#oSubject').style.display=show?'':'none';$('#lSub').style.display=show?'':'none';}
async function genDraft(id){const btn=event.target;btn.disabled=true;btn.innerHTML='Drafting <span class="spin"></span>';
  const d=await jpost(`/api/leads/${id}/draft`,{clinic:CLINIC,specialty:SPECIALTY,channel:CHAN});
  $('#oSubject').value=d.subject||'';$('#oBody').value=d.body||'';btn.disabled=false;btn.innerHTML='&#10024; Draft with EggWise Agent';}
async function sendOutreach(id){const body=$('#oBody').value.trim();if(!body){toast('Draft a message first');return;}
  const b=$('#sendBtn');b.disabled=true;await jpost('/api/outreach/send',{lead_id:id,channel:CHAN,subject:$('#oSubject').value,body});
  b.disabled=false;closeDrawer();toast('Sent. Saved to Outbox.');}
function openDrawer(){$('#drawer').classList.add('on');$('#scrim').classList.add('on');}
function closeDrawer(){$('#drawer').classList.remove('on');$('#scrim').classList.remove('on');}

function renderSchedule(){
  $('#main').innerHTML=`<h1>Schedule</h1><p class="sub">Create follow-up invites and medication reminders. Each returns a real add-to-calendar link.</p>
  <div class="panel"><h3>Follow-up appointment</h3>
    <div class="field"><label>Patient id</label><input id="sPid" value="pt-jasmine"></div>
    <div class="row2"><div class="field"><label>Date</label><input id="sDate" type="date" value="2026-06-15"></div><div class="field"><label>Time</label><input id="sTime" type="time" value="09:00"></div></div>
    <div class="field"><label>Reason</label><input id="sReason" value="cycle review"></div>
    <button class="btn teal" onclick="doSchedule()">Create invite</button><div id="sOut"></div></div>
  <div class="panel"><h3>Medication reminder</h3>
    <div class="field"><label>Patient id</label><input id="rPid" value="pt-jasmine"></div>
    <div class="row2"><div class="field"><label>Medication</label><input id="rMed" value="evening medication"></div><div class="field"><label>Time</label><input id="rTime" type="time" value="20:00"></div></div>
    <div class="field"><label>Repeat for (days)</label><input id="rDays" type="number" value="14"></div>
    <button class="btn teal" onclick="doReminder()">Create reminder</button><div id="rOut"></div></div>`;
}
async function doSchedule(){const r=await jpost('/api/schedule',{patient_id:$('#sPid').value,date:$('#sDate').value,time:$('#sTime').value,reason:$('#sReason').value});
  $('#sOut').innerHTML=r.error?`<div class="result">${esc(r.error)}</div>`:`<div class="result"><b>${esc(r.title)}</b><br>${esc(r.start)} (${esc(r.timezone)})<br><br><a class="btn gold" href="${r.google_calendar_link}" target="_blank">Add to Google Calendar</a><div class="muted" style="margin-top:8px">${esc(r.note)}</div></div>`;}
async function doReminder(){const r=await jpost('/api/reminder',{patient_id:$('#rPid').value,medication:$('#rMed').value,time:$('#rTime').value,days:$('#rDays').value});
  $('#rOut').innerHTML=r.error?`<div class="result">${esc(r.error)}</div>`:`<div class="result"><b>${esc(r.medication)}</b> · ${esc(r.frequency)}<br><br><a class="btn gold" href="${r.google_calendar_link}" target="_blank">Add reminder to Google Calendar</a><div class="muted" style="margin-top:8px">${esc(r.note)}</div></div>`;}

async function renderPatients(){
  $('#main').innerHTML=`<h1>Patients</h1><p class="sub">Triage board: everyone ranked by risk from their daily logs. Open a patient for a full report.</p><ul class="plist" id="pList"><li>Loading <span class="spin"></span></li></ul>`;
  const data=await api('/api/triage');$('#pList').innerHTML='';
  data.patients.forEach(p=>{const li=document.createElement('li');li.onclick=()=>showReport(p.id);
    li.innerHTML=`<div><b>${esc(p.name)}</b> <span class="muted">${esc(p.id)}</span><div class="pmeta">${Math.round(p.adherence_rate*100)}% adherence · ${p.doses_missed} missed · streak ${p.current_streak_days}d</div></div>
      <span class="badge ${p.risk_level}">${p.risk_level==='high'?'At risk':p.risk_level==='watch'?'Watch':'Stable'}</span>`;$('#pList').appendChild(li);});
}
async function showReport(id){
  $('#main').innerHTML=`<button class="btn ghost" onclick="renderPatients()">&lsaquo; Back to triage</button><div id="rep" style="margin-top:14px"><div class="empty">Generating report <span class="spin"></span></div></div>`;
  const r=await jpost(`/api/patients/${id}/report`,{});
  $('#rep').innerHTML=r.error?`<div class="result">${esc(r.error)}</div>`:`<div class="report">${mdToHtml(r.report_markdown)}</div>`;
}

async function renderOutbox(){
  $('#main').innerHTML=`<h1>Outbox</h1><p class="sub">One-click sends are recorded here (demo). Nothing actually leaves the system.</p><ul class="obx" id="obx"></ul>`;
  const data=await api('/api/outbox');const o=$('#obx');
  if(!data.messages.length){o.innerHTML='<div class="empty">No messages yet. Draft and send outreach from the Leads tab.</div>';return;}
  data.messages.forEach(m=>{const li=document.createElement('li');
    li.innerHTML=`<div class="oh"><span><span class="chan">${esc(m.channel)}</span> &nbsp;to ${esc(m.to)}</span><span>${esc(m.sent_at)}</span></div>${m.subject?`<div class="osub">${esc(m.subject)}</div>`:''}<div class="obody">${esc(m.body)}</div>`;o.appendChild(li);});
}

$('#cmdForm').addEventListener('submit',async e=>{
  e.preventDefault();const inp=$('#cmdInput');const text=inp.value.trim();if(!text)return;inp.value='';
  const feed=$('#feed');feed.classList.add('on');addTurn('me','You',text);
  const t=addTurn('agent','EggWise Agent','<span class="spin"></span>');
  const r=await jpost('/api/agent',{message:text,audience:'clinic'});
  if(r.error){t.querySelector('.body').innerHTML=`<span class="muted">Agent unavailable here (${esc(r.error)}). The console actions above still work.</span>`;}
  else{const chip=r.route?`<span class="chip">${esc(r.route.replace('_agent',''))}</span>`:'';const tl=(r.tools&&r.tools.length)?`<span class="chip">${r.tools.map(esc).join(', ')}</span>`:'';
    t.querySelector('.who2').innerHTML='EggWise Agent'+chip+tl;t.querySelector('.body').innerHTML=esc(r.text||'(no response)').replace(/\n/g,'<br>');}
  feed.scrollTop=feed.scrollHeight;
});
function addTurn(cls,who,html){const feed=$('#feed');const d=document.createElement('div');d.className='turn '+cls;d.innerHTML=`<div class="who2">${who}</div><div class="body">${html}</div>`;feed.appendChild(d);feed.scrollTop=feed.scrollHeight;return d;}

function mdToHtml(md){const lines=(md||'').split('\n');let out='';let inList=false;const flush=()=>{if(inList){out+='</ul>';inList=false;}};
  for(let ln of lines){if(/^# /.test(ln)){flush();out+='<h1>'+inline(ln.slice(2))+'</h1>';}
    else if(/^## /.test(ln)){flush();out+='<h2>'+inline(ln.slice(3))+'</h2>';}
    else if(/^- /.test(ln)){if(!inList){out+='<ul>';inList=true;}out+='<li>'+inline(ln.slice(2))+'</li>';}
    else if(/^> /.test(ln)){flush();out+='<blockquote>'+inline(ln.slice(2))+'</blockquote>';}
    else if(/^\*.*\*$/.test(ln.trim())){flush();out+='<p><em>'+inline(ln.trim().replace(/^\*|\*$/g,''))+'</em></p>';}
    else if(ln.trim()===''){flush();}else{flush();out+='<p>'+inline(ln)+'</p>';}}
  flush();return out;}
function inline(s){return esc(s).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');}

renderLeads();
</script>
</body>
</html>""".replace("__FONT__", FONT_LINK).replace("__BASE__", BASE_CSS)
   .replace("__CONSOLE__", _CONSOLE_CSS).replace("__LOGO__", LOGO_SVG).replace("__CLINIC__", CLINIC))
