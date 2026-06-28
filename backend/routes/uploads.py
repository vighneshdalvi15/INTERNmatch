from __future__ import annotations

import os
import uuid

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from werkzeug.utils import secure_filename

from backend.db import get_db
from backend.utils.mongo import parse_oid
from backend.utils.security import rate_limit


uploads_bp = Blueprint("uploads", __name__)

ALLOWED_EXT = frozenset({"pdf", "doc", "docx"})


def _ext(filename: str) -> str:
    return (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()


def _safe_upload_name(original: str) -> str:
    ext = _ext(original)
    token = uuid.uuid4().hex
    return f"{token}.{ext}" if ext else token


def _is_safe_filename(name: str) -> bool:
    if not name or ".." in name or "/" in name or "\\" in name:
        return False
    base = secure_filename(name)
    return base == name and bool(base)


@uploads_bp.post("/resume")
@jwt_required()
@rate_limit(10, 60, key_prefix="upload_resume")
def upload_resume():
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "forbidden"}), 403

    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "missing_file"}), 400

    ext = _ext(f.filename)
    if ext not in ALLOWED_EXT:
        return jsonify({"error": "invalid_file_type", "allowed": sorted(ALLOWED_EXT)}), 400

    upload_dir = current_app.config["UPLOAD_DIR"]
    name = _safe_upload_name(f.filename)
    path = os.path.join(upload_dir, name)
    f.save(path)

    url = f"/api/uploads/resume/{name}"
    return jsonify({"url": url, "filename": name})


@uploads_bp.get("/resume/<filename>")
@jwt_required()
def download_resume(filename: str):
    if not _is_safe_filename(filename):
        return jsonify({"error": "invalid_filename"}), 400

    ext = _ext(filename)
    if ext not in ALLOWED_EXT:
        return jsonify({"error": "invalid_file_type"}), 400

    claims = get_jwt()
    user_id = parse_oid(get_jwt_identity())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401

    db = get_db(current_app)
    expected_url = f"/api/uploads/resume/{filename}"

    if claims.get("role") == "student":
        prof = db.student_profiles.find_one({"user_id": user_id}) or {}
        if prof.get("resume_url") != expected_url:
            return jsonify({"error": "forbidden"}), 403
    elif claims.get("role") == "company":
        # Company may view resumes only for students who applied to their jobs.
        student = db.student_profiles.find_one({"resume_url": expected_url})
        if not student:
            return jsonify({"error": "not_found"}), 404
        applied = db.applications.find_one({"student_id": student["user_id"], "company_id": user_id})
        if not applied:
            return jsonify({"error": "forbidden"}), 403
    else:
        return jsonify({"error": "forbidden"}), 403

    upload_dir = current_app.config["UPLOAD_DIR"]
    path = os.path.join(upload_dir, filename)
    if not os.path.isfile(path):
        return jsonify({"error": "not_found"}), 404

    return send_from_directory(upload_dir, filename, as_attachment=False, download_name=secure_filename(filename))
