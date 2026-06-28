from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_EMAIL_LEN = 254
MAX_PASSWORD_LEN = 128
MAX_TITLE_LEN = 200
MAX_SHORT_LEN = 500
MAX_TEXT_LEN = 10000
MAX_LIST_ITEMS = 50


def require_fields(payload: dict[str, Any], fields: list[str]) -> list[str]:
    missing: list[str] = []
    for f in fields:
        v = payload.get(f)
        if v is None or (isinstance(v, str) and not v.strip()):
            missing.append(f)
    return missing


def clip_str(value: Any, max_len: int = MAX_SHORT_LEN) -> str:
    return str(value or "")[:max_len].strip()


def clip_list(value: Any, max_items: int = MAX_LIST_ITEMS) -> list:
    if not isinstance(value, list):
        return []
    return value[:max_items]


def is_valid_email(email: str) -> bool:
    e = (email or "").strip()
    if len(e) > MAX_EMAIL_LEN:
        return False
    return bool(EMAIL_RE.match(e))


def is_strong_password(password: str) -> bool:
    p = password or ""
    if len(p) < 8 or len(p) > MAX_PASSWORD_LEN:
        return False
    has_alpha = any(c.isalpha() for c in p)
    has_digit = any(c.isdigit() for c in p)
    return has_alpha and has_digit


def normalize_skill(skill: str) -> str:
    return re.sub(r"\s+", " ", (skill or "").strip()).lower()


def split_skills(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value).split(",")
    out: list[str] = []
    for s in raw:
        ns = normalize_skill(str(s))
        if ns and ns not in out:
            out.append(ns)
    return out


# Public email domains — cannot be used for company website↔email verification.
_PUBLIC_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.in",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "icloud.com",
        "protonmail.com",
        "proton.me",
        "aol.com",
        "rediffmail.com",
    }
)


def domain_from_email(email: str) -> str:
    e = (email or "").strip().lower()
    if "@" not in e:
        return ""
    return e.split("@", 1)[1].strip()


def domain_from_website(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if not u.lower().startswith(("http://", "https://")):
        u = "https://" + u
    try:
        parsed = urlparse(u)
        host = (parsed.netloc or parsed.path or "").lower()
        if host.startswith("www."):
            host = host[4:]
        if "/" in host:
            host = host.split("/")[0]
        if ":" in host:
            host = host.split(":")[0]
        return host
    except Exception:
        return ""


def company_email_matches_website(login_email: str, company_website: str) -> bool:
    """
    True if the user's work email domain matches the company website host
    (e.g. user@acme.com vs https://careers.acme.com).
    """
    ed = domain_from_email(login_email)
    wd = domain_from_website(company_website)
    if not ed or not wd:
        return False
    if ed in _PUBLIC_EMAIL_DOMAINS:
        return False
    if ed == wd:
        return True
    # Subdomain: jobs.acme.com vs acme.com
    if ed.endswith("." + wd) or wd.endswith("." + ed):
        return True
    return False

