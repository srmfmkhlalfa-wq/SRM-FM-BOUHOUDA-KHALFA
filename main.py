import os, json, sqlite3
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

DB = os.getenv("DB_PATH", "srmfm.db")
PINS = {os.getenv("AGENT_PIN", "1234"): "agent", os.getenv("ADMIN_PIN", "admin2026"): "admin"}
SEED = [{"n": 1, "l": "Réparation fuite sur branchement avec fourniture", "u": "U", "pu": 0, "min": 0, "max": 0},
        {"n": 6, "l": "Réparation fuite PEHD ≤ 63", "u": "U", "pu": 0, "min": 0, "max": 0},
        {"n": 31, "l": "Robinet vanne", "u": "U", "pu": 0, "min": 0, "max": 0}]
app = FastAPI(title="SRM-FM Marché 42/24/2026")

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

with db() as c:
    c.execute("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS interventions(id INTEGER PRIMARY KEY AUTOINCREMENT, centre TEXT, bp INT,
        nature TEXT, loc TEXT, gps TEXT, agent TEXT, h1 TEXT, h2 TEXT, statut TEXT, qte REAL, ht REAL)""")
    c.execute("INSERT OR IGNORE INTO kv VALUES('bp', ?)", (json.dumps(SEED),))

def role(pin, need=None):
    r = PINS.get(pin or "")
    if not r: raise HTTPException(401, "Code invalide")
    if need and r != need: raise HTTPException(403, "Accès refusé")
    return r

def get_bp(c): return json.loads(c.execute("SELECT v FROM kv WHERE k='bp'").fetchone()[0])
def row(c, i): return dict(c.execute("SELECT * FROM interventions WHERE id=?", (i,)).fetchone())

class I(BaseModel):
    centre: str; bp: int; nature: str = ""; loc: str; gps: str = ""; agent: str
    h1: str; h2: str = ""; statut: str = "I"; qte: float = 1

@app.get("/api/data")
def data(x_pin: str = Header(None)):
    r = role(x_pin)
    with db() as c:
        rows = [dict(x) for x in c.execute("SELECT * FROM interventions ORDER BY h1 DESC")] if r == "admin" else []
        return {"role": r, "bp": get_bp(c), "int": rows}

@app.post("/api/interventions")
def create(i: I, x_pin: str = Header(None)):
    role(x_pin)
    with db() as c:
        pu = next((b["pu"] for b in get_bp(c) if b["n"] == i.bp), 0)
        cur = c.execute("INSERT INTO interventions(centre,bp,nature,loc,gps,agent,h1,h2,statut,qte,ht) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (i.centre, i.bp, i.nature, i.loc, i.gps, i.agent, i.h1, i.h2, i.statut, i.qte, pu * i.qte))
        return row(c, cur.lastrowid)

@app.patch("/api/interventions/{iid}/close")
def close(iid: int, x_pin: str = Header(None)):
    role(x_pin)
    with db() as c:
        c.execute("UPDATE interventions SET statut='R', h2=? WHERE id=?", (datetime.now().strftime("%Y-%m-%dT%H:%M"), iid))
        return row(c, iid)

@app.put("/api/bordereau")
def put_bp(bp: list[dict], x_pin: str = Header(None)):
    role(x_pin, "admin")
    with db() as c: c.execute("UPDATE kv SET v=? WHERE k='bp'", (json.dumps(bp),))
    return {"ok": True}

@app.get("/")
def index(): return FileResponse("static/index.html")
