from __future__ import annotations

import os
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from backend.db import get_db
from backend.utils.mongo import parse_oid, serialize_doc
from backend.utils.validation import clip_str, company_email_matches_website, domain_from_email, domain_from_website, is_valid_email, MAX_TEXT_LEN
from backend.utils.security import is_production


companies_bp = Blueprint("companies", __name__)

MIN_ABOUT_LEN = 40


def _require_company():
    claims = get_jwt()
    if claims.get("role") != "company":
        return jsonify({"error": "forbidden"}), 403
    return None


def _profile_missing_fields(prof: dict) -> list[str]:
    missing: list[str] = []
    if not str(prof.get("company_name", "")).strip():
        missing.append("company_name")
    if not str(prof.get("website", "")).strip():
        missing.append("website")
    if not str(prof.get("location", "")).strip():
        missing.append("location")
    if not str(prof.get("industry", "")).strip():
        missing.append("industry")
    if len(str(prof.get("about", "")).strip()) < MIN_ABOUT_LEN:
        missing.append("about")
    return missing


def _compute_verification(db, user_id, website: str, existing: dict | None) -> dict:
    """Auto-verify when login email domain matches company website domain."""
    if existing and existing.get("verification_status") == "manual_verified":
        return {"verification_status": "manual_verified", "verification_method": "admin"}

    user = db.users.find_one({"_id": user_id})
    email = str((user or {}).get("email", "") or "")
    website = str(website or "").strip()
    if not website:
        return {
            "verification_status": "unverified",
            "verification_method": None,
            "verification_note": "Add your company website to enable domain verification.",
        }

    if company_email_matches_website(email, website):
        return {
            "verification_status": "email_domain_match",
            "verification_method": "email_domain_match",
            "matched_login_domain": domain_from_email(email),
            "matched_website_domain": domain_from_website(website),
            "verification_note": "Verified: your account email domain matches your company website.",
        }

    return {
        "verification_status": "unverified",
        "verification_method": None,
        "verification_note": "Sign up and save your profile using a work email on the same domain as your website (not Gmail/Yahoo).",
    }


def posting_eligibility_payload(db, user_id) -> dict:
    prof = db.company_profiles.find_one({"user_id": user_id}) or {}
    missing = _profile_missing_fields(prof)
    profile_complete = len(missing) == 0
    vs = prof.get("verification_status") or "unverified"
    skip_verify = os.getenv("INTERNMATCH_SKIP_COMPANY_VERIFY", "0") == "1" and not is_production()
    verified_ok = skip_verify or vs in ("email_domain_match", "manual_verified")
    can_post = profile_complete and verified_ok
    reason = None
    if not profile_complete:
        reason = "incomplete_profile"
    elif not verified_ok:
        reason = "company_not_verified"

    return {
        "can_post": can_post,
        "reason": reason,
        "profile_complete": profile_complete,
        "missing_profile_fields": missing,
        "verification_status": vs,
        "verification_note": prof.get("verification_note"),
        "skip_verify_env": skip_verify,
    }


@companies_bp.get("/me")
@jwt_required()
def get_me():
    denied = _require_company()
    if denied:
        return denied

    db = get_db(current_app)
    user_id = parse_oid(get_jwt_identity())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401
    prof = db.company_profiles.find_one({"user_id": user_id}) or {"user_id": user_id}
    return jsonify({"profile": serialize_doc(prof), "posting": posting_eligibility_payload(db, user_id)})


@companies_bp.put("/me")
@jwt_required()
def upsert_me():
    denied = _require_company()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    db = get_db(current_app)
    user_id = parse_oid(get_jwt_identity())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401
    now = datetime.now(timezone.utc)

    links = payload.get("links", {})
    if not isinstance(links, dict):
        links = {}

    careers_email = clip_str(payload.get("careers_contact_email"), 254)
    if careers_email and not is_valid_email(careers_email):
        return jsonify({"error": "invalid_careers_contact_email"}), 400

    doc = {
        "company_name": clip_str(payload.get("company_name")),
        "website": clip_str(payload.get("website")),
        "location": clip_str(payload.get("location")),
        "about": clip_str(payload.get("about"), MAX_TEXT_LEN),
        "industry": clip_str(payload.get("industry")),
        "size": clip_str(payload.get("size"), 64),
        "linkedin_url": clip_str(payload.get("linkedin_url")),
        "careers_contact_email": careers_email,
        "links": {str(k)[:64]: clip_str(v) for k, v in list(links.items())[:10]},
        "updated_at": now,
    }

    existing = db.company_profiles.find_one({"user_id": user_id})
    ver = _compute_verification(db, user_id, doc.get("website", ""), existing)
    doc.update(ver)

    if existing:
        db.company_profiles.update_one({"_id": existing["_id"]}, {"$set": doc})
        prof = db.company_profiles.find_one({"_id": existing["_id"]})
    else:
        doc["user_id"] = user_id
        doc["created_at"] = now
        res = db.company_profiles.insert_one(doc)
        prof = db.company_profiles.find_one({"_id": res.inserted_id})

    return jsonify({"profile": serialize_doc(prof), "posting": posting_eligibility_payload(db, user_id)})


@companies_bp.get("/me/posting-eligibility")
@jwt_required()
def posting_eligibility():
    denied = _require_company()
    if denied:
        return denied
    db = get_db(current_app)
    user_id = parse_oid(get_jwt_identity())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401
    return jsonify(posting_eligibility_payload(db, user_id))

