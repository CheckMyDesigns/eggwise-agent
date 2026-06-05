"""EggWise Agent CLINIC front desk: branded UI + shared JSON API over the agent tools.

The clinic-facing screen. The agent is told it is assisting clinic staff. Beyond the
data views it includes an autonomous-messaging "Campaigns" flow: one click drafts a
personalized check-in for every at-risk patient (or outreach for every top lead), the
clinic reviews/edits, and sends them all, the work that used to need front-desk staff.
The patient view (patient.py) reuses this module's /api endpoints. Synthetic data only.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import calendar_tools, config, leads_data, outreach, patient_tools, tools
from .ui_common import ATTRIB, BASE_CSS, FONT_LINK, LOGO_SVG

CLINIC = config.CLINIC_NAME
router = APIRouter()

# --------------------------------------------------------------------------
# Shared JSON API
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
def api_draft(lead_id: str, channel: str = "email", specialty: str = ""):
    lead = leads_data.get_lead(lead_id)
    if not lead:
        return JSONResponse({"error": "lead not found"}, status_code=404)
    return outreach.draft_outreach(lead, clinic=CLINIC, specialty=specialty, channel=channel)


@router.post("/api/outreach/send")
async def api_send(request: Request):
    b = await request.json()
    return outreach.send_outreach(
        b.get("lead_id") or b.get("recipient_id", ""), b.get("channel", "email"),
        b.get("subject", ""), b.get("body", ""), b.get("to", ""),
    )


@router.post("/api/send_batch")
async def api_send_batch(request: Request):
    b = await request.json()
    items = b.get("items", [])
    for it in items:
        outreach.send_outreach(it.get("recipient_id", ""), it.get("channel", "email"),
                               it.get("subject", ""), it.get("body", ""), it.get("to", ""))
    return {"sent": len(items)}


@router.get("/api/outbox")
def api_outbox():
    return {"messages": outreach.list_outbox()}


@router.post("/api/outbox/approve")
async def api_outbox_approve(request: Request):
    b = await request.json()
    return outreach.approve_message(b["id"]) if b.get("id") else outreach.approve_all()


@router.post("/api/outbox/discard")
async def api_outbox_discard(request: Request):
    b = await request.json()
    return outreach.discard_message(b.get("id", ""))


@router.get("/api/patients")
def api_patients():
    return {"patients": tools.list_patients()}


@router.get("/api/triage")
def api_triage():
    return {"patients": tools.list_patients_with_risk()}


@router.post("/api/patients/{patient_id}/report")
def api_report(patient_id: str):
    return tools.generate_health_report(patient_id)


@router.post("/api/patients/{patient_id}/checkin_draft")
def api_checkin_draft(patient_id: str, channel: str = "in-app"):
    rep = tools.generate_health_report(patient_id)
    if "error" in rep:
        return rep
    d = outreach.draft_checkin(rep["name"], rep, CLINIC, channel)
    return {"recipient_id": patient_id, "name": rep["name"], **d}


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


@router.get("/api/info/topics")
def api_info_topics():
    return {"topics": tools._load("approved_content.json")}


@router.get("/api/info")
def api_info(topic: str = ""):
    return patient_tools.get_approved_info(topic)


@router.post("/api/checkin")
async def api_checkin(request: Request):
    b = await request.json()
    return patient_tools.log_daily_checkin(
        b.get("patient_id", ""), bool(b.get("meds_taken", True)),
        int(b.get("mood", 3)), b.get("note", ""),
    )


# Batch personalized messaging (the autonomous front desk).
@router.post("/api/campaign/checkins")
async def api_campaign_checkins(request: Request):
    b = await request.json()
    audience = b.get("audience", "at_risk")
    channel = b.get("channel", "in-app")
    rows = tools.list_patients_with_risk()
    if audience == "at_risk":
        rows = [r for r in rows if r["risk_level"] != "stable"]

    def one(r):
        rep = tools.generate_health_report(r["id"])
        d = outreach.draft_checkin(r["name"], rep, CLINIC, channel)
        return {"recipient_id": r["id"], "name": r["name"], "channel": channel,
                "subject": d["subject"], "body": d["body"], "chip": r["risk_level"]}

    items = list(await asyncio.gather(*[asyncio.to_thread(one, r) for r in rows])) if rows else []
    return {"items": items}


@router.post("/api/campaign/outreach")
async def api_campaign_outreach(request: Request):
    b = await request.json()
    count = int(b.get("count", 3))
    channel = b.get("channel", "email")
    spec = b.get("specialty", "")
    loc = b.get("location", "")
    ranked = leads_data.rank_leads(spec, loc)[:count]

    def one(lead_view):
        lead = leads_data.get_lead(lead_view["id"])
        d = outreach.draft_outreach(lead, clinic=CLINIC, specialty=spec, channel=channel)
        return {"recipient_id": lead_view["id"], "name": lead_view.get("display") or lead_view["alias"], "channel": channel,
                "subject": d["subject"], "body": d["body"], "chip": "fit " + str(lead_view["fit_score"])}

    items = list(await asyncio.gather(*[asyncio.to_thread(one, L) for L in ranked])) if ranked else []
    return {"items": items}


def _context_preamble(audience: str, patient_id: str = "", patient_name: str = "") -> str:
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
        f"(patients, daily logs, reports, triage, scheduling, check-ins). Default the clinic's "
        f"specialty and location from this context. Do not ask whether the user is a clinician or "
        f"a patient.\n\n"
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
    app.include_router(router)

    @app.get("/console", response_class=HTMLResponse)
    def console_page():
        return HTMLResponse(CONSOLE_HTML)


# --------------------------------------------------------------------------
# Clinic console page
# --------------------------------------------------------------------------

_CONSOLE_CSS = r"""
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
  .crow{display:flex;gap:9px;margin-top:13px;align-items:center;flex-wrap:wrap}
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
  /* campaigns */
  .cbar{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:16px}
  .cbar .field{margin:0}.cbar select{font:inherit;font-size:13px;padding:9px 12px;border:1px solid var(--line2);border-radius:10px;background:var(--card2);color:var(--ink)}
  .ccards{display:flex;flex-direction:column;gap:12px;max-width:720px}
  .ccard{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
  .ccard.sent{opacity:.5}
  .ccard .ch{display:flex;justify-content:space-between;align-items:center;gap:10px}
  .ccard .nm{font-family:'Poppins',sans-serif;font-weight:700}
  .ccard input,.ccard textarea{width:100%;font:inherit;font-size:13px;padding:9px 11px;border:1px solid var(--line2);border-radius:9px;background:var(--card2);color:var(--ink);margin-top:8px;resize:vertical}
  .ccard textarea{min-height:120px;line-height:1.5}
  .ccard:focus-within{border-color:var(--teal)}
  .cmodal{position:fixed;top:50%;left:50%;transform:translate(-50%,-46%);width:min(420px,92vw);background:var(--bg2);border:1px solid var(--line2);border-radius:16px;padding:20px 22px;box-shadow:var(--shadow);z-index:60;opacity:0;pointer-events:none;transition:opacity .18s,transform .18s}
  .cmodal.on{opacity:1;pointer-events:auto;transform:translate(-50%,-50%)}
  .cmtitle{font-family:'Poppins',sans-serif;font-weight:700;font-size:17px;margin-bottom:8px}
  .cmbody{font-size:13.5px;color:var(--ink-soft);line-height:1.5;margin-bottom:16px}
  .cmact{display:flex;gap:10px;justify-content:flex-end}
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
      <button class="navbtn ask active" data-view="ask"><span class="ico">&#128172;</span> Ask EggWise</button>
      <button class="navbtn" data-view="leads"><span class="ico">&#9733;</span> Leads</button>
      <button class="navbtn" data-view="patients"><span class="ico">&#129658;</span> Patients</button>
      <button class="navbtn" data-view="campaigns"><span class="ico">&#128640;</span> Campaigns</button>
      <button class="navbtn" data-view="schedule"><span class="ico">&#128197;</span> Schedule</button>
      <button class="navbtn" data-view="outbox"><span class="ico">&#9993;</span> Outbox</button>
      <div class="ntitle" style="margin-top:14px">Reference</div>
      <button class="navbtn" onclick="window.open('/dev-ui/','_blank')"><span class="ico">&#9881;</span> ADK console</button>
    </nav>
    <div class="work"><main id="main"></main></div>
  </div>

  <nav class="tabbar">
    <button class="navbtn ask active" data-view="ask"><span class="ico">&#128172;</span>Ask</button>
    <button class="navbtn" data-view="leads"><span class="ico">&#9733;</span>Leads</button>
    <button class="navbtn" data-view="patients"><span class="ico">&#129658;</span>Patients</button>
    <button class="navbtn" data-view="campaigns"><span class="ico">&#128640;</span>Send</button>
    <button class="navbtn" data-view="schedule"><span class="ico">&#128197;</span>Schedule</button>
    <button class="navbtn" data-view="outbox"><span class="ico">&#9993;</span>Outbox</button>
  </nav>

  <div class="scrim" id="scrim" onclick="closeDrawer()"></div>
  <div class="drawer" id="drawer"><div class="dh"><div id="dTitle" style="font-family:'Poppins',sans-serif;font-weight:700;font-size:18px"></div><button class="x" onclick="closeDrawer()">&times;</button></div><div class="db" id="dBody"></div></div>
  <div id="toast"></div>
  <div class="scrim" id="cscrim" onclick="closeConfirm()"></div>
  <div class="cmodal" id="cmodal"><div class="cmtitle" id="cmTitle"></div><div class="cmbody" id="cmBody"></div><div class="cmact"><button class="btn ghost" onclick="closeConfirm()">Cancel</button><button class="btn teal" id="cmOk">Confirm &amp; send</button></div></div>

<script>
const $=(s,r=document)=>r.querySelector(s);
const api=async(u,o)=>{const r=await fetch(u,o);return r.json();};
const jpost=(u,b)=>api(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});
const ATTRIB=`__ATTRIB__`;
let CLINIC='__CLINIC__', SPECIALTY='', LOCATION='', CHAT=[];
const SUGGEST=["Who is at risk right now?","Find egg-freezing patients in Las Vegas","Draft a check-in for pt-sarah","Draft outreach to the top prospect"];
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('on');setTimeout(()=>t.classList.remove('on'),2600);}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function scoreClass(n){return n>=85?'s-hi':n>=70?'s-mid':'s-lo';}
function setNav(v){document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===v));}
function go(v){setNav(v);render(v);}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>go(b.dataset.view));
function render(v){({leads:renderLeads,patients:renderPatients,campaigns:renderCampaigns,schedule:renderSchedule,outbox:renderOutbox,ask:renderAsk}[v]||renderLeads)();}

/* LEADS */
async function renderLeads(){
  $('#main').innerHTML=`<h1>Prospective patients</h1><p class="sub">Lead generation for ${esc(CLINIC)}. Ranked by fit. Click a patient for detail and one-click outreach.</p>
   <div class="filters"><div class="frow">
     <input id="fSpec" placeholder="Clinic specialty (e.g. IVF, egg freezing)" value="${esc(SPECIALTY)}" onkeydown="if(event.key==='Enter')applyFilters()">
     <input id="fLoc" placeholder="Clinic location (e.g. Las Vegas, NV)" value="${esc(LOCATION)}" onkeydown="if(event.key==='Enter')applyFilters()">
   </div><button class="btn teal" onclick="applyFilters()">Re-rank</button></div>
   <div class="grid" id="leadGrid"><div class="empty">Loading leads <span class="spin"></span></div></div><div id="att"></div>`;
  const data=await api(`/api/leads?specialty=${encodeURIComponent(SPECIALTY)}&location=${encodeURIComponent(LOCATION)}`);
  CLINIC=data.clinic||CLINIC;const g=$('#leadGrid');g.innerHTML='';
  data.leads.forEach(L=>{const cons=L.consented_to_share;const el=document.createElement('div');el.className='lead';el.onclick=()=>openLead(L.id);
    el.innerHTML=`<div class="top"><div><div class="alias">${esc(L.display||L.alias)}</div><div class="meta">${L.age}, ${esc(L.location)}</div></div>
      <div class="score ${scoreClass(L.fit_score)}">${L.fit_score}<small>fit</small></div></div>
      <span class="goal">${esc(L.goal)}</span><div class="reason">${esc(L.fit_reason)}</div>
      <span class="badge ${cons?'cons':'pend'}">${cons?'&#10003; Consented to share':'Consent pending'}</span>`;g.appendChild(el);});
  $('#att').innerHTML=ATTRIB;
}
function applyFilters(){SPECIALTY=$('#fSpec').value.trim();LOCATION=$('#fLoc').value.trim();renderLeads();}

let CHAN='email';
async function openLead(id){
  const d=await api(`/api/leads/${id}`);$('#dTitle').textContent=(d.display||d.alias)+' · '+d.goal;CHAN='email';
  const clin=d.clinical_visible?`<div class="clin"><h4>Clinical profile (consented)</h4>${Object.entries(d.clinical).map(([k,v])=>`<div class="kv"><b>${esc(k.toUpperCase())}</b>: ${esc(String(v))}</div>`).join('')}</div>`:`<div class="clin locked"><h4>Clinical profile</h4><div class="kv">${esc(d.clinical_note||'Locked')}</div></div>`;
  $('#dBody').innerHTML=`<div class="kv"><b>Age</b>: ${d.age}</div><div class="kv"><b>Location</b>: ${esc(d.location)}</div><div class="kv"><b>Goal</b>: ${esc(d.goal)}</div><div class="kv"><b>Wellness Score</b>: ${d.wellness_score}</div><div class="kv"><b>Signals</b>: ${esc(d.signals||'')}</div>${clin}
    <div class="compose"><div class="seg"><button id="chEmail" class="on" onclick="setChan('email')">Email</button><button id="chApp" onclick="setChan('in-app')">In-app message</button></div>
      <button class="btn gold" onclick="genDraft('${d.id}')">&#10024; Draft with EggWise Agent</button>
      <label id="lSub">Subject</label><input id="oSubject" placeholder="(generated)"><label>Message</label><textarea id="oBody" placeholder="Click Draft to generate a personalized, consent-safe message."></textarea>
      <div class="crow"><button class="btn teal" id="sendBtn" onclick="sendOutreach('${d.id}')">Send</button><span class="muted">Records to the Outbox. No PHI in outreach.</span></div></div>`;
  openDrawer();
}
function setChan(c){CHAN=c;$('#chEmail').classList.toggle('on',c==='email');$('#chApp').classList.toggle('on',c==='in-app');const s=(c!=='in-app');$('#oSubject').style.display=s?'':'none';$('#lSub').style.display=s?'':'none';}
async function genDraft(id){const b=event.target;b.disabled=true;b.innerHTML='Drafting <span class="spin"></span>';const d=await api(`/api/leads/${id}/draft?channel=${CHAN}&specialty=${encodeURIComponent(SPECIALTY)}`,{method:'POST'});$('#oSubject').value=d.subject||'';$('#oBody').value=d.body||'';b.disabled=false;b.innerHTML='&#10024; Draft with EggWise Agent';}
async function sendOutreach(id){const body=$('#oBody').value.trim();if(!body){toast('Draft a message first');return;}const b=$('#sendBtn');b.disabled=true;await jpost('/api/outreach/send',{lead_id:id,channel:CHAN,subject:$('#oSubject').value,body});b.disabled=false;closeDrawer();toast('Sent. Saved to Outbox.');}
function openDrawer(){$('#drawer').classList.add('on');$('#scrim').classList.add('on');}
function closeDrawer(){$('#drawer').classList.remove('on');$('#scrim').classList.remove('on');}

/* PATIENTS (triage) */
async function renderPatients(){
  $('#main').innerHTML=`<h1>Patients</h1><p class="sub">Triage board: everyone ranked by risk from their daily logs. Open a patient for a report and a one-click check-in draft.</p><ul class="plist" id="pList"><li>Loading <span class="spin"></span></li></ul><div id="att"></div>`;
  const data=await api('/api/triage');$('#pList').innerHTML='';
  data.patients.forEach(p=>{const li=document.createElement('li');li.onclick=()=>showReport(p.id);
    li.innerHTML=`<div><b>${esc(p.name)}</b> <span class="muted">${esc(p.id)}</span><div class="pmeta">${Math.round(p.adherence_rate*100)}% adherence · ${p.doses_missed} missed · streak ${p.current_streak_days}d</div></div><span class="badge ${p.risk_level}">${p.risk_level==='high'?'At risk':p.risk_level==='watch'?'Watch':'Stable'}</span>`;$('#pList').appendChild(li);});
  $('#att').innerHTML=ATTRIB;
}
async function showReport(id){
  $('#main').innerHTML=`<button class="btn ghost" onclick="renderPatients()">&lsaquo; Back to triage</button><div id="rep" style="margin-top:14px"><div class="empty">Generating report <span class="spin"></span></div></div>`;
  const r=await jpost(`/api/patients/${id}/report`,{});
  if(r.error){$('#rep').innerHTML=`<div class="result">${esc(r.error)}</div>`;return;}
  $('#rep').innerHTML=`<div class="report">${mdToHtml(r.report_markdown)}</div>
    <div class="crow"><button class="btn gold" onclick="draftCheckin('${id}')">&#9993; Draft check-in for ${esc((r.name||'').split(' (')[0])}</button></div>
    <div id="ci"></div>${ATTRIB}`;
}
async function draftCheckin(id){
  const b=event.target;b.disabled=true;b.innerHTML='Drafting <span class="spin"></span>';
  const d=await api(`/api/patients/${id}/checkin_draft?channel=in-app`,{method:'POST'});b.disabled=false;b.innerHTML='&#9993; Re-draft check-in';
  if(d.error){$('#ci').innerHTML=`<div class="result">${esc(d.error)}</div>`;return;}
  $('#ci').innerHTML=`<div class="ccard"><div class="ch"><span class="nm">Check-in for ${esc(d.name)}</span><span class="chan">${esc(d.channel)}</span></div>
    <input id="ciSub" value="${esc(d.subject)}"><textarea id="ciBody">${esc(d.body)}</textarea>
    <div class="crow"><button class="btn teal" onclick="sendCheckin('${id}','${esc(d.channel)}')">Send</button><span class="muted">Requires clinician review. Records to Outbox.</span></div></div>`;
}
async function sendCheckin(id,channel){await jpost('/api/outreach/send',{recipient_id:id,channel:channel,subject:$('#ciSub').value,body:$('#ciBody').value});toast('Check-in sent to Outbox');$('#ci').innerHTML='';}

/* CAMPAIGNS (batch personalized messaging) */
function renderCampaigns(){
  $('#main').innerHTML=`<h1>Campaigns</h1><p class="sub">Draft personalized messages for many recipients at once, review and edit, then send them all. This is the front-desk work the agent does for you.</p>
   <div class="cbar">
     <div class="field"><label>Type</label><select id="cType" onchange="campaignType()"><option value="checkins">Patient check-ins</option><option value="outreach">Lead outreach</option></select></div>
     <div class="field" id="cAudWrap"><label>Audience</label><select id="cAud"><option value="at_risk">At-risk patients</option><option value="all">All patients</option></select></div>
     <div class="field"><label>Channel</label><select id="cChan"><option value="in-app">In-app message</option><option value="email">Email</option></select></div>
     <button class="btn gold" onclick="draftAll()">&#10024; Draft all</button>
   </div>
   <div id="cOut"></div>`;
}
function campaignType(){const t=$('#cType').value;const w=$('#cAudWrap');
  if(t==='outreach'){w.innerHTML=`<label>How many top leads</label><select id="cAud"><option>3</option><option>5</option><option>7</option></select>`;$('#cChan').value='email';}
  else{w.innerHTML=`<label>Audience</label><select id="cAud"><option value="at_risk">At-risk patients</option><option value="all">All patients</option></select>`;$('#cChan').value='in-app';}}
async function draftAll(){
  const t=$('#cType').value,chan=$('#cChan').value,aud=$('#cAud').value;
  $('#cOut').innerHTML=`<div class="empty">Drafting personalized messages <span class="spin"></span></div>`;
  let data;
  if(t==='outreach')data=await jpost('/api/campaign/outreach',{count:aud,channel:chan,specialty:SPECIALTY,location:LOCATION});
  else data=await jpost('/api/campaign/checkins',{audience:aud,channel:chan});
  const items=data.items||[];
  if(!items.length){$('#cOut').innerHTML='<div class="empty">No recipients matched.</div>';return;}
  window.CAMP=items;
  $('#cOut').innerHTML=`<div class="crow" style="margin-bottom:12px"><button class="btn teal" onclick="sendAll()">Send all (${items.length})</button><span class="muted">Each message is personalized. Review and edit before sending.</span></div>
    <div class="ccards" id="cc">${items.map((m,i)=>`<div class="ccard" id="cc${i}"><div class="ch"><span class="nm">${esc(m.name)}</span><span class="chan">${esc(m.channel)}${m.chip?' · '+esc(m.chip):''}</span></div>
      <input id="cs${i}" value="${esc(m.subject)}"><textarea id="cb${i}">${esc(m.body)}</textarea>
      <div class="crow"><button class="btn ghost" onclick="sendOne(${i})">Send</button></div></div>`).join('')}</div>${ATTRIB}`;
}
function collect(i){const m=window.CAMP[i];return {recipient_id:m.recipient_id,channel:m.channel,subject:$('#cs'+i).value,body:$('#cb'+i).value};}
async function sendOne(i){await jpost('/api/outreach/send',collect(i));$('#cc'+i).classList.add('sent');toast('Sent to Outbox');}
async function sendAll(){const items=window.CAMP.map((m,i)=>collect(i));await jpost('/api/send_batch',{items});document.querySelectorAll('.ccard').forEach(c=>c.classList.add('sent'));toast('Sent '+items.length+' to Outbox');}

/* SCHEDULE */
function renderSchedule(){
  $('#main').innerHTML=`<h1>Schedule</h1><p class="sub">Create follow-up invites and medication reminders. Each returns a real add-to-calendar link.</p>
  <div class="panel"><h3>Follow-up appointment</h3><div class="field"><label>Patient id</label><input id="sPid" value="pt-jasmine"></div>
    <div class="row2"><div class="field"><label>Date</label><input id="sDate" type="date" value="2026-06-15"></div><div class="field"><label>Time</label><input id="sTime" type="time" value="09:00"></div></div>
    <div class="field"><label>Reason</label><input id="sReason" value="cycle review"></div><button class="btn teal" onclick="doSchedule()">Create invite</button><div id="sOut"></div></div>
  <div class="panel"><h3>Medication reminder</h3><div class="field"><label>Patient id</label><input id="rPid" value="pt-jasmine"></div>
    <div class="row2"><div class="field"><label>Medication</label><input id="rMed" value="evening medication"></div><div class="field"><label>Time</label><input id="rTime" type="time" value="20:00"></div></div>
    <div class="field"><label>Repeat for (days)</label><input id="rDays" type="number" value="14"></div><button class="btn teal" onclick="doReminder()">Create reminder</button><div id="rOut"></div></div>`;
}
async function doSchedule(){const r=await jpost('/api/schedule',{patient_id:$('#sPid').value,date:$('#sDate').value,time:$('#sTime').value,reason:$('#sReason').value});$('#sOut').innerHTML=r.error?`<div class="result">${esc(r.error)}</div>`:`<div class="result"><b>${esc(r.title)}</b><br>${esc(r.start)} (${esc(r.timezone)})<br><br><a class="btn gold" href="${r.google_calendar_link}" target="_blank">Add to Google Calendar</a></div>`;}
async function doReminder(){const r=await jpost('/api/reminder',{patient_id:$('#rPid').value,medication:$('#rMed').value,time:$('#rTime').value,days:$('#rDays').value});$('#rOut').innerHTML=r.error?`<div class="result">${esc(r.error)}</div>`:`<div class="result"><b>${esc(r.medication)}</b> · ${esc(r.frequency)}<br><br><a class="btn gold" href="${r.google_calendar_link}" target="_blank">Add reminder to Google Calendar</a></div>`;}

/* OUTBOX */
async function renderOutbox(){
  $('#main').innerHTML=`<h1>Outbox</h1><p class="sub">Agent-drafted messages wait here as Queued for review. You confirm and send each one (or all at once), or discard it. Nothing leaves the system in this demo.</p><div id="obtop"></div><ul class="obx" id="obx"></ul>`;
  const data=await api('/api/outbox');const o=$('#obx');const msgs=data.messages;
  const nq=msgs.filter(m=>m.status==='queued_for_review').length;
  $('#obtop').innerHTML=nq?`<div class="crow" style="margin-bottom:12px"><button class="btn teal" onclick="askConfirm('Send all queued messages?','You are about to send ${nq} agent-drafted messages to their recipients.','Confirm & send all',doApproveAll)">Confirm & send all (${nq})</button><span class="muted">Drafted by the agent, awaiting your review.</span></div>`:'';
  if(!msgs.length){o.innerHTML='<div class="empty">No messages yet. Use Ask EggWise, Leads, a patient check-in, or Campaigns.</div>';return;}
  msgs.forEach(m=>{const li=document.createElement('li');const isq=m.status==='queued_for_review';
    const st=isq?'<span class="badge watch">Queued for review</span>':'<span class="badge stable">Sent &#10003;</span>';
    const act=isq?`<div class="crow" style="margin-top:9px"><button class="btn teal" onclick="askConfirm('Send this message?','The agent drafted this. Confirming records it as sent to ${esc(m.to)}.','Confirm & send',()=>doApprove('${m.id}'))">Confirm & send</button><button class="btn ghost" onclick="askConfirm('Discard this draft?','This removes the queued draft without sending it.','Discard',()=>doDiscard('${m.id}'))">Discard</button></div>`:'';
    li.innerHTML=`<div class="oh"><span><span class="chan">${esc(m.channel)}</span> &nbsp;to ${esc(m.to)}</span><span>${st} &nbsp; ${esc(m.sent_at)}</span></div>${m.subject?`<div class="osub">${esc(m.subject)}</div>`:''}<div class="obody">${esc(m.body)}</div>${act}`;o.appendChild(li);});
}
let _cmCb=null;
function askConfirm(title,body,ok,cb){_cmCb=cb;$('#cmTitle').textContent=title;$('#cmBody').textContent=body;$('#cmOk').textContent=ok;$('#cscrim').classList.add('on');$('#cmodal').classList.add('on');}
function closeConfirm(){$('#cscrim').classList.remove('on');$('#cmodal').classList.remove('on');_cmCb=null;}
$('#cmOk').onclick=()=>{const cb=_cmCb;closeConfirm();if(cb)cb();};
async function doApprove(id){await jpost('/api/outbox/approve',{id});toast('Confirmed and sent');renderOutbox();}
async function doApproveAll(){await jpost('/api/outbox/approve',{});toast('All confirmed and sent');renderOutbox();}
async function doDiscard(id){await jpost('/api/outbox/discard',{id});toast('Draft discarded');renderOutbox();}

/* ASK EGGWISE (chat) */
function renderAsk(){
  $('#main').innerHTML=`<div class="chatwrap"><div class="chips">${SUGGEST.map(s=>`<button class="chip2" data-q="${esc(s)}" onclick="ask(this.dataset.q)">${esc(s)}</button>`).join('')}</div>
    <div class="tx" id="tx"></div><form class="chatin" id="chatForm"><input id="ci2" placeholder="Ask the EggWise Agent to do anything..." autocomplete="off"><button class="btn teal" type="submit">Send</button></form></div>`;
  if(!CHAT.length)CHAT.push({role:'bot',html:"Hi, I'm the EggWise Agent for "+esc(CLINIC)+". I can find and rank leads, draft outreach, triage patients, draft check-ins, and schedule. What would you like to do?"});
  drawChat();$('#chatForm').addEventListener('submit',e=>{e.preventDefault();const v=$('#ci2').value.trim();if(v){$('#ci2').value='';ask(v);}});$('#ci2').focus();
}
function drawChat(){const tx=$('#tx');if(!tx)return;tx.innerHTML=CHAT.map(m=>`<div class="msg ${m.role==='me'?'me':'bot'}">${m.role==='me'?esc(m.html):m.html}</div>`).join('');$('#main').scrollTop=$('#main').scrollHeight;}
async function ask(text){
  if(!$('#tx'))go('ask');
  CHAT.push({role:'me',html:text});const idx=CHAT.push({role:'bot',html:'<span class="spin"></span>'})-1;drawChat();
  const r=await jpost('/api/agent',{message:text,audience:'clinic'});
  CHAT[idx].html=r.error?`<span class="muted">Agent unavailable here (${esc(r.error)}). The console actions still work.</span>`:mdToHtml(r.text||'(no response)');
  drawChat();
}

/* markdown -> cards */
function mdToHtml(md){const lines=(md||'').split('\n');let out='';let inList=false;const flush=()=>{if(inList){out+='</ul>';inList=false;}};
  for(let raw of lines){const ln=raw.replace(/\s+$/,'');const t=ln.trim();
    if(/^(\-\-\-|\*\*\*|___)$/.test(t)){flush();out+='<hr>';}
    else if(/^### /.test(t)){flush();out+='<h3>'+inl(t.slice(4))+'</h3>';}
    else if(/^## /.test(t)){flush();out+='<h2>'+inl(t.slice(3))+'</h2>';}
    else if(/^# /.test(t)){flush();out+='<h2>'+inl(t.slice(2))+'</h2>';}
    else if(/^[-*] /.test(t)){if(!inList){out+='<ul>';inList=true;}out+='<li>'+inl(t.slice(2))+'</li>';}
    else if(/^> /.test(t)){flush();out+='<blockquote>'+inl(t.slice(2))+'</blockquote>';}
    else if(t===''){flush();}
    else{flush();out+='<p>'+inl(ln)+'</p>';}}
  flush();return out;}
function inl(s){return esc(s).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');}

renderAsk();
</script>
</body>
</html>""".replace("__FONT__", FONT_LINK).replace("__BASE__", BASE_CSS)
   .replace("__CONSOLE__", _CONSOLE_CSS).replace("__LOGO__", LOGO_SVG)
   .replace("__CLINIC__", CLINIC).replace("__ATTRIB__", ATTRIB))
