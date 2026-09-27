"""SQLite persistence: schema + repositories.

All timestamps are stored as IST wall-clock strings 'YYYY-MM-DD HH:MM:SS'.
Thread model: one connection per thread (thread-local), WAL enabled.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strategies(
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    mode TEXT NOT NULL DEFAULT 'Paper',
    params TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS signals(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    cycle_id TEXT,
    strategy_key TEXT NOT NULL,
    instrument TEXT NOT NULL,
    side TEXT NOT NULL,
    entry REAL, sl REAL, target REAL,
    confidence REAL,
    reasons TEXT, thought TEXT,
    status TEXT DEFAULT 'NEW'
);
CREATE TABLE IF NOT EXISTS decision_log(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    cycle_id TEXT,
    stage TEXT NOT NULL,
    strategy_key TEXT DEFAULT '',
    thought TEXT NOT NULL,
    data TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS orders(
    id TEXT PRIMARY KEY,
    tag TEXT NOT NULL,
    ts TEXT NOT NULL,
    instrument TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL,
    qty INTEGER NOT NULL,
    price REAL,
    trigger_price REAL,
    filled_qty INTEGER DEFAULT 0,
    avg_fill_price REAL DEFAULT 0,
    status TEXT NOT NULL,
    strategy_key TEXT DEFAULT '',
    source TEXT NOT NULL,
    broker_order_id TEXT DEFAULT '',
    message TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS trades(
    id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    order_id TEXT,
    instrument TEXT NOT NULL,
    side TEXT NOT NULL,
    qty INTEGER NOT NULL,
    price REAL NOT NULL,
    fee REAL DEFAULT 0,
    pnl REAL DEFAULT 0,
    strategy_key TEXT DEFAULT '',
    source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS positions(
    instrument TEXT PRIMARY KEY,
    qty INTEGER NOT NULL,
    avg_price REAL NOT NULL,
    sl REAL, target REAL,
    trail_active INTEGER DEFAULT 0,
    trail_price REAL DEFAULT 0,
    strategy_key TEXT DEFAULT '',
    source TEXT NOT NULL,
    opened_at TEXT,
    is_options INTEGER DEFAULT 0,
    option_meta TEXT DEFAULT '{}',
    max_hold_seconds INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    source TEXT NOT NULL,
    event TEXT NOT NULL,
    detail TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS bot_state(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    strategy_key TEXT NOT NULL,
    window TEXT,
    stats TEXT DEFAULT '{}',
    suggestion TEXT DEFAULT '{}',
    applied INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_decision_ts ON decision_log(ts);
CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(ts);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts);
CREATE INDEX IF NOT EXISTS idx_orders_ts ON orders(ts);
"""


def ist_now_str() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


class Database:
    """Small thread-safe SQLite helper with thread-local connections."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_lock = threading.Lock()
        with self._conn() as con:
            con.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(self.path, timeout=30)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
            self._local.con = con
        return con

    # ---- generic helpers -------------------------------------------------
    def execute(self, sql: str, params: tuple = ()) -> None:
        with self._conn() as con:
            con.execute(sql, params)

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._conn() as con:
            return list(con.execute(sql, params).fetchall())

    def one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._conn() as con:
            return con.execute(sql, params).fetchone()

    # ---- settings -------------------------------------------------------
    def get_setting(self, key: str, default: str = "") -> str:
        row = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def get_state(self, key: str, default: str = "") -> str:
        row = self.one("SELECT value FROM bot_state WHERE key=?", (key,))
        return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO bot_state(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    # ---- logging / journal ---------------------------------------------
    def log(self, level: str, source: str, event: str, detail: str = "") -> None:
        self.execute(
            "INSERT INTO logs(ts,level,source,event,detail) VALUES(?,?,?,?,?)",
            (ist_now_str(), level, source, event, detail[:2000]),
        )

    def log_decision(self, cycle_id: str, stage: str, strategy_key: str,
                     thought: str, data: dict | None = None) -> None:
        self.execute(
            "INSERT INTO decision_log(ts,cycle_id,stage,strategy_key,thought,data) "
            "VALUES(?,?,?,?,?,?)",
            (ist_now_str(), cycle_id, stage, strategy_key, thought,
             json.dumps(data or {}, default=str)),
        )

    def recent_decisions(self, limit: int = 120) -> list[dict]:
        rows = self.query(
            "SELECT ts,stage,strategy_key,thought FROM decision_log "
            "ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows][::-1]

    def insert_signal(self, cycle_id: str, sig, status: str = "NEW") -> None:
        self.execute(
            "INSERT INTO signals(ts,cycle_id,strategy_key,instrument,side,entry,sl,"
            "target,confidence,reasons,thought,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (ist_now_str(), cycle_id, sig.strategy_key, sig.instrument,
             sig.side.value, sig.entry, sig.sl, sig.target, sig.confidence,
             json.dumps(sig.reasons), sig.thought, status),
        )

    # ---- orders / trades / positions ------------------------------------
    def upsert_order(self, o) -> None:
        self.execute(
            "INSERT INTO orders(id,tag,ts,instrument,side,order_type,qty,price,"
            "trigger_price,filled_qty,avg_fill_price,status,strategy_key,source,"
            "broker_order_id,message) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET filled_qty=excluded.filled_qty,"
            "avg_fill_price=excluded.avg_fill_price,status=excluded.status,"
            "message=excluded.message",
            (o.id, o.tag, o.created_at, o.instrument, o.side.value, o.order_type.value,
             o.qty, o.price, o.trigger_price, o.filled_qty, o.avg_fill_price,
             o.status.value, o.strategy_key, o.source.value, o.broker_order_id,
             o.message),
        )

    def insert_trade(self, t) -> None:
        self.execute(
            "INSERT INTO trades(id,ts,order_id,instrument,side,qty,price,fee,pnl,"
            "strategy_key,source) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (t.id, t.ts, "", t.instrument, t.side.value, t.qty, t.price, t.fee,
             t.pnl, t.strategy_key, t.source.value),
        )

    def upsert_position(self, p) -> None:
        self.execute(
            "INSERT INTO positions(instrument,qty,avg_price,sl,target,trail_active,"
            "trail_price,strategy_key,source,opened_at,is_options,option_meta,"
            "max_hold_seconds) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(instrument) DO UPDATE SET qty=excluded.qty,"
            "avg_price=excluded.avg_price,sl=excluded.sl,target=excluded.target,"
            "trail_active=excluded.trail_active,trail_price=excluded.trail_price",
            (p.instrument, p.qty, p.avg_price, p.sl, p.target, int(p.trail_active),
             p.trail_price, p.strategy_key, p.source.value, p.opened_at,
             int(p.is_options), json.dumps(p.option_meta or {}),
             p.max_hold_seconds),
        )

    def delete_position(self, instrument: str) -> None:
        self.execute("DELETE FROM positions WHERE instrument=?", (instrument,))

    def load_positions(self) -> list[dict]:
        return [dict(r) for r in self.query("SELECT * FROM positions")]

    def load_open_orders(self) -> list[dict]:
        return [dict(r) for r in self.query(
            "SELECT * FROM orders WHERE status IN ('PENDING','OPEN','PARTIAL')")]

    # ---- reviews --------------------------------------------------------
    def insert_review(self, strategy_key: str, window: str, stats: dict,
                      suggestion: dict, applied: bool) -> None:
        self.execute(
            "INSERT INTO reviews(ts,strategy_key,window,stats,suggestion,applied) "
            "VALUES(?,?,?,?,?,?)",
            (ist_now_str(), strategy_key, window, json.dumps(stats),
             json.dumps(suggestion), int(applied)),
        )

    def recent_reviews(self, limit: int = 50) -> list[dict]:
        rows = self.query("SELECT * FROM reviews ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]
