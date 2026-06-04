"""EggWise Agent front-desk console: branded UI + JSON API over the agent's tools.

This is the screen judges see after login. It wraps the same tools the agents use
(lead ranking + consent gating, outreach drafting + simulated outbox, scheduling and
reminders, health reports) in a product UI, plus a command bar that drives the live
multi-agent coordinator. All data is synthetic. Nothing is actually sent.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import calendar_tools, leads_data, outreach, tools

CLINIC = "Bay Area Fertility Institute"

router = APIRouter()

# --------------------------------------------------------------------------
# JSON API
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
        lead,
        clinic=body.get("clinic") or CLINIC,
        specialty=body.get("specialty", ""),
        channel=body.get("channel", "email"),
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


@router.post("/api/patients/{patient_id}/report")
def api_report(patient_id: str):
    return tools.generate_health_report(patient_id)


@router.post("/api/schedule")
async def api_schedule(request: Request):
    b = await request.json()
    return calendar_tools.schedule_followup(
        b.get("patient_id", ""), b.get("date", ""), b.get("time", "09:00"),
        b.get("reason", "follow-up consultation"), int(b.get("duration_minutes", 30)),
    )


@router.post("/api/reminder")
async def api_reminder(request: Request):
    b = await request.json()
    return calendar_tools.set_medication_reminder(
        b.get("patient_id", ""), b.get("medication", ""), b.get("time", "20:00"),
        b.get("start_date", ""), int(b.get("days", 14)),
    )


# Command bar: drive the live multi-agent coordinator.
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
    try:
        runner = _get_runner()
        session = await runner.session_service.create_session(app_name="console", user_id="console")
        msg = types.Content(role="user", parts=[types.Part(text=message)])
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
    except Exception as e:  # offline / no creds: graceful, the rest of the console still works
        return {"error": "agent_unavailable", "detail": str(e)[:300]}


def register_console(app):
    """Mount the console page and API on the FastAPI app."""
    app.include_router(router)

    @app.get("/console", response_class=HTMLResponse)
    def console_page():
        return HTMLResponse(CONSOLE_HTML)


# --------------------------------------------------------------------------
# UI (single self-contained page)
# --------------------------------------------------------------------------

LOGO_SVG = (
    '<svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg" width="30" height="30" aria-hidden="true">'
    '<path d="M50 20C25 20 10 55 10 80C10 105 27.9086 120 50 120C72.0914 120 90 105 90 80C90 55 75 20 50 20Z" fill="#74A0A0"/>'
    '<path d="M50 68L55.5 74.5L61.5 65.5L67 72" stroke="#FFD700" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
    "</svg>"
)

CONSOLE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EggWise Agent &mdash; Front Desk</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{
    --paper:#FBF6EA; --card:#FFFFFF; --ink:#2C1F1A; --ink-soft:#5B4A3F; --ink-mute:#8A776A;
    --teal:#2D6A6D; --teal-deep:#1F4E50; --teal-tint:#EDF3F2; --gold:#A66D14; --gold-soft:#EFD79A;
    --line:rgba(44,31,26,.10); --line2:rgba(44,31,26,.16); --ok:#2E7D5B; --shadow:0 12px 30px -16px rgba(44,31,26,.30);
  }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%}
  body{font-family:'Inter',system-ui,sans-serif;color:var(--ink);background:var(--paper);
    -webkit-font-smoothing:antialiased;display:flex;flex-direction:column;height:100vh;overflow:hidden}
  a{color:var(--teal);text-decoration:none}
  /* top bar */
  header{display:flex;align-items:center;gap:12px;padding:12px 20px;background:var(--card);
    border-bottom:1px solid var(--line)}
  .brand{display:flex;align-items:center;gap:9px;font-family:'Fraunces',serif;font-weight:600;font-size:19px}
  .brand .dot{color:var(--gold)}
  .tag{font-size:10px;letter-spacing:.28em;text-transform:uppercase;color:var(--teal);font-weight:600;
    border-left:1px solid var(--line2);padding-left:12px;margin-left:4px}
  header .spacer{flex:1}
  .clinic{font-size:13px;color:var(--ink-soft)}
  .clinic b{color:var(--ink)}
  header .logout{font-size:12px;color:var(--ink-mute);border:1px solid var(--line2);padding:6px 11px;border-radius:8px}
  header .logout:hover{color:var(--ink);border-color:var(--teal)}
  /* body grid */
  .shell{flex:1;display:grid;grid-template-columns:204px 1fr;min-height:0}
  nav{background:var(--card);border-right:1px solid var(--line);padding:14px 12px;display:flex;flex-direction:column;gap:3px}
  nav button{display:flex;align-items:center;gap:10px;width:100%;text-align:left;border:0;background:transparent;
    font:inherit;font-size:14px;color:var(--ink-soft);padding:10px 12px;border-radius:9px;cursor:pointer}
  nav button .ico{width:18px;text-align:center;opacity:.8}
  nav button:hover{background:var(--teal-tint);color:var(--ink)}
  nav button.active{background:var(--teal);color:#fff;font-weight:600}
  nav .ntitle{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--ink-mute);padding:6px 12px 4px}
  .work{display:flex;flex-direction:column;min-height:0}
  main{flex:1;overflow:auto;padding:24px 26px}
  h1{font-family:'Fraunces',serif;font-weight:600;font-size:24px;margin:0 0 3px}
  .sub{color:var(--ink-mute);font-size:13px;margin:0 0 18px}
  /* leads */
  .filters{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap}
  .filters input{font:inherit;font-size:13px;padding:9px 12px;border:1px solid var(--line2);border-radius:9px;background:var(--card);color:var(--ink)}
  .filters input:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 3px var(--teal-tint)}
  .btn{font:inherit;font-weight:600;font-size:13px;border:0;border-radius:9px;cursor:pointer;padding:9px 14px}
  .btn.teal{background:var(--teal);color:#fff}.btn.teal:hover{background:var(--teal-deep)}
  .btn.gold{background:linear-gradient(180deg,#C79A3A,var(--gold));color:#1A1208}.btn.gold:hover{filter:brightness(1.06)}
  .btn.ghost{background:transparent;border:1px solid var(--line2);color:var(--ink-soft)}.btn.ghost:hover{border-color:var(--teal);color:var(--ink)}
  .btn:disabled{opacity:.5;cursor:default}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(244px,1fr));gap:14px}
  .lead{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px;box-shadow:var(--shadow);cursor:pointer;transition:transform .12s,border-color .12s}
  .lead:hover{transform:translateY(-2px);border-color:var(--teal)}
  .lead .top{display:flex;justify-content:space-between;align-items:flex-start}
  .lead .alias{font-family:'Fraunces',serif;font-weight:600;font-size:18px}
  .lead .meta{font-size:12.5px;color:var(--ink-mute);margin-top:1px}
  .score{font-family:'Fraunces',serif;font-weight:700;font-size:22px;line-height:1}
  .score small{display:block;font-family:'Inter';font-weight:600;font-size:9px;letter-spacing:.12em;color:var(--ink-mute);text-transform:uppercase}
  .s-hi{color:var(--teal)}.s-mid{color:var(--gold)}.s-lo{color:var(--ink-mute)}
  .goal{display:inline-block;margin-top:10px;font-size:11px;font-weight:600;color:var(--teal-deep);background:var(--teal-tint);padding:3px 9px;border-radius:20px}
  .reason{font-size:12px;color:var(--ink-soft);margin-top:9px;line-height:1.4}
  .badge{font-size:10px;font-weight:600;padding:3px 8px;border-radius:20px;margin-top:11px;display:inline-block}
  .badge.cons{background:#E5F0EA;color:var(--ok)}
  .badge.pend{background:#F3ECDD;color:var(--gold)}
  /* drawer */
  .scrim{position:fixed;inset:0;background:rgba(28,20,15,.34);opacity:0;pointer-events:none;transition:opacity .2s;z-index:40}
  .scrim.on{opacity:1;pointer-events:auto}
  .drawer{position:fixed;top:0;right:0;height:100%;width:min(520px,94vw);background:var(--paper);box-shadow:-20px 0 50px -20px rgba(0,0,0,.4);
    transform:translateX(102%);transition:transform .26s cubic-bezier(.2,.7,.2,1);z-index:50;display:flex;flex-direction:column}
  .drawer.on{transform:none}
  .drawer .dh{display:flex;justify-content:space-between;align-items:center;padding:18px 20px;border-bottom:1px solid var(--line);background:var(--card)}
  .drawer .dh .x{cursor:pointer;border:0;background:transparent;font-size:22px;color:var(--ink-mute);line-height:1}
  .drawer .db{padding:18px 20px;overflow:auto}
  .kv{font-size:13px;color:var(--ink-soft);margin:3px 0}
  .kv b{color:var(--ink)}
  .clin{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:12px 14px;margin:12px 0}
  .clin h4{margin:0 0 7px;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--teal)}
  .clin.locked{border-style:dashed;color:var(--ink-mute)}
  .compose{margin-top:8px}
  .seg{display:inline-flex;border:1px solid var(--line2);border-radius:9px;overflow:hidden;margin:10px 0}
  .seg button{border:0;background:var(--card);font:inherit;font-size:12px;font-weight:600;color:var(--ink-soft);padding:7px 14px;cursor:pointer}
  .seg button.on{background:var(--teal);color:#fff}
  .compose label{display:block;font-size:11px;color:var(--ink-mute);margin:10px 0 4px;letter-spacing:.04em}
  .compose input,.compose textarea{width:100%;font:inherit;font-size:13px;padding:10px 12px;border:1px solid var(--line2);border-radius:9px;background:var(--card);color:var(--ink);resize:vertical}
  .compose textarea{min-height:170px;line-height:1.5}
  .compose input:focus,.compose textarea:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 3px var(--teal-tint)}
  .crow{display:flex;gap:9px;margin-top:13px;align-items:center}
  .muted{color:var(--ink-mute);font-size:11.5px}
  /* forms / panels */
  .panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;box-shadow:var(--shadow);max-width:560px;margin-bottom:16px}
  .panel h3{margin:0 0 12px;font-family:'Fraunces',serif;font-size:17px}
  .field{margin-bottom:11px}
  .field label{display:block;font-size:12px;color:var(--ink-mute);margin-bottom:4px}
  .field input,.field select{width:100%;font:inherit;font-size:13px;padding:9px 12px;border:1px solid var(--line2);border-radius:9px;background:#fff;color:var(--ink)}
  .field input:focus,.field select:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 3px var(--teal-tint)}
  .row2{display:grid;grid-template-columns:1fr 1fr;gap:11px}
  .result{margin-top:14px;padding:13px 15px;border:1px solid var(--line);border-radius:11px;background:var(--teal-tint);font-size:13px}
  .report{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:6px 24px 18px;box-shadow:var(--shadow);max-width:640px}
  .report h1{font-size:21px;margin-top:18px}.report h2{font-family:'Fraunces',serif;font-size:15px;color:var(--teal-deep);margin:16px 0 6px}
  .report ul{margin:6px 0;padding-left:20px}.report li{font-size:13.5px;margin:3px 0}
  .report blockquote{border-left:3px solid var(--gold);margin:14px 0 0;padding:6px 14px;color:var(--ink-soft);font-size:12.5px;background:#FCF7EC}
  .report em{color:var(--ink-mute)}
  .plist{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:8px;max-width:420px}
  .plist li{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:12px 15px;display:flex;justify-content:space-between;align-items:center;cursor:pointer}
  .plist li:hover{border-color:var(--teal)}
  .obx{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:10px;max-width:640px}
  .obx li{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px 16px}
  .obx .oh{display:flex;justify-content:space-between;font-size:12px;color:var(--ink-mute)}
  .obx .osub{font-weight:600;margin:3px 0}
  .obx .obody{font-size:12.5px;color:var(--ink-soft);white-space:pre-wrap;margin-top:5px;max-height:80px;overflow:hidden}
  .chan{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;border-radius:5px;background:var(--teal-tint);color:var(--teal-deep)}
  .empty{color:var(--ink-mute);font-size:13px;padding:18px 0}
  /* command bar */
  .cmd{border-top:1px solid var(--line);background:var(--card);padding:11px 18px}
  .cmd .feed{max-height:0;overflow:auto;transition:max-height .2s}
  .cmd .feed.on{max-height:220px;margin-bottom:10px}
  .turn{font-size:13px;margin:8px 0;line-height:1.5}
  .turn .who{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-mute);font-weight:600}
  .turn.me .who{color:var(--gold)}
  .chip{display:inline-block;font-size:10px;font-weight:600;background:var(--teal-tint);color:var(--teal-deep);padding:2px 8px;border-radius:20px;margin-left:7px}
  .cmd form{display:flex;gap:10px;align-items:center}
  .cmd input{flex:1;font:inherit;font-size:14px;padding:12px 15px;border:1px solid var(--line2);border-radius:11px;background:var(--paper);color:var(--ink)}
  .cmd input:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 3px var(--teal-tint)}
  /* toast */
  #toast{position:fixed;bottom:84px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--ink);color:#fff;
    padding:11px 20px;border-radius:11px;font-size:13px;opacity:0;pointer-events:none;transition:all .25s;z-index:80;box-shadow:var(--shadow)}
  #toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
  .spin{display:inline-block;width:13px;height:13px;border:2px solid var(--teal-tint);border-top-color:var(--teal);border-radius:50%;animation:sp .7s linear infinite;vertical-align:-2px}
  @keyframes sp{to{transform:rotate(360deg)}}
</style>
</head>
<body>
  <header>
    <div class="brand">__LOGO__ EggWise<span class="dot">.</span></div>
    <div class="tag">Agent &middot; Front Desk</div>
    <div class="spacer"></div>
    <div class="clinic">Signed in as <b id="clinicName">clinic</b></div>
    <a class="logout" href="/logout">Sign out</a>
  </header>

  <div class="shell">
    <nav>
      <div class="ntitle">Front desk</div>
      <button data-view="leads" class="active"><span class="ico">&#9733;</span> Leads</button>
      <button data-view="schedule"><span class="ico">&#128197;</span> Schedule</button>
      <button data-view="patients"><span class="ico">&#129658;</span> Patients</button>
      <button data-view="outbox"><span class="ico">&#9993;</span> Outbox</button>
      <div class="ntitle" style="margin-top:14px">Reference</div>
      <button onclick="window.open('/dev-ui/','_blank')"><span class="ico">&#9881;</span> ADK console</button>
    </nav>

    <div class="work">
      <main id="main"></main>
      <div class="cmd">
        <div class="feed" id="feed"></div>
        <form id="cmdForm">
          <input id="cmdInput" placeholder="Ask the EggWise Agent to do anything (e.g. &quot;find IVF patients near San Jose and draft outreach to the top one&quot;)" autocomplete="off">
          <button class="btn teal" type="submit">Send</button>
        </form>
      </div>
    </div>
  </div>

  <div class="scrim" id="scrim" onclick="closeDrawer()"></div>
  <div class="drawer" id="drawer"><div class="dh"><div id="dTitle" style="font-family:'Fraunces',serif;font-weight:600;font-size:18px"></div><button class="x" onclick="closeDrawer()">&times;</button></div><div class="db" id="dBody"></div></div>
  <div id="toast"></div>

<script>
const $ = (s,r=document)=>r.querySelector(s);
const api = async (url,opts)=>{const r=await fetch(url,opts);return r.json();};
const jpost = (url,body)=>api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
let CLINIC='clinic', SPECIALTY='', LOCATION='';
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('on');setTimeout(()=>t.classList.remove('on'),2600);}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function scoreClass(n){return n>=85?'s-hi':n>=70?'s-mid':'s-lo';}

/* nav */
document.querySelectorAll('nav button[data-view]').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button[data-view]').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');render(b.dataset.view);
});

function render(view){
  if(view==='leads')return renderLeads();
  if(view==='schedule')return renderSchedule();
  if(view==='patients')return renderPatients();
  if(view==='outbox')return renderOutbox();
}

/* LEADS */
async function renderLeads(){
  const m=$('#main');
  m.innerHTML=`<h1>Prospective patients</h1><p class="sub">Ranked by fit for ${esc(CLINIC)}. Click a patient to view detail and draft one-click outreach.</p>
   <div class="filters">
     <input id="fSpec" placeholder="Clinic specialty (e.g. IVF, egg freezing)" value="${esc(SPECIALTY)}">
     <input id="fLoc" placeholder="Clinic location (e.g. San Francisco, CA)" value="${esc(LOCATION)}">
     <button class="btn teal" onclick="applyFilters()">Re-rank</button>
   </div><div class="grid" id="leadGrid"><div class="empty">Loading leads <span class="spin"></span></div></div>`;
  const data=await api(`/api/leads?specialty=${encodeURIComponent(SPECIALTY)}&location=${encodeURIComponent(LOCATION)}`);
  CLINIC=data.clinic||CLINIC;$('#clinicName').textContent=CLINIC;
  const g=$('#leadGrid');g.innerHTML='';
  data.leads.forEach(L=>{
    const cons=L.consented_to_share;
    const el=document.createElement('div');el.className='lead';el.onclick=()=>openLead(L.id);
    el.innerHTML=`<div class="top"><div><div class="alias">${esc(L.alias)}</div><div class="meta">${L.age}, ${esc(L.location)}</div></div>
      <div class="score ${scoreClass(L.fit_score)}">${L.fit_score}<small>fit</small></div></div>
      <span class="goal">${esc(L.goal)}</span>
      <div class="reason">${esc(L.fit_reason)}</div>
      <span class="badge ${cons?'cons':'pend'}">${cons?'&#10003; Consented to share':'Consent pending'}</span>`;
    g.appendChild(el);
  });
}
function applyFilters(){SPECIALTY=$('#fSpec').value.trim();LOCATION=$('#fLoc').value.trim();renderLeads();}

async function openLead(id){
  const d=await api(`/api/leads/${id}`);
  $('#dTitle').textContent=d.alias+' · '+d.goal;
  const clin = d.clinical_visible
    ? `<div class="clin"><h4>Clinical profile (consented)</h4>${Object.entries(d.clinical).map(([k,v])=>`<div class="kv"><b>${esc(k.toUpperCase())}</b>: ${esc(String(v))}</div>`).join('')}</div>`
    : `<div class="clin locked"><h4>Clinical profile</h4><div class="kv">${esc(d.clinical_note||'Locked')}</div></div>`;
  $('#dBody').innerHTML=`
    <div class="kv"><b>Age</b>: ${d.age}</div>
    <div class="kv"><b>Location</b>: ${esc(d.location)}</div>
    <div class="kv"><b>Goal</b>: ${esc(d.goal)}</div>
    <div class="kv"><b>Wellness Score</b>: ${d.wellness_score}</div>
    <div class="kv"><b>Signals</b>: ${esc(d.signals||'')}</div>
    <div class="kv"><b>Payment</b>: ${esc(d.payment||'')}</div>
    ${clin}
    <div class="compose">
      <div class="seg"><button id="chEmail" class="on" onclick="setChan('email')">Email</button><button id="chApp" onclick="setChan('in-app')">In-app message</button></div>
      <button class="btn gold" onclick="genDraft('${d.id}')">&#10024; Draft with EggWise Agent</button>
      <label>Subject</label><input id="oSubject" placeholder="(generated)">
      <label>Message</label><textarea id="oBody" placeholder="Click Draft to generate a personalized, consent-safe message, then edit and send."></textarea>
      <div class="crow"><button class="btn teal" id="sendBtn" onclick="sendOutreach('${d.id}')">Send</button>
      <span class="muted">Demo: records to the Outbox. No PHI is ever included in outreach.</span></div>
    </div>`;
  openDrawer();
}
let CHAN='email';
function setChan(c){CHAN=c;$('#chEmail').classList.toggle('on',c==='email');$('#chApp').classList.toggle('on',c==='in-app');
  $('#oSubject').parentElement.querySelector('#oSubject').style.display=(c==='in-app')?'none':'';
  $('#oSubject').previousElementSibling.style.display=(c==='in-app')?'none':'';}
async function genDraft(id){
  const btn=event.target;btn.disabled=true;btn.innerHTML='Drafting <span class="spin"></span>';
  const d=await jpost(`/api/leads/${id}/draft`,{clinic:CLINIC,specialty:SPECIALTY,channel:CHAN});
  $('#oSubject').value=d.subject||'';$('#oBody').value=d.body||'';
  btn.disabled=false;btn.innerHTML='&#10024; Draft with EggWise Agent';
}
async function sendOutreach(id){
  const body=$('#oBody').value.trim();if(!body){toast('Draft a message first');return;}
  const b=$('#sendBtn');b.disabled=true;
  await jpost('/api/outreach/send',{lead_id:id,channel:CHAN,subject:$('#oSubject').value,body});
  b.disabled=false;closeDrawer();toast('Sent. Saved to Outbox.');
}
function openDrawer(){$('#drawer').classList.add('on');$('#scrim').classList.add('on');}
function closeDrawer(){$('#drawer').classList.remove('on');$('#scrim').classList.remove('on');}

/* SCHEDULE */
function renderSchedule(){
  $('#main').innerHTML=`<h1>Schedule</h1><p class="sub">Create follow-up invites and medication reminders. Each returns a real add-to-calendar link.</p>
  <div class="panel"><h3>Follow-up appointment</h3>
    <div class="field"><label>Patient id</label><input id="sPid" value="pt-jasmine"></div>
    <div class="row2"><div class="field"><label>Date</label><input id="sDate" type="date" value="2026-06-15"></div>
    <div class="field"><label>Time</label><input id="sTime" type="time" value="09:00"></div></div>
    <div class="field"><label>Reason</label><input id="sReason" value="cycle review"></div>
    <button class="btn teal" onclick="doSchedule()">Create invite</button>
    <div id="sOut"></div></div>
  <div class="panel"><h3>Medication reminder</h3>
    <div class="field"><label>Patient id</label><input id="rPid" value="pt-jasmine"></div>
    <div class="row2"><div class="field"><label>Medication</label><input id="rMed" value="evening medication"></div>
    <div class="field"><label>Time</label><input id="rTime" type="time" value="20:00"></div></div>
    <div class="field"><label>Repeat for (days)</label><input id="rDays" type="number" value="14"></div>
    <button class="btn teal" onclick="doReminder()">Create reminder</button>
    <div id="rOut"></div></div>`;
}
async function doSchedule(){
  const r=await jpost('/api/schedule',{patient_id:$('#sPid').value,date:$('#sDate').value,time:$('#sTime').value,reason:$('#sReason').value});
  $('#sOut').innerHTML = r.error?`<div class="result">${esc(r.error)}</div>`
    :`<div class="result"><b>${esc(r.title)}</b><br>${esc(r.start)} (${esc(r.timezone)})<br><br>
       <a class="btn gold" href="${r.google_calendar_link}" target="_blank">Add to Google Calendar</a>
       <div class="muted" style="margin-top:8px">${esc(r.note)}</div></div>`;
}
async function doReminder(){
  const r=await jpost('/api/reminder',{patient_id:$('#rPid').value,medication:$('#rMed').value,time:$('#rTime').value,days:$('#rDays').value});
  $('#rOut').innerHTML = r.error?`<div class="result">${esc(r.error)}</div>`
    :`<div class="result"><b>${esc(r.medication)}</b> &middot; ${esc(r.frequency)}<br><br>
       <a class="btn gold" href="${r.google_calendar_link}" target="_blank">Add reminder to Google Calendar</a>
       <div class="muted" style="margin-top:8px">${esc(r.note)}</div></div>`;
}

/* PATIENTS */
async function renderPatients(){
  $('#main').innerHTML=`<h1>Patients</h1><p class="sub">Open a patient for an adherence and symptom report with clinician-review flags.</p><ul class="plist" id="pList"><li>Loading <span class="spin"></span></li></ul>`;
  const data=await api('/api/patients');
  $('#pList').innerHTML='';
  data.patients.forEach(p=>{const li=document.createElement('li');li.onclick=()=>showReport(p.id);
    li.innerHTML=`<span><b>${esc(p.name)}</b> <span class="muted">${esc(p.id)}</span></span><span class="muted">View report &rsaquo;</span>`;$('#pList').appendChild(li);});
}
async function showReport(id){
  $('#main').innerHTML=`<button class="btn ghost" onclick="renderPatients()">&lsaquo; Back</button><div id="rep" style="margin-top:14px"><div class="empty">Generating report <span class="spin"></span></div></div>`;
  const r=await jpost(`/api/patients/${id}/report`,{});
  if(r.error){$('#rep').innerHTML=`<div class="result">${esc(r.error)}</div>`;return;}
  $('#rep').innerHTML=`<div class="report">${mdToHtml(r.report_markdown)}</div>`;
}

/* OUTBOX */
async function renderOutbox(){
  $('#main').innerHTML=`<h1>Outbox</h1><p class="sub">One-click sends are recorded here (demo). Nothing actually leaves the system.</p><ul class="obx" id="obx"></ul>`;
  const data=await api('/api/outbox');
  const o=$('#obx');
  if(!data.messages.length){o.innerHTML='<div class="empty">No messages yet. Draft and send outreach from the Leads tab.</div>';return;}
  data.messages.forEach(m=>{const li=document.createElement('li');
    li.innerHTML=`<div class="oh"><span><span class="chan">${esc(m.channel)}</span> &nbsp;to ${esc(m.to)}</span><span>${esc(m.sent_at)}</span></div>
      ${m.subject?`<div class="osub">${esc(m.subject)}</div>`:''}<div class="obody">${esc(m.body)}</div>`;o.appendChild(li);});
}

/* COMMAND BAR */
$('#cmdForm').addEventListener('submit',async e=>{
  e.preventDefault();const inp=$('#cmdInput');const text=inp.value.trim();if(!text)return;inp.value='';
  const feed=$('#feed');feed.classList.add('on');
  addTurn('me','You',text);
  const t=addTurn('agent','EggWise Agent','<span class="spin"></span>');
  const r=await jpost('/api/agent',{message:text});
  if(r.error){t.querySelector('.body').innerHTML=`<span class="muted">Agent unavailable in this environment (${esc(r.error)}). The console actions above still work.</span>`;}
  else{const chip=r.route?`<span class="chip">${esc(r.route.replace('_agent',''))}</span>`:'';
    const tl=(r.tools&&r.tools.length)?`<span class="chip">${r.tools.map(esc).join(', ')}</span>`:'';
    t.querySelector('.who').innerHTML='EggWise Agent'+chip+tl;
    t.querySelector('.body').innerHTML=esc(r.text||'(no response)').replace(/\n/g,'<br>');}
  feed.scrollTop=feed.scrollHeight;
});
function addTurn(cls,who,html){const feed=$('#feed');const d=document.createElement('div');d.className='turn '+cls;
  d.innerHTML=`<div class="who">${who}</div><div class="body">${html}</div>`;feed.appendChild(d);feed.scrollTop=feed.scrollHeight;return d;}

/* tiny markdown for reports */
function mdToHtml(md){
  const lines=(md||'').split('\n');let out='';let inList=false;
  const flush=()=>{if(inList){out+='</ul>';inList=false;}};
  for(let ln of lines){
    if(/^# /.test(ln)){flush();out+='<h1>'+inline(ln.slice(2))+'</h1>';}
    else if(/^## /.test(ln)){flush();out+='<h2>'+inline(ln.slice(3))+'</h2>';}
    else if(/^- /.test(ln)){if(!inList){out+='<ul>';inList=true;}out+='<li>'+inline(ln.slice(2))+'</li>';}
    else if(/^> /.test(ln)){flush();out+='<blockquote>'+inline(ln.slice(2))+'</blockquote>';}
    else if(/^\*.*\*$/.test(ln.trim())){flush();out+='<p><em>'+inline(ln.trim().replace(/^\*|\*$/g,''))+'</em></p>';}
    else if(ln.trim()===''){flush();}
    else{flush();out+='<p>'+inline(ln)+'</p>';}
  }
  flush();return out;
}
function inline(s){return esc(s).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');}

renderLeads();
</script>
</body>
</html>""".replace("__LOGO__", LOGO_SVG)
