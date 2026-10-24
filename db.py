"""Archivio SQLite: cache prezzi ed eventi, portafoglio, segnali dello scanner,
istantanee giornaliere (classe B), report del Laboratorio e registro delle prove."""
import json
import os
import sqlite3
import threading
import time

import config

_lock = threading.Lock()


def connect():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init():
    with _lock, connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS price_cache (
                ticker TEXT PRIMARY KEY, ts REAL, payload TEXT);
            CREATE TABLE IF NOT EXISTS fund_cache (
                ticker TEXT PRIMARY KEY, ts REAL, payload TEXT);
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL, qty REAL NOT NULL, avg_price REAL NOT NULL,
                buy_date TEXT, note TEXT);
            CREATE TABLE IF NOT EXISTS signals (
                ticker TEXT PRIMARY KEY, ts REAL, market TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS scan_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, status TEXT, detail TEXT);
            CREATE TABLE IF NOT EXISTS events_cache (
                ticker TEXT PRIMARY KEY, ts REAL, payload TEXT);
            CREATE TABLE IF NOT EXISTS options_cache (
                ticker TEXT PRIMARY KEY, ts REAL, payload TEXT);
            CREATE TABLE IF NOT EXISTS source_cache (
                ticker TEXT PRIMARY KEY, ts REAL, payload TEXT);
            CREATE TABLE IF NOT EXISTS snapshots (
                date TEXT, ticker TEXT, field TEXT, value REAL,
                PRIMARY KEY (date, ticker, field));
            CREATE TABLE IF NOT EXISTS lab_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, panel TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS trials (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, panel TEXT, name TEXT,
                config_hash TEXT, config TEXT, metrics TEXT);
            """
        )


def cache_get(table, ticker, ttl):
    with connect() as con:
        r = con.execute(f"SELECT ts, payload FROM {table} WHERE ticker=?", (ticker,)).fetchone()
    if r and time.time() - r["ts"] < ttl:
        return json.loads(r["payload"])
    return None


def cache_put(table, ticker, payload):
    with _lock, connect() as con:
        con.execute(
            f"INSERT OR REPLACE INTO {table}(ticker, ts, payload) VALUES (?,?,?)",
            (ticker, time.time(), json.dumps(payload)),
        )


# ---- portafoglio ----
def holdings_list():
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM holdings ORDER BY ticker")]


def holding_add(ticker, qty, avg_price, buy_date=None, note=None):
    with _lock, connect() as con:
        cur = con.execute(
            "INSERT INTO holdings(ticker, qty, avg_price, buy_date, note) VALUES (?,?,?,?,?)",
            (ticker.upper(), qty, avg_price, buy_date, note),
        )
        return cur.lastrowid


def holding_delete(hid):
    with _lock, connect() as con:
        con.execute("DELETE FROM holdings WHERE id=?", (hid,))


# ---- segnali ----
def signal_put(ticker, market, payload):
    with _lock, connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO signals(ticker, ts, market, payload) VALUES (?,?,?,?)",
            (ticker, time.time(), market, json.dumps(payload)),
        )


def signals_all():
    with connect() as con:
        rows = con.execute("SELECT ticker, ts, market, payload FROM signals").fetchall()
    out = []
    for r in rows:
        p = json.loads(r["payload"])
        p["scan_ts"] = r["ts"]
        out.append(p)
    return out


def signal_get(ticker):
    with connect() as con:
        r = con.execute("SELECT ts, payload FROM signals WHERE ticker=?", (ticker,)).fetchone()
    if not r:
        return None
    p = json.loads(r["payload"])
    p["scan_ts"] = r["ts"]
    return p


def scan_log(status, detail=""):
    with _lock, connect() as con:
        con.execute("INSERT INTO scan_log(ts, status, detail) VALUES (?,?,?)", (time.time(), status, detail))


def scan_last():
    with connect() as con:
        r = con.execute("SELECT * FROM scan_log ORDER BY id DESC LIMIT 1").fetchone()
    return dict(r) if r else None


# ---- istantanee di classe B (raccolte ogni notte, mai usate nel passato) ----
def snapshot_put(date, ticker, values: dict):
    rows = [(date, ticker, k, float(v)) for k, v in values.items()
            if v is not None and v == v and abs(float(v)) < 1e300]
    if not rows:
        return 0
    with _lock, connect() as con:
        con.executemany("INSERT OR REPLACE INTO snapshots(date, ticker, field, value) VALUES (?,?,?,?)", rows)
    return len(rows)


def snapshot_rows(field=None):
    q = "SELECT date, ticker, field, value FROM snapshots"
    args = ()
    if field:
        q += " WHERE field=?"
        args = (field,)
    with connect() as con:
        return [dict(r) for r in con.execute(q, args)]


def snapshot_dates_by_field():
    with connect() as con:
        rows = con.execute("SELECT field, COUNT(DISTINCT date) AS n, MIN(date) AS first, MAX(date) AS last "
                           "FROM snapshots GROUP BY field").fetchall()
    return {r["field"]: dict(r) for r in rows}


# ---- Laboratorio ----
def lab_report_put(panel, payload):
    with _lock, connect() as con:
        con.execute("INSERT INTO lab_reports(ts, panel, payload) VALUES (?,?,?)",
                    (time.time(), panel, json.dumps(payload)))


def lab_report_last(panel):
    with connect() as con:
        r = con.execute("SELECT ts, payload FROM lab_reports WHERE panel=? ORDER BY id DESC LIMIT 1",
                        (panel,)).fetchone()
    if not r:
        return None
    p = json.loads(r["payload"])
    p["ts"] = r["ts"]
    return p


def trial_put(panel, name, config_hash, cfg, metrics):
    with _lock, connect() as con:
        con.execute("INSERT INTO trials(ts, panel, name, config_hash, config, metrics) VALUES (?,?,?,?,?,?)",
                    (time.time(), panel, name, config_hash, json.dumps(cfg), json.dumps(metrics)))


def trials_count(panel=None):
    """Numero di configurazioni DISTINTE provate (serve al Deflated Sharpe)."""
    q = "SELECT COUNT(DISTINCT config_hash) AS n FROM trials"
    args = ()
    if panel:
        q += " WHERE panel=?"
        args = (panel,)
    with connect() as con:
        return int(con.execute(q, args).fetchone()["n"])


def trials_list(panel=None, limit=200):
    q = "SELECT ts, panel, name, config_hash, metrics FROM trials"
    args = []
    if panel:
        q += " WHERE panel=?"
        args.append(panel)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with connect() as con:
        out = []
        for r in con.execute(q, args):
            d = dict(r)
            d["metrics"] = json.loads(d["metrics"])
            out.append(d)
        return out
