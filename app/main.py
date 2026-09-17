import os
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'kittylol.db'}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_urlsafe(32))
HOMEPAGE_URL = os.getenv("HOMEPAGE_URL", "/")
MAX_SCRIPT_BYTES = int(os.getenv("MAX_SCRIPT_BYTES", "2097152"))


class Base(DeclarativeBase):
    pass


class Script(Base):
    __tablename__ = "scripts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(40), default="1.0.0")
    content: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    loads: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[list["Token"]] = relationship(back_populates="script", cascade="all, delete-orphan")


class Token(Base):
    __tablename__ = "tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id", ondelete="CASCADE"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    loads: Mapped[int] = mapped_column(Integer, default=0)
    script: Mapped[Script] = relationship(back_populates="tokens")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    key_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hwid: Mapped[str | None] = mapped_column(String(180), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Log(Base):
    __tablename__ = "logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(String(500))
    ip: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(engine)

app = FastAPI(title="Kittylol API", version="2.0.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="kittylol_session",
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

_rate = defaultdict(deque)


def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def admin_required(request: Request):
    if not request.session.get("admin"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return True


def add_log(session, event, detail, request):
    session.add(Log(event=event, detail=detail[:500], ip=request.client.host if request.client else ""))


def browser_request(request: Request):
    accept = request.headers.get("accept", "").lower()
    ua = request.headers.get("user-agent", "").lower()
    return "text/html" in accept and not any(x in ua for x in ("roblox", "luau", "httpget"))


def valid_token(token, script):
    if not token or not script or not token.enabled or not script.enabled:
        return False
    if token.expires_at:
        exp = token.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= datetime.now(timezone.utc):
            return False
    return True


def rate_limit(request: Request, limit=90, window=60):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    q = _rate[ip]
    while q and q[0] <= now - window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    q.append(now)


@app.middleware("http")
async def headers_and_limit(request: Request, call_next):
    if request.url.path.startswith("/files/v4/loader/"):
        rate_limit(request)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health():
    return {"status": "ok", "service": "kittylol-api", "version": "2.0.0"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request, "homepage_url": HOMEPAGE_URL})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if secrets.compare_digest(username, ADMIN_USERNAME) and secrets.compare_digest(password, ADMIN_PASSWORD):
        request.session.clear()
        request.session["admin"] = True
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"}, status_code=401)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, _: bool = Depends(admin_required), session: Session = Depends(db)):
    scripts = session.scalars(select(Script).order_by(Script.id.desc())).all()
    tokens = session.scalars(select(Token).order_by(Token.id.desc())).all()
    users = session.scalars(select(User).order_by(User.id.desc())).all()
    logs = session.scalars(select(Log).order_by(Log.id.desc()).limit(30)).all()
    total_loads = sum(s.loads for s in scripts)
    active_tokens = sum(1 for t in tokens if t.enabled)
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "scripts": scripts, "tokens": tokens, "users": users, "logs": logs,
        "total_loads": total_loads, "active_tokens": active_tokens,
        "base_url": str(request.base_url).rstrip("/"), "homepage_url": HOMEPAGE_URL
    })


@app.post("/dashboard/scripts")
async def create_script(
    request: Request,
    name: str = Form(...),
    version: str = Form("1.0.0"),
    content: str = Form(""),
    file: UploadFile | None = File(None),
    _: bool = Depends(admin_required),
    session: Session = Depends(db),
):
    if file and file.filename:
        raw = await file.read()
        if len(raw) > MAX_SCRIPT_BYTES:
            raise HTTPException(413, "Script exceeds configured size limit")
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(400, "Script must be UTF-8 text")
    if not content.strip():
        raise HTTPException(400, "Script content is required")
    if len(content.encode("utf-8")) > MAX_SCRIPT_BYTES:
        raise HTTPException(413, "Script exceeds configured size limit")
    now = datetime.now(timezone.utc)
    s = Script(name=name.strip()[:120], version=version.strip()[:40] or "1.0.0", content=content, created_at=now, updated_at=now)
    session.add(s)
    add_log(session, "script.created", s.name, request)
    session.commit()
    return RedirectResponse("/dashboard#scripts", 303)


@app.post("/dashboard/scripts/{script_id}/toggle")
def toggle_script(script_id: int, request: Request, _: bool = Depends(admin_required), session: Session = Depends(db)):
    s = session.get(Script, script_id)
    if not s:
        raise HTTPException(404, "Script not found")
    s.enabled = not s.enabled
    s.updated_at = datetime.now(timezone.utc)
    add_log(session, "script.status", f"{s.name}: {s.enabled}", request)
    session.commit()
    return RedirectResponse("/dashboard#scripts", 303)


@app.post("/dashboard/scripts/{script_id}/delete")
def delete_script(script_id: int, request: Request, _: bool = Depends(admin_required), session: Session = Depends(db)):
    s = session.get(Script, script_id)
    if not s:
        raise HTTPException(404, "Script not found")
    add_log(session, "script.deleted", s.name, request)
    session.delete(s)
    session.commit()
    return RedirectResponse("/dashboard#scripts", 303)


@app.post("/dashboard/tokens")
def create_token(
    request: Request,
    script_id: int = Form(...),
    expires_days: int = Form(0),
    _: bool = Depends(admin_required),
    session: Session = Depends(db),
):
    s = session.get(Script, script_id)
    if not s:
        raise HTTPException(404, "Script not found")
    expiry = None if expires_days <= 0 else datetime.now(timezone.utc) + timedelta(days=min(expires_days, 3650))
    t = Token(value=secrets.token_urlsafe(18), script_id=script_id, expires_at=expiry)
    session.add(t)
    add_log(session, "token.created", f"{s.name}: {t.value}", request)
    session.commit()
    return RedirectResponse("/dashboard#tokens", 303)


@app.post("/dashboard/tokens/{token_id}/toggle")
def toggle_token(token_id: int, request: Request, _: bool = Depends(admin_required), session: Session = Depends(db)):
    t = session.get(Token, token_id)
    if not t:
        raise HTTPException(404, "Token not found")
    t.enabled = not t.enabled
    add_log(session, "token.status", f"{t.value}: {t.enabled}", request)
    session.commit()
    return RedirectResponse("/dashboard#tokens", 303)


@app.post("/dashboard/tokens/{token_id}/delete")
def delete_token(token_id: int, request: Request, _: bool = Depends(admin_required), session: Session = Depends(db)):
    t = session.get(Token, token_id)
    if not t:
        raise HTTPException(404, "Token not found")
    add_log(session, "token.deleted", t.value, request)
    session.delete(t)
    session.commit()
    return RedirectResponse("/dashboard#tokens", 303)


@app.post("/dashboard/users")
def create_user(
    request: Request,
    username: str = Form(...),
    key_value: str = Form(""),
    _: bool = Depends(admin_required),
    session: Session = Depends(db),
):
    name = username.strip()[:80]
    if not name:
        raise HTTPException(400, "Username required")
    existing = session.scalar(select(User).where(User.username == name))
    if existing:
        raise HTTPException(409, "Username already exists")
    u = User(username=name, key_value=key_value.strip()[:100] or None)
    session.add(u)
    add_log(session, "user.created", name, request)
    session.commit()
    return RedirectResponse("/dashboard#users", 303)


@app.post("/dashboard/users/{user_id}/toggle")
def toggle_user(user_id: int, request: Request, _: bool = Depends(admin_required), session: Session = Depends(db)):
    u = session.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    u.status = "banned" if u.status == "active" else "active"
    add_log(session, "user.status", f"{u.username}: {u.status}", request)
    session.commit()
    return RedirectResponse("/dashboard#users", 303)


@app.post("/dashboard/users/{user_id}/reset-hwid")
def reset_hwid(user_id: int, request: Request, _: bool = Depends(admin_required), session: Session = Depends(db)):
    u = session.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    u.hwid = None
    add_log(session, "hwid.reset", u.username, request)
    session.commit()
    return RedirectResponse("/dashboard#users", 303)


@app.get("/api/v1/key/{value}")
def validate_key(value: str, session: Session = Depends(db)):
    t = session.scalar(select(Token).where(Token.value == value))
    if not t:
        return {"valid": False}
    s = session.get(Script, t.script_id)
    return {"valid": valid_token(t, s), "token": t.value, "script": s.name if s else None,
            "expires_at": t.expires_at.isoformat() if t.expires_at else None}


@app.get("/api/v1/stats")
def stats(_: bool = Depends(admin_required), session: Session = Depends(db)):
    return {
        "scripts": session.scalar(select(func.count(Script.id))) or 0,
        "tokens": session.scalar(select(func.count(Token.id))) or 0,
        "users": session.scalar(select(func.count(User.id))) or 0,
        "logs": session.scalar(select(func.count(Log.id))) or 0,
    }


@app.get("/files/v4/loader/{token}.lua")
def loader(request: Request, token: str, session: Session = Depends(db)):
    t = session.scalar(select(Token).where(Token.value == token))
    s = session.get(Script, t.script_id) if t else None
    if not valid_token(t, s):
        if browser_request(request):
            return templates.TemplateResponse("loader.html", {
                "request": request, "valid": False, "message": "This loader is disabled, expired, or invalid.",
                "homepage_url": HOMEPAGE_URL
            }, status_code=403 if t else 404)
        return PlainTextResponse("Kittylol: invalid or disabled loader", status_code=403 if t else 404)
    t.loads += 1
    s.loads += 1
    add_log(session, "loader.load", s.name, request)
    session.commit()
    if browser_request(request):
        return templates.TemplateResponse("loader.html", {
            "request": request, "valid": True, "script": s, "token": t,
            "homepage_url": HOMEPAGE_URL
        })
    return PlainTextResponse(s.content, media_type="text/plain; charset=utf-8")
