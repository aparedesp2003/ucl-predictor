from functools import lru_cache

from sqlalchemy import Engine, create_engine

from engine.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().sqlalchemy_url, pool_pre_ping=True)
