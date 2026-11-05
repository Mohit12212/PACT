"""Async client for any OpenAI-compatible local server (Ollama, BionicGPT, LM Studio, vLLM).

Every public helper degrades gracefully: callers always get (text, used_ai) so features keep working offline.
"""
import json, re

import httpx

from ..config import settings
from ..db import SessionLocal
from ..models import Setting

KEYS = ("base_url", "api_key", "model", "embed_model")


def get_cfg() -> dict:
    cfg = {"base_url": settings.llm_base_url, "api_key": settings.llm_api_key,
           "model": settings.llm_model, "embed_model": settings.llm_embed_model}
    with SessionLocal() as db:
        for s in db.query(Setting).all():
            if s.k in KEYS and s.v != "":
                cfg[s.k] = s.v
    return cfg


def _h(cfg):
    return {"Authorization": f"Bearer {cfg['api_key']}"} if cfg["api_key"] else {}


async def list_models(base: str | None = None, key: str | None = None) -> list[str]:
    cfg = get_cfg()
    base = (base or cfg["base_url"]).rstrip("/")
    h = {"Authorization": f"Bearer {key}"} if key else _h(cfg)
    async with httpx.AsyncClient(timeout=6) as c:
        try:
            r = await c.get(base + "/models", headers=h)
            r.raise_for_status()
            return sorted(m["id"] for m in r.json().get("data", []))
        except Exception:
            r = await c.get(re.sub(r"/v1$", "", base) + "/api/tags")
            r.raise_for_status()
            return sorted(m["name"] for m in r.json().get("models", []))


async def is_up() -> bool:
    try:
        return bool(await list_models())
    except Exception:
        return False


async def chat(prompt: str, system: str = "You are a helpful assistant for a partnership platform.",
               temp: float = 0.4, history: list | None = None) -> str:
    cfg = get_cfg()
    if not cfg["model"]:
        raise RuntimeError("No AI model selected. Open Settings to connect a local model.")
    msgs = [{"role": "system", "content": system}, *(history or []), {"role": "user", "content": prompt}]
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(cfg["base_url"].rstrip("/") + "/chat/completions", headers=_h(cfg),
                         json={"model": cfg["model"], "temperature": temp, "messages": msgs})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()


async def embed_texts(texts: list[str]) -> tuple[list[list[float]], str] | None:
    """Real embeddings if an embedding model is configured, else None (callers use the hashed fallback)."""
    cfg = get_cfg()
    if not cfg["embed_model"]:
        return None
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(cfg["base_url"].rstrip("/") + "/embeddings", headers=_h(cfg),
                             json={"model": cfg["embed_model"], "input": texts})
            r.raise_for_status()
            data = sorted(r.json()["data"], key=lambda d: d["index"])
            return [d["embedding"] for d in data], cfg["embed_model"]
    except Exception:
        return None


def parse_json(text: str):
    m = re.search(r"(\[.*\]|\{.*\})", text, re.S)
    return json.loads(m.group(1)) if m else None
