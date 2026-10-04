from fastapi import FastAPI
from app.api.v1 import router
from app.modules.queues.load import marker_for
app=FastAPI(title="Queue Manager API",version="0.2.0")
app.include_router(router,prefix="/api/v1")
@app.get("/health")
async def health(): return {"status":"ok"}
@app.get("/api/v1/queue/load-preview")
async def load_preview():
    counts=[0,2,5,8,15,20]
    return [{"queue_count":n,"level":marker_for(n,counts).level,"label":marker_for(n,counts).label} for n in counts]
