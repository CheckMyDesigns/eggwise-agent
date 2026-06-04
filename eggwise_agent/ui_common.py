"""Shared UI shell for the EggWise consoles (clinic + patient).

One dark theme matching EggWise.app (navy, dusty-teal, soft-gold, Poppins + Nunito
Sans, egg logo), one responsive app shell (top bar, desktop sidebar, mobile bottom
tab bar, command bar). Each page embeds FONT_LINK + BASE_CSS and adds its own views.
"""
from __future__ import annotations

LOGO_SVG = (
    '<svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg" width="30" height="30" aria-hidden="true">'
    '<path d="M50 20C25 20 10 55 10 80C10 105 27.9086 120 50 120C72.0914 120 90 105 90 80C90 55 75 20 50 20Z" fill="#74A0A0"/>'
    '<path d="M50 68L55.5 74.5L61.5 65.5L67 72" stroke="#FFD700" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
    "</svg>"
)

ATTRIB = '<div class="attrib">&#129666; Information from <b>EggWise: AI Fertility Tracker</b></div>'

FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800;900'
    '&family=Nunito+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">'
)

# Shared theme + responsive app shell. Page-specific rules live in each page.
BASE_CSS = r"""
  :root{
    --bg:#0A0F1C; --bg2:#0F1626; --card:#111827; --card2:#0D1422; --raised:#16203A;
    --ink:#EEE4D2; --ink-soft:#C7CAD1; --ink-mute:#9CA3AF;
    --teal:#74A0A0; --teal-lt:#8FBDBB; --teal-deep:#0D9488; --teal-tint:rgba(116,160,160,.14);
    --gold:#FFD700; --peach:#FFCBA4; --ok:#4ECDC4; --warn:#E9B949; --risk:#E8836B;
    --line:rgba(116,160,160,.16); --line2:rgba(116,160,160,.30);
    --shadow:0 18px 42px -22px rgba(0,0,0,.75);
  }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%}
  body{font-family:'Nunito Sans',system-ui,sans-serif;color:var(--ink);background:var(--bg);
    -webkit-font-smoothing:antialiased;display:flex;flex-direction:column;height:100vh;overflow:hidden}
  a{color:var(--teal-lt);text-decoration:none}
  /* top bar */
  header{display:flex;align-items:center;gap:12px;padding:12px 18px;background:var(--card);border-bottom:1px solid var(--line);flex-wrap:wrap}
  .brand{display:flex;align-items:center;gap:9px;font-family:'Poppins',sans-serif;font-weight:700;font-size:19px}
  .brand .dot{color:var(--gold)}
  .tag{font-size:10px;letter-spacing:.24em;text-transform:uppercase;color:var(--teal-lt);font-weight:700;border-left:1px solid var(--line2);padding-left:12px;margin-left:2px}
  header .spacer{flex:1}
  .switch{display:inline-flex;border:1px solid var(--line2);border-radius:10px;overflow:hidden}
  .switch a{padding:7px 13px;font-size:12px;font-weight:700;color:var(--ink-mute)}
  .switch a.on{background:linear-gradient(135deg,var(--teal),var(--teal-deep));color:#fff}
  .who{font-size:13px;color:var(--ink-mute)} .who b{color:var(--ink)}
  .logout{font-size:12px;color:var(--ink-mute);border:1px solid var(--line2);padding:6px 11px;border-radius:9px}
  .logout:hover{color:var(--ink);border-color:var(--teal)}
  /* shell */
  .shell{flex:1;display:grid;grid-template-columns:210px 1fr;min-height:0}
  .side{background:var(--card);border-right:1px solid var(--line);padding:14px 12px;display:flex;flex-direction:column;gap:3px}
  .navbtn{display:flex;align-items:center;gap:10px;width:100%;text-align:left;border:0;background:transparent;font:inherit;font-size:14px;font-weight:600;color:var(--ink-mute);padding:10px 12px;border-radius:11px;cursor:pointer;transition:.12s}
  .navbtn .ico{width:18px;text-align:center;opacity:.85}
  .navbtn:hover{background:var(--teal-tint);color:var(--ink)}
  .navbtn.active{background:linear-gradient(135deg,var(--teal),var(--teal-deep));color:#fff;box-shadow:0 8px 20px -10px rgba(116,160,160,.6)}
  .navbtn.ask{border:1px solid rgba(255,215,0,.55)}
  .navbtn.ask:not(.active){color:var(--gold)}
  .ntitle{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--ink-mute);opacity:.7;padding:6px 12px 4px}
  .work{display:flex;flex-direction:column;min-height:0}
  main{flex:1;overflow:auto;padding:24px 26px}
  h1{font-family:'Poppins',sans-serif;font-weight:700;font-size:23px;margin:0 0 3px}
  .sub{color:var(--ink-mute);font-size:13px;margin:0 0 18px;max-width:680px}
  /* bottom tab bar (mobile) */
  .tabbar{display:none}
  /* buttons */
  .btn{font:inherit;font-weight:700;font-size:13px;border:0;border-radius:11px;cursor:pointer;padding:10px 15px;transition:.12s}
  .btn:active{transform:scale(.97)}
  .btn.teal{background:linear-gradient(135deg,var(--teal),var(--teal-deep));color:#fff;box-shadow:0 10px 22px -12px rgba(116,160,160,.7)}
  .btn.teal:hover{filter:brightness(1.08)}
  .btn.gold{background:linear-gradient(135deg,var(--gold),var(--peach));color:#241a02}.btn.gold:hover{filter:brightness(1.06)}
  .btn.ghost{background:transparent;border:1px solid var(--line2);color:var(--ink-soft)}.btn.ghost:hover{border-color:var(--teal);color:var(--ink)}
  .btn.block{display:block;width:100%}
  .btn:disabled{opacity:.5;cursor:default}
  /* fields */
  .field{margin-bottom:11px}
  .field label{display:block;font-size:12px;color:var(--ink-mute);margin-bottom:4px}
  .field input,.field select{width:100%;font:inherit;font-size:13px;padding:10px 12px;border:1px solid var(--line2);border-radius:10px;background:var(--card2);color:var(--ink)}
  .field input:focus,.field select:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 3px var(--teal-tint)}
  .row2{display:grid;grid-template-columns:1fr 1fr;gap:11px}
  /* badges */
  .badge{font-size:10px;font-weight:700;padding:3px 9px;border-radius:20px;display:inline-block}
  .badge.cons{background:rgba(78,205,196,.15);color:var(--ok)}
  .badge.pend{background:rgba(255,203,164,.14);color:var(--peach)}
  .badge.high{background:rgba(232,131,107,.16);color:var(--risk)}
  .badge.watch{background:rgba(233,185,73,.16);color:var(--warn)}
  .badge.stable{background:rgba(78,205,196,.13);color:var(--ok)}
  .muted{color:var(--ink-mute);font-size:11.5px}
  .attrib{display:flex;align-items:center;gap:6px;color:var(--ink-mute);font-size:11.5px;margin:18px 0 4px}
  .attrib b{color:var(--teal-lt);font-weight:700}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px;box-shadow:var(--shadow);max-width:580px;margin-bottom:16px}
  .panel h3{margin:0 0 12px;font-family:'Poppins',sans-serif;font-weight:700;font-size:16px}
  .result{margin-top:14px;padding:13px 15px;border:1px solid var(--line);border-radius:12px;background:var(--teal-tint);font-size:13px}
  .empty{color:var(--ink-mute);font-size:13px;padding:18px 0}
  /* command bar */
  .cmd{border-top:1px solid var(--line);background:var(--card);padding:11px 16px}
  .cmd .feed{max-height:0;overflow:auto;transition:max-height .2s}
  .cmd .feed.on{max-height:230px;margin-bottom:10px}
  .turn{font-size:13px;margin:8px 0;line-height:1.5}
  .turn .who2{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-mute);font-weight:700}
  .turn.me .who2{color:var(--gold)}
  .chip{display:inline-block;font-size:10px;font-weight:700;background:var(--teal-tint);color:var(--teal-lt);padding:2px 8px;border-radius:20px;margin-left:7px}
  .cmd form{display:flex;gap:10px;align-items:center}
  .cmd input{flex:1;font:inherit;font-size:14px;padding:12px 15px;border:1px solid var(--line2);border-radius:12px;background:var(--card2);color:var(--ink)}
  .cmd input::placeholder{color:var(--ink-mute)}
  .cmd input:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 3px var(--teal-tint)}
  /* chat (shared by clinic Ask EggWise + patient Chat) */
  .chatwrap{display:flex;flex-direction:column;min-height:calc(100dvh - 175px)}
  .chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
  .chip2{font:inherit;font-size:12px;font-weight:700;color:var(--teal-lt);background:var(--teal-tint);border:0;border-radius:20px;padding:7px 12px;cursor:pointer;text-align:left}
  .chip2:hover{filter:brightness(1.12)}
  .tx{flex:1;display:flex;flex-direction:column;gap:10px;padding-bottom:12px}
  .msg{max-width:88%;padding:11px 15px;border-radius:16px;font-size:14px;line-height:1.55}
  .msg.me{align-self:flex-end;background:linear-gradient(135deg,var(--teal),var(--teal-deep));color:#fff;border-bottom-right-radius:5px;white-space:pre-wrap}
  .msg.bot{align-self:flex-start;background:var(--card);border:1px solid var(--line);border-bottom-left-radius:5px;max-width:94%}
  .msg.bot h2{font-family:'Poppins',sans-serif;font-size:14px;color:var(--teal-lt);margin:10px 0 5px}
  .msg.bot h3{font-family:'Poppins',sans-serif;font-size:13px;color:var(--ink);margin:8px 0 4px}
  .msg.bot p{margin:6px 0}.msg.bot ul{margin:6px 0;padding-left:20px}.msg.bot li{margin:3px 0}
  .msg.bot hr{border:0;border-top:1px solid var(--line2);margin:12px 0}.msg.bot b{color:var(--ink)}
  .chatin{position:sticky;bottom:0;display:flex;gap:10px;padding:10px 0 4px;background:var(--bg)}
  .chatin input{flex:1;font:inherit;font-size:15px;padding:12px 15px;border:1px solid var(--line2);border-radius:12px;background:var(--card2);color:var(--ink)}
  .chatin input:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 3px var(--teal-tint)}
  /* toast + spinner */
  #toast{position:fixed;bottom:96px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--raised);color:var(--ink);padding:11px 20px;border-radius:12px;font-size:13px;opacity:0;pointer-events:none;transition:all .25s;z-index:90;box-shadow:var(--shadow);border:1px solid var(--line2)}
  #toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
  .spin{display:inline-block;width:13px;height:13px;border:2px solid var(--teal-tint);border-top-color:var(--teal-lt);border-radius:50%;animation:sp .7s linear infinite;vertical-align:-2px}
  @keyframes sp{to{transform:rotate(360deg)}}
  /* mobile: hide sidebar, show bottom tab bar like the EggWise app */
  @media (max-width:760px){
    header{padding:10px 14px}
    .tag{display:none}
    .who{display:none}
    .shell{grid-template-columns:1fr}
    .side{display:none}
    main{padding:16px 14px 20px}
    .row2{grid-template-columns:1fr}
    .cmd input{font-size:16px}
    .chatin input{font-size:16px}
    .chatwrap{min-height:calc(100dvh - 215px)}
    .tabbar{display:flex;overflow:hidden;align-items:stretch;background:var(--card);border-top:1px solid var(--line);padding:6px 2px 8px}
    .tabbar button{flex:1 1 0;min-width:0;display:flex;flex-direction:column;align-items:center;gap:2px;border:0;background:transparent;color:var(--ink-mute);font:inherit;font-size:9.5px;font-weight:700;padding:5px 2px;border-radius:10px;cursor:pointer;white-space:nowrap}
    .tabbar button .ico{font-size:17px}
    .tabbar button.active{color:var(--teal-lt)}
    .panel{max-width:none}
  }
"""
