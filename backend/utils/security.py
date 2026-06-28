from __future__ import annotations

import os
import time
from collections import defaultdict
from functools import wraps
from threading import Lock
from typing import Callable, Literal

from flask import jsonify, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from werkzeug.security import check_password_hash, generate_password_hash

Role = Literal["student", "company", "admin"]

_WEAK_SECRETS = frozenset(
    {
        "",
        "dev-secret",
        "dev-jwt-secret",
        "change-me",
        "change-me-too",
        "internmatch-jwt-secret-change-in-prod",
        "internmatch-flask-secret",
    }
)

_rate_lock = Lock()
_rate_buckets: dict[str, list[float]] = defaultdict(list)


def is_production() -> bool:
    env = os.getenv("FLASK_ENV", os.getenv("INTERNMATCH_ENV", "development")).lower()
    return env in ("production", "prod")


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def validate_runtime_secrets(secret_key: str, jwt_secret_key: str) -> None:
    if not is_production():
        return
    if secret_key in _WEAK_SECRETS or len(secret_key) < 32:
        raise RuntimeError("Set a strong SECRET_KEY (32+ chars) in production.")
    if jwt_secret_key in _WEAK_SECRETS or len(jwt_secret_key) < 32:
        raise RuntimeError("Set a strong JWT_SECRET_KEY (32+ chars) in production.")


def cors_origins() -> list[str] | str:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if not raw:
        return "*" if not is_production() else []
    return [o.strip() for o in raw.split(",") if o.strip()]


def rate_limit(max_calls: int, window_seconds: int, *, key_prefix: str = ""):
    """Simple in-memory rate limiter for auth and upload endpoints."""

    def decorator(fn: Callable):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            remote = request.remote_addr or "unknown"
            key = f"{key_prefix}:{remote}"
            now = time.time()
            with _rate_lock:
                bucket = [t for t in _rate_buckets[key] if now - t < window_seconds]
                if len(bucket) >= max_calls:
                    return jsonify({"error": "rate_limit_exceeded"}), 429
                bucket.append(now)
                _rate_buckets[key] = bucket
            return fn(*args, **kwargs)

        return wrapped

    return decorator


def require_roles(*roles: Role):
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            verify_jwt_in_request()
            if get_jwt().get("role") not in roles:
                return jsonify({"error": "forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapped

    return decorator
