from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from backend.db import get_db
from backend.utils.mongo import parse_oid, serialize_doc
from backend.utils.validation import clip_str, MAX_TEXT_LEN


applications_bp = Blueprint("applications", __name__)

ALLOWED_STATUSES = frozenset({"submitted", "under_review", "shortlisted", "rejected", "selected"})


@applications_bp.post("")
@jwt_required()
def apply():
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    job_id_raw = payload.get("job_id")
    if not job_id_raw:
        return jsonify({"error": "missing_fields", "fields": ["job_id"]}), 400

    job_oid = parse_oid(str(job_id_raw))
    if not job_oid:
        return jsonify({"error": "invalid_job_id"}), 400

    db = get_db(current_app)
    student_id = parse_oid(get_jwt_identity())
    if not student_id:
        return jsonify({"error": "invalid_token"}), 401

    job = db.jobs.find_one({"_id": job_oid})
    if not job or job.get("status") != "open":
        return jsonify({"error": "job_not_available"}), 400

    now = datetime.now(timezone.utc)
    doc = {
        "job_id": job["_id"],
        "company_id": job["company_id"],
        "student_id": student_id,
        "status": "submitted",
        "cover_note": clip_str(payload.get("cover_note"), MAX_TEXT_LEN),
        "created_at": now,
        "updated_at": now,
    }

    try:
        res = db.applications.insert_one(doc)
    except Exception:
        return jsonify({"error": "already_applied"}), 409

    app_doc = db.applications.find_one({"_id": res.inserted_id})
    return jsonify({"application": serialize_doc(app_doc)}), 201


@applications_bp.get("/mine")
@jwt_required()
def mine():
    claims = get_jwt()
    db = get_db(current_app)
    user_id = parse_oid(get_jwt_identity())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401

    if claims.get("role") == "student":
        items = [serialize_doc(d) for d in db.applications.find({"student_id": user_id}).sort("created_at", -1).limit(200)]
        return jsonify({"items": items})

    if claims.get("role") == "company":
        items = [serialize_doc(d) for d in db.applications.find({"company_id": user_id}).sort("created_at", -1).limit(200)]
        return jsonify({"items": items})

    return jsonify({"error": "forbidden"}), 403


@applications_bp.put("/<app_id>")
@jwt_required()
def update_status(app_id: str):
    claims = get_jwt()
    if claims.get("role") != "company":
        return jsonify({"error": "forbidden"}), 403

    app_oid = parse_oid(app_id)
    if not app_oid:
        return jsonify({"error": "invalid_application_id"}), 400

    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    if status not in ALLOWED_STATUSES:
        return jsonify({"error": "invalid_status"}), 400

    db = get_db(current_app)
    company_id = parse_oid(get_jwt_identity())
    if not company_id:
        return jsonify({"error": "invalid_token"}), 401

    existing = db.applications.find_one({"_id": app_oid})
    if not existing:
        return jsonify({"error": "not_found"}), 404
    if existing.get("company_id") != company_id:
        return jsonify({"error": "forbidden"}), 403

    now = datetime.now(timezone.utc)
    db.applications.update_one({"_id": existing["_id"]}, {"$set": {"status": status, "updated_at": now}})
    updated = db.applications.find_one({"_id": existing["_id"]})
    return jsonify({"application": serialize_doc(updated)})
