# A pretend ad platform: accepts audience members in batches, like Meta/Google Customer Match APIs
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Mock Ad Platform")
audiences = {}   # audience name -> set of external IDs

class Batch(BaseModel):
    external_ids: list[str]

@app.post("/audiences/{name}/members")
def add_members(name: str, batch: Batch):
    if len(batch.external_ids) > 10000:
        raise HTTPException(status_code=400, detail="Max 10,000 IDs per request")
    audiences.setdefault(name, set()).update(batch.external_ids)
    return {"audience": name, "received": len(batch.external_ids), "total": len(audiences[name])}

@app.get("/audiences")
def list_audiences():
    return {name: len(ids) for name, ids in audiences.items()}