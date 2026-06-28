from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from backend.db import get_db
from backend.utils.mongo import parse_oid, serialize_doc
from backend.utils.validation import clip_list, clip_str, MAX_TEXT_LEN, split_skills


students_bp = Blueprint("students", __name__)

_ALLOWED_RESUME_PREFIX = "/api/uploads/resume/"


def _sanitize_resume_url(value) -> str:
    url = clip_str(value, 512)
    if not url:
        return ""
    if url.startswith(_ALLOWED_RESUME_PREFIX):
        return url
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return ""


def _require_student():
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "forbidden"}), 403
    return None


@students_bp.get("/me")
@jwt_required()
def get_me():
    denied = _require_student()
    if denied:
        return denied

    db = get_db(current_app)
    user_id = parse_oid(get_jwt_identity())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401
    prof = db.student_profiles.find_one({"user_id": user_id}) or {"user_id": user_id}
    return jsonify({"profile": serialize_doc(prof)})


@students_bp.put("/me")
@jwt_required()
def upsert_me():
    denied = _require_student()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    db = get_db(current_app)
    user_id = parse_oid(get_jwt_identity())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401
    now = datetime.now(timezone.utc)

    education = payload.get("education", {})
    preferences = payload.get("preferences", {})
    links = payload.get("links", {})
    if not isinstance(education, dict):
        education = {}
    if not isinstance(preferences, dict):
        preferences = {}
    if not isinstance(links, dict):
        links = {}

    doc = {
        "full_name": clip_str(payload.get("full_name")),
        "phone": clip_str(payload.get("phone"), 32),
        "education": {str(k)[:64]: clip_str(v) for k, v in list(education.items())[:20]},
        "skills": split_skills(payload.get("skills")),
        "projects": clip_list(payload.get("projects")),
        "experience": clip_str(payload.get("experience"), MAX_TEXT_LEN),
        "preferences": {str(k)[:64]: clip_str(v) for k, v in list(preferences.items())[:20]},
        "links": {str(k)[:64]: clip_str(v) for k, v in list(links.items())[:10]},
        "resume_url": _sanitize_resume_url(payload.get("resume_url")),
        "updated_at": now,
    }

    existing = db.student_profiles.find_one({"user_id": user_id})
    if existing:
        db.student_profiles.update_one({"_id": existing["_id"]}, {"$set": doc})
        prof = db.student_profiles.find_one({"_id": existing["_id"]})
    else:
        doc["user_id"] = user_id
        doc["created_at"] = now
        res = db.student_profiles.insert_one(doc)
        prof = db.student_profiles.find_one({"_id": res.inserted_id})

    return jsonify({"profile": serialize_doc(prof)})


@students_bp.get("/me/dashboard")
@jwt_required()
def dashboard():
    denied = _require_student()
    if denied:
        return denied

    db = get_db(current_app)
    user_id = parse_oid(get_jwt_identity())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401

    prof = db.student_profiles.find_one({"user_id": user_id}) or {}
    skills_known = len(prof.get("skills") or [])
    courses_watched = len(prof.get("courses_watched") or [])

    tests_given = db.test_attempts.count_documents({"user_id": user_id})
    internships_applied = db.applications.count_documents({"student_id": user_id})
    internships_completed = db.applications.count_documents({"student_id": user_id, "status": "selected"})

    return jsonify(
        {
            "stats": {
                "tests_given": tests_given,
                "internships_applied": internships_applied,
                "internships_completed": internships_completed,
                "courses_watched": courses_watched,
                "skills_known": skills_known,
            }
        }
    )
