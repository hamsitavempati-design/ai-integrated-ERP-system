"""Single-owner authentication for the ERP app.

Set ERP_AUTH_SECRET and ERP_OWNER_EMAIL / ERP_OWNER_PASSWORD in the environment.
Password-reset email requires SMTP_* environment variables.
Google OAuth requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET plus Authlib.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import smtplib
import sqlite3
import time
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/auth", tags=["authentication"])
DB_PATH = Path(os.getenv("ERP_AUTH_DB", "erp_auth.db"))
SECRET = os.getenv("ERP_AUTH_SECRET", "")
COOKIE = "erp_session"
COOKIE_SECURE = os.getenv("ERP_COOKIE_SECURE", "0") == "1"
RESET_TTL = 30 * 60


class LoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    remember_me: bool = False


class OwnerRegistration(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    confirm_password: str = Field(min_length=12, max_length=256)


class ForgotPayload(BaseModel):
    email: EmailStr


class ResetPayload(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    password: str = Field(min_length=12, max_length=256)
    confirm_password: str = Field(min_length=12, max_length=256)


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password, stored):
    try:
        s, d = stored.split("$", 1)
        salt = base64.urlsafe_b64decode(s.encode())
        expected = base64.urlsafe_b64decode(d.encode())
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def init_auth_db():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner')),
            active INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS password_resets(
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        email = os.getenv("ERP_OWNER_EMAIL", "").strip().lower()
        password = os.getenv("ERP_OWNER_PASSWORD", "")
        if email and password:
            existing = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if not existing and not c.execute("SELECT id FROM users LIMIT 1").fetchone():
                c.execute(
                    "INSERT INTO users(email,password_hash,role,active,created_at) VALUES(?,?,?,?,?)",
                    (email, hash_password(password), "owner", 1, int(time.time())),
                )


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def make_token(user, ttl):
    if not SECRET or SECRET == "CHANGE-ME-local-development-only":
        raise HTTPException(500, "Set a unique ERP_AUTH_SECRET before signing in.")
    head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = b64(json.dumps({
        "sub": user["id"], "email": user["email"], "role": "owner",
        "exp": int(time.time()) + ttl,
    }, separators=(",", ":")).encode())
    body = head + "." + payload
    sig = b64(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest())
    return body + "." + sig


def decode(token):
    try:
        if not SECRET or SECRET == "CHANGE-ME-local-development-only":
            return None
        head, payload, sig = token.split(".")
        body = head + "." + payload
        expected = b64(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(unb64(payload))
        return data if int(data.get("exp", 0)) > int(time.time()) else None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def current_user(request: Request):
    claims = decode(request.cookies.get(COOKIE, ""))
    if not claims:
        raise HTTPException(401, "Please sign in.")
    with connect() as c:
        user = c.execute("SELECT id,email,active FROM users WHERE id=?", (claims["sub"],)).fetchone()
    if not user or not user["active"]:
        raise HTTPException(401, "Account inactive.")
    return {"id": user["id"], "email": user["email"], "role": "owner"}


def send_reset_email(email, reset_url):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", username or "")
    if not all([host, username, password, sender]):
        raise RuntimeError("SMTP email settings are missing")
    msg = EmailMessage()
    msg["Subject"] = "Reset your ERP password"
    msg["From"] = sender
    msg["To"] = email
    msg.set_content(
        "A password reset was requested for your ERP account.\n\n"
        f"Use this link within 30 minutes:\n{reset_url}\n\n"
        "If you did not request this, ignore this message."
    )
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(msg)


@router.get("/setup-status")
def setup_status():
    with connect() as c:
        has_owner = c.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
    return {"owner_exists": has_owner}


@router.post("/register-owner")
def register_owner(data: OwnerRegistration):
    if data.password != data.confirm_password:
        raise HTTPException(400, "Passwords do not match.")
    with connect() as c:
        if c.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            raise HTTPException(403, "The owner account is already set up. Public registration is closed.")
        c.execute(
            "INSERT INTO users(email,password_hash,role,active,created_at) VALUES(?,?,?,?,?)",
            (str(data.email).lower(), hash_password(data.password), "owner", 1, int(time.time())),
        )
    return {"ok": True, "message": "Owner account created. You can now sign in."}


@router.post("/login")
def login(data: LoginPayload, response: Response):
    with connect() as c:
        user = c.execute(
            "SELECT id,email,password_hash,active FROM users WHERE email=?",
            (str(data.email).lower(),),
        ).fetchone()
    if not user or not user["active"] or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password. Check the email and password used when creating your owner account.")
    ttl = 60 * 60 * 24 * 30 if data.remember_me else 60 * 60 * 12
    response.set_cookie(
        COOKIE, make_token(user, ttl), httponly=True, secure=COOKIE_SECURE,
        samesite="lax", max_age=ttl, path="/",
    )
    return {"ok": True, "user": {"id": user["id"], "email": user["email"], "role": "owner"}}


@router.get("/me")
def me(user=Depends(current_user)):
    return {"user": user}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/", httponly=True, secure=COOKIE_SECURE, samesite="lax")
    return {"ok": True}


@router.post("/forgot-password")
def forgot_password(data: ForgotPayload, request: Request):
    # Always return the same response to avoid revealing whether an email exists.
    with connect() as c:
        user = c.execute("SELECT id,email FROM users WHERE email=? AND active=1", (str(data.email).lower(),)).fetchone()
        if user:
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            c.execute("DELETE FROM password_resets WHERE user_id=?", (user["id"],))
            c.execute(
                "INSERT INTO password_resets(token_hash,user_id,expires_at) VALUES(?,?,?)",
                (token_hash, user["id"], int(time.time()) + RESET_TTL),
            )
    if user:
        base_url = str(request.base_url).rstrip("/")
        reset_url = base_url + "/?reset_token=" + raw_token
        try:
            send_reset_email(user["email"], reset_url)
        except Exception as exc:
            # Do not expose token or account details to the browser.
            print(f"Password reset email was not sent. Configure SMTP_* environment variables. Details: {exc}")
    return {"ok": True, "message": "If that email belongs to the owner account and email delivery is configured, a reset link will be sent."}


@router.post("/reset-password")
def reset_password(data: ResetPayload):
    if data.password != data.confirm_password:
        raise HTTPException(400, "Passwords do not match.")
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    with connect() as c:
        row = c.execute(
            "SELECT user_id FROM password_resets WHERE token_hash=? AND expires_at>?",
            (token_hash, int(time.time())),
        ).fetchone()
        if not row:
            raise HTTPException(400, "Reset link is invalid or expired. Request a new one.")
        c.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(data.password), row["user_id"]))
        c.execute("DELETE FROM password_resets WHERE user_id=?", (row["user_id"],))
    return {"ok": True, "message": "Password updated. Please sign in."}


@router.get("/google")
def google_login():
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(503, "Google sign-in is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and install Authlib.")
    try:
        from authlib.integrations.starlette_client import OAuth
        from starlette.requests import Request as StarletteRequest
    except ImportError:
        raise HTTPException(503, "Install Authlib first: python -m pip install Authlib")
    # Redirect URI must be registered in Google Cloud Console.
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/auth/google/callback")
    from starlette.responses import RedirectResponse as StarletteRedirectResponse
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": secrets.token_urlsafe(24),
        "access_type": "online",
        "prompt": "select_account",
    }
    # This endpoint builds the standard OAuth authorization redirect. Callback exchange
    # and identity verification should be configured for deployment before use.
    from urllib.parse import urlencode
    return StarletteRedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))


@router.get("/health")
def health():
    return {"ok": True}
