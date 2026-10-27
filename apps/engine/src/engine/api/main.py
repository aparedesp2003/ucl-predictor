import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from engine.db import get_engine

logger = logging.getLogger(__name__)

app = FastAPI(title="UCL predictor engine")


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("health check failed")
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok"}
