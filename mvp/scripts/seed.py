#!/usr/bin/env python
# Idempotent seed for CI/demos.
import os, sqlite3, uuid, json, time
DB_PATH = os.getenv("IR_DB_PATH", "data/ir.sqlite")

def uuid5(ns, name):  # deterministic IDs
    return str(uuid.uuid5(ns, name))

def main():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    cur = con.cursor()

    # --- 1) ensure tables exist (very minimal; your real migrations may already do this)
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS person (id TEXT PRIMARY KEY, name TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS calendar_event (
      id TEXT PRIMARY KEY, person_name TEXT, start TEXT, end TEXT
    );
    CREATE UNIQUE INDEX IF NOT EXISTS ux_calendar ON calendar_event(person_name,start,end);
    """)

    # --- 2) people fixtures for CLARIFY (two Danas)
    dns = uuid.UUID("12345678-1234-5678-1234-567812345678")
    for name in ["Dana Lee", "Dana Xu"]:
        cur.execute("INSERT OR IGNORE INTO person(id,name) VALUES(?,?)",
                    (uuid5(dns, name), name))

    # --- 3) calendar fixture for GUARDRAIL (Dana busy at 2025-09-06 13:00-14:00 -07:00)
    # Match your Proof Packet input exactly.
    evt_id = uuid5(dns, "Dana@2025-09-06T13:00-07:00")
    cur.execute("""INSERT OR IGNORE INTO calendar_event(id,person_name,start,end)
                   VALUES(?,?,?,?)""",
                (evt_id, "Dana", "2025-09-06T13:00-07:00", "2025-09-06T14:00-07:00"))

    con.commit()
    con.close()
    print("seed.py: ok (fixtures ensured)")

if __name__ == "__main__":
    main()
