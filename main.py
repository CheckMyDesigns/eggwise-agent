"""Cloud Run / local entrypoint for EggWise Agent, with a branded login gate.

Wraps the ADK FastAPI app, serves a styled /login page (EggWise brand: Fraunces +
Inter, warm palette, egg logo), and protects every other route behind a signed
cookie. Set DEMO_PASS to require login (DEMO_USER defaults to "eggwise").
"""
import hashlib
import hmac
import os

import uvicorn
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from google.adk.cli.fast_api import get_fast_api_app
from starlette.middleware.base import BaseHTTPMiddleware

from eggwise_agent import console, patient

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_USER = os.environ.get("DEMO_USER", "eggwise")
DEMO_PASS = os.environ.get("DEMO_PASS", "")
_SECRET = (os.environ.get("DEMO_SECRET") or ("eggwise-secret-" + DEMO_PASS)).encode()
TOKEN = hmac.new(_SECRET, DEMO_USER.encode(), hashlib.sha256).hexdigest()
COOKIE = "eggwise_auth"

app = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    web=True,
    session_service_uri="memory://",
    use_local_storage=False,
)

# Branded clinic front-desk console + patient companion view + shared JSON API.
console.register_console(app)
patient.register_patient(app)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# EggWise egg mark (from the app's eggwise-logo-premium.svg): sage egg + gold check + sparkles.
LOGO_SVG = (
    '<svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg" width="56" height="56" aria-hidden="true">'
    '<path d="M50 20C25 20 10 55 10 80C10 105 27.9086 120 50 120C72.0914 120 90 105 90 80C90 55 75 20 50 20Z" fill="#74A0A0"/>'
    '<path d="M50 68L55.5 74.5L61.5 65.5L67 72" stroke="#FFD700" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M99.813 15.904L99 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L92.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L99 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L105.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM108.259 8.715L108 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L104.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L108 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L111.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" fill="#FFD700"/>'
    "</svg>"
)

LOGIN_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EggWise Agent &mdash; Sign in</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&family=Nunito+Sans:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#0A0F1C; --ink:#EEE4D2; --muted:#9CA3AF;
    --teal:#74A0A0; --teal-bright:#8FBDBB;
    --gold:#FFD700; --gold-bright:#FFCBA4;
  }
  *{ box-sizing:border-box; }
  html,body{ height:100%; }
  body{
    margin:0; color:var(--ink);
    font-family:'Nunito Sans',ui-sans-serif,system-ui,"Segoe UI",sans-serif;
    -webkit-font-smoothing:antialiased;
    background:
      radial-gradient(900px 520px at 14% -12%, rgba(116,160,160,.20), transparent 60%),
      radial-gradient(720px 520px at 112% 118%, rgba(255,215,0,.10), transparent 55%),
      linear-gradient(160deg,#0F1626 0%, #0A0F1C 55%, #070B14 100%);
    display:flex; align-items:center; justify-content:center; padding:24px; overflow:hidden;
  }
  .orb{ position:fixed; border-radius:50%; filter:blur(22px); z-index:0; pointer-events:none;
    width:540px; height:540px; top:-130px; left:-90px;
    background:radial-gradient(circle at 35% 30%, rgba(116,160,160,.34), rgba(116,160,160,0) 62%); }
  .orb.gold{ width:440px; height:440px; top:auto; left:auto; bottom:-130px; right:-100px;
    background:radial-gradient(circle at 60% 60%, rgba(255,215,0,.14), rgba(255,215,0,0) 60%); }
  .card{
    position:relative; z-index:1; width:100%; max-width:394px;
    background:linear-gradient(180deg, rgba(22,32,58,.74), rgba(17,24,39,.84));
    border:1px solid rgba(116,160,160,.18); border-radius:18px; padding:38px 36px 28px;
    box-shadow:0 34px 90px -34px rgba(0,0,0,.85), inset 0 1px 0 rgba(255,255,255,.04);
    backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px); overflow:hidden;
  }
  .card::before{ content:""; position:absolute; left:0; right:0; top:0; height:3px;
    background:linear-gradient(90deg,var(--teal-bright),var(--gold-bright)); }
  .logo{ margin:0 0 12px; }
  .logo svg{ display:block; filter:drop-shadow(0 8px 16px rgba(0,0,0,.45)); }
  .tag{ font-size:11px; letter-spacing:.34em; text-transform:uppercase; color:var(--teal-bright); font-weight:600; }
  .brand{ font-family:'Poppins',sans-serif; font-size:38px; line-height:1.04;
    margin:7px 0 0; font-weight:700; letter-spacing:-.01em; }
  .brand .dot{ color:var(--gold-bright); }
  .tagline{ color:var(--muted); font-size:14px; margin:7px 0 26px; }
  label{ display:block; font-size:12px; color:var(--muted); margin:0 0 7px 2px; }
  .field{ margin-bottom:16px; }
  input{ width:100%; padding:13px 14px; border-radius:11px; color:var(--ink); font-size:15px;
    font-family:inherit; background:rgba(13,20,34,.72); border:1px solid rgba(116,160,160,.20); outline:none;
    transition:border-color .18s, box-shadow .18s, background .18s; }
  input::placeholder{ color:#7c8597; }
  input:focus{ border-color:var(--teal-bright); box-shadow:0 0 0 3px rgba(116,160,160,.22); background:rgba(13,20,34,.92); }
  button{ width:100%; margin-top:6px; padding:13px 16px; border:0; border-radius:11px; cursor:pointer;
    font-family:inherit; font-size:15px; font-weight:700; color:#ffffff; letter-spacing:.01em;
    background:linear-gradient(135deg,var(--teal),#0D9488);
    box-shadow:0 12px 26px -12px rgba(116,160,160,.7); transition:transform .12s, box-shadow .18s, filter .18s; }
  button:hover{ transform:translateY(-1px); filter:brightness(1.08); box-shadow:0 16px 32px -12px rgba(116,160,160,.8); }
  button:active{ transform:translateY(0); }
  .error{ background:rgba(192,106,72,.16); border:1px solid rgba(192,106,72,.5); color:#f3cdb8;
    font-size:13px; padding:10px 12px; border-radius:10px; margin-bottom:18px; }
  .foot{ margin-top:22px; text-align:center; font-size:11.5px; color:#8a7a68; }
  .foot a{ color:var(--teal-bright); text-decoration:none; font-weight:600; }
  .foot a:hover{ color:var(--gold-bright); }
  .card>*{ opacity:0; transform:translateY(8px); animation:rise .6s cubic-bezier(.2,.7,.2,1) forwards; }
  .card>*:nth-child(1){ animation-delay:.05s } .card>*:nth-child(2){ animation-delay:.11s }
  .card>*:nth-child(3){ animation-delay:.17s } .card>*:nth-child(4){ animation-delay:.23s }
  .card>*:nth-child(5){ animation-delay:.29s } .card>*:nth-child(6){ animation-delay:.35s }
  .card>*:nth-child(7){ animation-delay:.41s } .card>*:nth-child(8){ animation-delay:.47s }
  .card>*:nth-child(9){ animation-delay:.53s }
  @keyframes rise{ to{ opacity:1; transform:none; } }
  @media (prefers-reduced-motion:reduce){ .card>*{ animation:none; opacity:1; transform:none } }
</style>
</head>
<body>
  <div class="orb"></div>
  <div class="orb gold"></div>
  <form class="card" method="post" action="/login" autocomplete="off">
    <div class="logo">__LOGO__</div>
    <div class="tag">Fertility Care AI</div>
    <div class="brand">EggWise<span class="dot">.</span></div>
    <div class="tagline">Agent console. Please sign in to continue.</div>
    <!--ERROR-->
    <div class="field">
      <label for="u">Username</label>
      <input id="u" name="username" placeholder="username" autofocus>
    </div>
    <div class="field">
      <label for="p">Password</label>
      <input id="p" name="password" type="password" placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;">
    </div>
    <button type="submit">Enter</button>
    <div class="foot">Secure access &middot; <a href="https://myeggwise.com" target="_blank" rel="noopener">MyEggWise.com</a></div>
  </form>
</body>
</html>""".replace("__LOGO__", LOGO_SVG)

ERROR_HTML = '<div class="error">Incorrect username or password.</div>'


def _login_page(error: bool) -> HTMLResponse:
    return HTMLResponse(LOGIN_HTML.replace("<!--ERROR-->", ERROR_HTML if error else ""))


@app.get("/login")
async def login_page(error: int = 0):
    return _login_page(bool(error))


@app.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    user = (form.get("username") or "").strip()
    pwd = form.get("password") or ""
    if DEMO_PASS and user == DEMO_USER and pwd == DEMO_PASS:
        secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
        resp = RedirectResponse("/console", status_code=303)
        resp.set_cookie(COOKIE, TOKEN, httponly=True, samesite="lax", secure=secure, max_age=60 * 60 * 12)
        return resp
    return RedirectResponse("/login?error=1", status_code=303)


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE)
    return resp


class LoginGate(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        is_html_get = request.method == "GET" and "text/html" in request.headers.get("accept", "")
        if DEMO_PASS:
            exempt = (path.startswith("/login") or path.startswith("/logout")
                      or path in ("/favicon.ico", "/healthz"))
            if not exempt and request.cookies.get(COOKIE) != TOKEN:
                if is_html_get:
                    return RedirectResponse("/login", status_code=303)
                return Response("Authentication required.", status_code=401)
        # Land everyone on the branded front-desk console.
        if path == "/" and is_html_get:
            return RedirectResponse("/console", status_code=303)
        return await call_next(request)


app.add_middleware(LoginGate)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
