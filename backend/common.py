import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(os.environ.get("COACH_ENV_FILE", str(ROOT / ".env")), override=False)
DATA = ROOT / ".local"
DATABASE = Path(os.environ.get("COACH_DB", str(DATA / "sessions.sqlite")))
BUDGET = Path(
    os.environ.get("COACH_BUDGET_DB") or str(ROOT.parent / ".ai-coach-state" / "budget.sqlite")
)


@contextmanager
def db():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DATABASE, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, payload TEXT, updated REAL)"
    )
    con.execute("CREATE TABLE IF NOT EXISTS events(id TEXT, name TEXT, payload TEXT, at REAL)")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def read_session(sid):
    with db() as con:
        row = con.execute("SELECT payload FROM sessions WHERE id=?", (sid,)).fetchone()
    return json.loads(row["payload"]) if row else {"revision": 0}


def save_session(sid, payload):
    payload["revision"] = payload.get("revision", 0) + 1
    with db() as con:
        con.execute(
            "INSERT OR REPLACE INTO sessions VALUES(?,?,?)",
            (sid, json.dumps(payload, ensure_ascii=False), time.time()),
        )
    return payload


def event(sid, name, payload=None):
    with db() as con:
        con.execute(
            "INSERT INTO events VALUES(?,?,?,?)",
            (sid, name, json.dumps(payload or {}), time.time()),
        )


def export_session(sid):
    with db() as con:
        events = [
            dict(r)
            for r in con.execute(
                "SELECT name,payload,at FROM events WHERE id=? ORDER BY at", (sid,)
            )
        ]
    return {
        "session": read_session(sid),
        "events": events,
        "boundary": "仅本会话；技术试测与真实参与者应分开，模型评分不是录用预测或真实学习效果。",
    }


def delete_session(sid):
    with db() as con:
        con.execute("DELETE FROM sessions WHERE id=?", (sid,))
        con.execute("DELETE FROM events WHERE id=?", (sid,))


@contextmanager
def budget_connection():
    BUDGET.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(BUDGET, timeout=20)
    con.execute(
        "CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY,provider TEXT,model TEXT,reserved REAL,charged REAL,status TEXT,at REAL)"
    )
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def reserve(provider, model, amount):
    if amount <= 0:
        raise ValueError("费用估算无效")
    with budget_connection() as con:
        con.execute("BEGIN IMMEDIATE")
        total = con.execute(
            "SELECT COALESCE(SUM(COALESCE(charged,reserved)),0) FROM calls"
        ).fetchone()[0]
        if total + amount > 5:
            raise ValueError("两个项目共享的5美元预算不足，本次请求未发送。")
        ticket = secrets.token_hex(12)
        con.execute(
            "INSERT INTO calls VALUES(?,?,?,?,?,?,?)",
            (ticket, provider, model, amount, None, "reserved", time.time()),
        )
    return ticket


def settle(ticket, actual=None, status="completed"):
    with budget_connection() as con:
        con.execute("UPDATE calls SET charged=?,status=? WHERE id=?", (actual, status, ticket))


def budget_status():
    with budget_connection() as con:
        value = con.execute(
            "SELECT COALESCE(SUM(COALESCE(charged,reserved)),0),COUNT(*) FROM calls"
        ).fetchone()
    return {
        "limit_usd": 5,
        "estimated_or_reserved_usd": round(value[0], 6),
        "requests": value[1],
        "note": "按配置的保守单价计算，非供应商账单；未知计费失败保留预留。",
    }


def input_text(value, label, maximum=30000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label}不能为空且最多{maximum}字")
    return value.strip()


def setup(app: FastAPI):
    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = request.headers.get("host", "")
        allowed = {f"127.0.0.1:{app.state.port}", f"localhost:{app.state.port}", "testserver"}
        if host not in allowed:
            return JSONResponse({"error": "仅允许本机访问"}, 403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if (
                request.headers.get("origin") not in {"http://" + h for h in allowed}
                or request.headers.get("x-coach-request") != "1"
            ):
                return JSONResponse({"error": "请求来源校验失败"}, 403)
            try:
                if int(request.headers.get("content-length", "0")) > 16000000:
                    return JSONResponse({"error": "请求过大"}, 413)
            except ValueError:
                return JSONResponse({"error": "请求大小无效"}, 400)
        sid = request.cookies.get("coach_session", "")
        if len(sid) != 64 or any(c not in "0123456789abcdef" for c in sid):
            sid = secrets.token_hex(32)
        request.state.sid = sid
        response = await call_next(request)
        response.set_cookie("coach_session", sid, httponly=True, samesite="strict", max_age=604800)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; media-src 'self' blob:; img-src 'self' data:; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(ValueError)
    async def invalid(_, exc):
        return JSONResponse({"error": str(exc)[:350]}, 400)

    @app.get("/api/status")
    def status():
        from backend.providers import provider_status

        return {**provider_status(), "budget": budget_status()}

    @app.get("/api/session")
    def session(request: Request):
        return read_session(request.state.sid)

    @app.get("/api/export")
    def export(request: Request):
        return export_session(request.state.sid)

    @app.delete("/api/session")
    def delete(request: Request):
        with app.state.locks[request.state.sid]:
            delete_session(request.state.sid)
        return {"ok": True}


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
