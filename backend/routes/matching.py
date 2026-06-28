from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from backend.db import get_db
from backend.utils.mongo import parse_oid, serialize_doc
from backend.utils.validation import normalize_skill


matching_bp = Blueprint("matching", __name__)


def _recommend_for_skills(missing: list[str]) -> list[dict]:
    """
    Recommend courses from the platform's course catalog by matching course.skills.
    Falls back gracefully to empty list if catalog isn't available.
    """
    db = get_db(current_app)
    missing_norm = [normalize_skill(s) for s in (missing or []) if normalize_skill(s)]
    if not missing_norm:
        return []

    # Fetch a small set of candidate courses and rank them.
    candidates = list(db.courses.find({"skills": {"$in": missing_norm}}).limit(50))
    scored = []
    for c in candidates:
        cskills = {normalize_skill(s) for s in (c.get("skills") or []) if normalize_skill(s)}
        overlap = [s for s in missing_norm if s in cskills]
        if overlap:
            scored.append((len(overlap), overlap[0], c))

    scored.sort(key=lambda x: (-x[0], x[1]))
    recs = []
    seen = set()
    for _, matched_skill, c in scored[:10]:
        key = (c.get("title"), c.get("url"))
        if key in seen:
            continue
        seen.add(key)
        recs.append({"skill": matched_skill, "title": c.get("title"), "provider": c.get("provider"), "url": c.get("url"), "thumbnail_url": c.get("thumbnail_url"), "course_id": str(c.get("_id"))})
    return recs


def _match_score(student_skills: list[str], required: list[str], preferred: list[str]) -> tuple[int, list[str]]:
    ss = {normalize_skill(s) for s in (student_skills or []) if normalize_skill(s)}
    req = [normalize_skill(s) for s in (required or []) if normalize_skill(s)]
    pref = [normalize_skill(s) for s in (preferred or []) if normalize_skill(s)]

    missing = [s for s in req if s not in ss]
    req_hit = len(req) - len(missing)

    if not req:
        base = 60
    else:
        base = int((req_hit / max(1, len(req))) * 85)

    pref_hit = sum(1 for s in pref if s in ss)
    bonus = 0 if not pref else int((pref_hit / max(1, len(pref))) * 15)

    score = max(0, min(100, base + bonus))
    return score, missing


@matching_bp.get("/jobs/recommended")
@jwt_required()
def recommended_jobs():
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "forbidden"}), 403

    db = get_db(current_app)
    user_id = parse_oid(get_jwt_identity())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401
    prof = db.student_profiles.find_one({"user_id": user_id}) or {}
    student_skills = prof.get("skills", [])
    prefs = prof.get("preferences", {}) or {}

    preferred_role = normalize_skill(str(prefs.get("preferred_role", "") or ""))
    preferred_location = normalize_skill(str(prefs.get("preferred_location", "") or ""))
    preferred_type = normalize_skill(str(prefs.get("internship_type", "") or ""))

    jobs = list(db.jobs.find({"status": "open"}).sort("created_at", -1).limit(200))

    ranked = []
    for j in jobs:
        score, missing = _match_score(student_skills, j.get("required_skills", []), j.get("preferred_skills", []))

        # lightweight preference boosts
        title = normalize_skill(j.get("title", ""))
        loc = normalize_skill(j.get("location", ""))
        jtype = normalize_skill(j.get("type", ""))

        if preferred_role and preferred_role in title:
            score = min(100, score + 5)
        if preferred_location and (preferred_location in loc or preferred_location in normalize_skill(j.get("work_mode", ""))):
            score = min(100, score + 5)
        if preferred_type and preferred_type in jtype:
            score = min(100, score + 3)

        ranked.append(
            {
                "job": serialize_doc(j),
                "match": {
                    "score": score,
                    "missing_required_skills": missing,
                    "recommended_courses": _recommend_for_skills(missing),
                },
            }
        )

    ranked.sort(key=lambda x: x["match"]["score"], reverse=True)
    return jsonify({"items": ranked[:30]})


@matching_bp.get("/jobs/<job_id>")
@jwt_required()
def match_job(job_id: str):
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "forbidden"}), 403

    db = get_db(current_app)
    user_id = parse_oid(get_jwt_identity())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401
    prof = db.student_profiles.find_one({"user_id": user_id}) or {}
    student_skills = prof.get("skills", [])

    job_oid = parse_oid(job_id)
    if not job_oid:
        return jsonify({"error": "invalid_job_id"}), 400

    job = db.jobs.find_one({"_id": job_oid})
    if not job:
        return jsonify({"error": "not_found"}), 404

    score, missing = _match_score(student_skills, job.get("required_skills", []), job.get("preferred_skills", []))
    return jsonify(
        {
            "job": serialize_doc(job),
            "match": {
                "score": score,
                "missing_required_skills": missing,
                "recommended_courses": _recommend_for_skills(missing),
                "computed_at": datetime.now(timezone.utc).isoformat(),
            },
        }
    )

