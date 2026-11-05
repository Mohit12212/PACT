"""PACT: Partnership Intelligence application entry point."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, engine
from .routers import ai, auth, matches, orgs, partnerships, system
from .security import read_token
from .seed import seed
from .services.realtime import hub

STATIC = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    await seed()
    yield


app = FastAPI(title="PACT Partnership Intelligence API", version="2.0.0", lifespan=lifespan,
              description="A collaboration operating system for SDG 17: partner discovery, shared delivery and impact reporting.")
for r in (auth, orgs, matches, partnerships, ai, system):
    app.include_router(r.router)


@app.get("/api/health", tags=["system"])
def health():
    return {"ok": True, "version": app.version}


@app.exception_handler(500)
async def boom(_: Request, exc):
    return JSONResponse({"detail": "Something went wrong on our side. Try again."}, status_code=500)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str = ""):
    uid = read_token(token)
    if not uid:
        await ws.close(code=4401)
        return
    await hub.connect(uid, ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive pings from the client
    except WebSocketDisconnect:
        hub.disconnect(uid, ws)


app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return FileResponse(STATIC / "index.html")
