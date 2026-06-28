from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from backend.db import get_db
from backend.routes.companies import posting_eligibility_payload
from backend.utils.mongo import parse_oid, serialize_doc
from backend.utils.validation import clip_str, MAX_SHORT_LEN, MAX_TEXT_LEN, MAX_TITLE_LEN, require_fields, split_skills


jobs_bp = Blueprint("jobs", __name__)

JOB_STATUSES = frozenset({"open", "closed", "draft"})
WORK_MODES = frozenset({"Remote", "Hybrid", "Onsite"})
JOB_TYPES = frozenset({"internship", "full-time", "part-time"})


def _seed_demo_jobs_if_needed() -> None:
    db = get_db(current_app)
    # Ensure at least 10 demo jobs exist. Uses upsert on seed_key to avoid duplicates.
    existing_demo = db.jobs.count_documents({"seed_key": {"$exists": True}})
    if existing_demo >= 10:
        return

    now = datetime.now(timezone.utc)
    seed = [
        {
            "seed_key": "demo_microsoft_data_science_intern",
            "company_id": None,
            "company_name": "Microsoft",
            "title": "Data Science Intern",
            "description": "Work with data pipelines, exploratory analysis, and model prototyping. Collaborate with engineering to deploy insights.",
            "required_skills": split_skills(["python", "sql", "data analysis"]),
            "preferred_skills": split_skills(["machine learning", "pandas", "numpy"]),
            "stipend_salary": "₹25,000 / month",
            "location": "Hyderabad",
            "work_mode": "Hybrid",
            "duration": "3 months",
            "eligibility": "Any UG/PG student with strong Python fundamentals and basic SQL.",
            "deadline": "2026-05-15",
            "responsibilities": [
                "Clean and preprocess datasets",
                "Build dashboards and reports",
                "Assist in model evaluation and experimentation",
            ],
            "type": "internship",
            "status": "open",
            "created_at": now,
            "updated_at": now,
        },
        {
            "seed_key": "demo_google_frontend_intern",
            "company_id": None,
            "company_name": "Google",
            "title": "Software Engineering Intern (Frontend)",
            "description": "Build user-facing features with modern frontend best practices, performance optimization, and accessible UI components.",
            "required_skills": split_skills(["javascript", "react", "html", "css"]),
            "preferred_skills": split_skills(["typescript", "testing", "web performance"]),
            "stipend_salary": "₹30,000 / month",
            "location": "Remote",
            "work_mode": "Remote",
            "duration": "4 months",
            "eligibility": "Strong fundamentals in JS + React. Bonus for TypeScript and testing experience.",
            "deadline": "2026-05-30",
            "responsibilities": [
                "Implement responsive UI components",
                "Integrate APIs and handle client-side state",
                "Write unit tests for key flows",
            ],
            "type": "internship",
            "status": "open",
            "created_at": now,
            "updated_at": now,
        },
        {
            "seed_key": "demo_amazon_backend_flask_mongo",
            "company_id": None,
            "company_name": "Amazon",
            "title": "Backend Intern (Flask + MongoDB)",
            "description": "Design REST APIs, implement authentication, and build scalable data models in MongoDB.",
            "required_skills": split_skills(["python", "flask", "mongodb", "rest api"]),
            "preferred_skills": split_skills(["docker", "aws", "jwt"]),
            "stipend_salary": "₹28,000 / month",
            "location": "Bengaluru",
            "work_mode": "Onsite",
            "duration": "3 months",
            "eligibility": "Comfortable with building APIs and working with NoSQL databases.",
            "deadline": "2026-06-05",
            "responsibilities": [
                "Build and document REST endpoints",
                "Implement data validation and auth",
                "Support basic monitoring/logging for APIs",
            ],
            "type": "internship",
            "status": "open",
            "created_at": now,
            "updated_at": now,
        },
        {
            "seed_key": "demo_netflix_fullstack_intern",
            "company_id": None,
            "company_name": "Netflix",
            "title": "Full Stack Development Intern",
            "description": "Build end-to-end product features across frontend and backend, focusing on performance and reliability.",
            "required_skills": split_skills(["javascript", "react", "node.js", "rest api"]),
            "preferred_skills": split_skills(["mongodb", "typescript", "testing"]),
            "stipend_salary": "₹32,000 / month",
            "location": "Mumbai",
            "work_mode": "Hybrid",
            "duration": "4 months",
            "eligibility": "Good grasp of React + Node.js fundamentals and REST APIs.",
            "deadline": "2026-06-12",
            "responsibilities": [
                "Implement features across frontend and backend",
                "Write clean, testable code",
                "Collaborate with designers and engineers",
            ],
            "type": "internship",
            "status": "open",
            "created_at": now,
            "updated_at": now,
        },
        {
            "seed_key": "demo_adobe_uiux_intern",
            "company_id": None,
            "company_name": "Adobe",
            "title": "UI/UX Design Intern",
            "description": "Create user flows, wireframes, and high-fidelity prototypes for a modern web platform.",
            "required_skills": split_skills(["ui/ux", "figma", "communication"]),
            "preferred_skills": split_skills(["prototyping", "design systems"]),
            "stipend_salary": "₹20,000 / month",
            "location": "Pune",
            "work_mode": "Onsite",
            "duration": "3 months",
            "eligibility": "Portfolio with at least 2 case studies and strong design fundamentals.",
            "deadline": "2026-05-28",
            "responsibilities": [
                "Design wireframes and prototypes",
                "Run quick user feedback sessions",
                "Collaborate with frontend team for handoff",
            ],
            "type": "internship",
            "status": "open",
            "created_at": now,
            "updated_at": now,
        },
        {
            "seed_key": "demo_meta_ml_intern",
            "company_id": None,
            "company_name": "Meta",
            "title": "Machine Learning Intern",
            "description": "Work on model training/evaluation and help improve recommendation quality with experimentation.",
            "required_skills": split_skills(["python", "machine learning", "data analysis"]),
            "preferred_skills": split_skills(["deep learning", "pytorch", "sql"]),
            "stipend_salary": "₹35,000 / month",
            "location": "Remote",
            "work_mode": "Remote",
            "duration": "4 months",
            "eligibility": "Strong ML fundamentals and ability to work with messy datasets.",
            "deadline": "2026-06-20",
            "responsibilities": [
                "Train and evaluate models",
                "Perform feature engineering",
                "Document experiments and results",
            ],
            "type": "internship",
            "status": "open",
            "created_at": now,
            "updated_at": now,
        },
        {
            "seed_key": "demo_spotify_python_intern",
            "company_id": None,
            "company_name": "Spotify",
            "title": "Python Development Intern",
            "description": "Build internal automation tools and small services using Python with clean APIs and integrations.",
            "required_skills": split_skills(["python", "rest api", "git"]),
            "preferred_skills": split_skills(["flask", "docker", "testing"]),
            "stipend_salary": "₹22,000 / month",
            "location": "Bengaluru",
            "work_mode": "Hybrid",
            "duration": "3 months",
            "eligibility": "Comfortable building small Python services and writing maintainable code.",
            "deadline": "2026-06-01",
            "responsibilities": [
                "Build Python scripts/services",
                "Integrate with third-party APIs",
                "Write basic tests and docs",
            ],
            "type": "internship",
            "status": "open",
            "created_at": now,
            "updated_at": now,
        },
        {
            "seed_key": "demo_unilever_digital_marketing",
            "company_id": None,
            "company_name": "Unilever",
            "title": "Digital Marketing Intern",
            "description": "Support campaign planning, analytics, and content performance reporting across channels.",
            "required_skills": split_skills(["communication", "data analysis", "problem solving"]),
            "preferred_skills": split_skills(["seo", "content writing"]),
            "stipend_salary": "₹15,000 / month",
            "location": "Delhi",
            "work_mode": "Onsite",
            "duration": "2 months",
            "eligibility": "Strong writing and analytical mindset; interest in marketing.",
            "deadline": "2026-05-22",
            "responsibilities": [
                "Assist with campaign calendars",
                "Track performance metrics and KPIs",
                "Create weekly reports and insights",
            ],
            "type": "internship",
            "status": "open",
            "created_at": now,
            "updated_at": now,
        },
        {
            "seed_key": "demo_byjus_content_writing",
            "company_id": None,
            "company_name": "BYJU'S",
            "title": "Content Writing Intern",
            "description": "Create clear learning content and short articles for students; collaborate with subject experts.",
            "required_skills": split_skills(["content writing", "communication"]),
            "preferred_skills": split_skills(["research", "editing"]),
            "stipend_salary": "₹12,000 / month",
            "location": "Remote",
            "work_mode": "Remote",
            "duration": "2 months",
            "eligibility": "Excellent writing skills and ability to explain concepts clearly.",
            "deadline": "2026-05-18",
            "responsibilities": [
                "Write and edit learning content",
                "Proofread and maintain consistency",
                "Incorporate reviewer feedback quickly",
            ],
            "type": "internship",
            "status": "open",
            "created_at": now,
            "updated_at": now,
        },
        {
            "seed_key": "demo_pixar_video_editing",
            "company_id": None,
            "company_name": "Pixar",
            "title": "Video Editing Intern",
            "description": "Edit short-form videos for social and product storytelling with attention to pacing and clarity.",
            "required_skills": split_skills(["video editing", "canva", "communication"]),
            "preferred_skills": split_skills(["photoshop", "storytelling"]),
            "stipend_salary": "₹18,000 / month",
            "location": "Chennai",
            "work_mode": "Hybrid",
            "duration": "3 months",
            "eligibility": "Portfolio of edits (reels/shorts) preferred.",
            "deadline": "2026-06-08",
            "responsibilities": [
                "Edit short-form videos",
                "Add captions and basic motion elements",
                "Work with feedback and deliver quickly",
            ],
            "type": "internship",
            "status": "open",
            "created_at": now,
            "updated_at": now,
        },
    ]

    for j in seed:
        key = j.get("seed_key")
        db.jobs.update_one({"seed_key": key}, {"$setOnInsert": j}, upsert=True)


@jobs_bp.before_app_request
def ensure_demo_jobs_seeded():
    if current_app.extensions.get("_seeded_jobs"):
        return
    try:
        _seed_demo_jobs_if_needed()
        current_app.extensions["_seeded_jobs"] = True
    except Exception:
        pass


@jobs_bp.get("")
def list_jobs():
    db = get_db(current_app)
    q: dict = {"status": "open"}
    items = [serialize_doc(d) for d in db.jobs.find(q).sort("created_at", -1).limit(200)]
    return jsonify({"items": items})


@jobs_bp.get("/mine")
@jwt_required()
def list_my_jobs():
    claims = get_jwt()
    if claims.get("role") != "company":
        return jsonify({"error": "forbidden"}), 403

    db = get_db(current_app)
    company_user_id = parse_oid(get_jwt_identity())
    if not company_user_id:
        return jsonify({"error": "invalid_token"}), 401
    items = [serialize_doc(d) for d in db.jobs.find({"company_id": company_user_id}).sort("created_at", -1).limit(200)]
    return jsonify({"items": items})


@jobs_bp.get("/<job_id>")
def get_job(job_id: str):
    job_oid = parse_oid(job_id)
    if not job_oid:
        return jsonify({"error": "invalid_job_id"}), 400
    db = get_db(current_app)
    job = db.jobs.find_one({"_id": job_oid})
    if not job:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"job": serialize_doc(job)})


@jobs_bp.post("")
@jwt_required()
def create_job():
    claims = get_jwt()
    if claims.get("role") != "company":
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    missing = require_fields(
        payload,
        ["title", "description", "required_skills", "stipend_salary", "hours_per_week", "duration", "location"],
    )
    if missing:
        return jsonify({"error": "missing_fields", "fields": missing}), 400

    db = get_db(current_app)
    company_user_id = parse_oid(get_jwt_identity())
    if not company_user_id:
        return jsonify({"error": "invalid_token"}), 401

    pe = posting_eligibility_payload(db, company_user_id)
    if not pe["can_post"]:
        return jsonify({"error": pe.get("reason", "cannot_post"), "posting": pe}), 403

    now = datetime.now(timezone.utc)

    company_profile = db.company_profiles.find_one({"user_id": company_user_id}) or {}
    company_name = str(company_profile.get("company_name") or "").strip()

    openings_raw = str(payload.get("openings", "1")).strip()
    try:
        openings = max(1, min(50, int(openings_raw)))
    except ValueError:
        openings = 1

    work_mode = str(payload.get("work_mode", "Remote")).strip()
    if work_mode not in WORK_MODES:
        work_mode = "Remote"
    job_type = str(payload.get("type", "internship")).strip()
    if job_type not in JOB_TYPES:
        job_type = "internship"

    doc = {
        "company_id": company_user_id,
        "company_name": company_name,
        "title": clip_str(payload.get("title"), MAX_TITLE_LEN),
        "description": clip_str(payload.get("description"), MAX_TEXT_LEN),
        "required_skills": split_skills(payload.get("required_skills")),
        "preferred_skills": split_skills(payload.get("preferred_skills")),
        "stipend_salary": clip_str(payload.get("stipend_salary")),
        "location": clip_str(payload.get("location")),
        "work_mode": work_mode,
        "duration": clip_str(payload.get("duration")),
        "eligibility": clip_str(payload.get("eligibility"), MAX_TEXT_LEN),
        "deadline": clip_str(payload.get("deadline"), 32),
        "responsibilities": payload.get("responsibilities", [])[:20] if isinstance(payload.get("responsibilities"), list) else [],
        "type": job_type,
        "department": clip_str(payload.get("department")),
        "hours_per_week": clip_str(payload.get("hours_per_week"), 32),
        "openings": openings,
        "start_date": clip_str(payload.get("start_date"), 32),
        "perks": clip_str(payload.get("perks"), MAX_TEXT_LEN),
        "role_contact_email": clip_str(payload.get("role_contact_email"), 254),
        "status": "open",
        "created_at": now,
        "updated_at": now,
    }
    res = db.jobs.insert_one(doc)
    job = db.jobs.find_one({"_id": res.inserted_id})
    return jsonify({"job": serialize_doc(job)}), 201


@jobs_bp.put("/<job_id>")
@jwt_required()
def update_job(job_id: str):
    claims = get_jwt()
    if claims.get("role") != "company":
        return jsonify({"error": "forbidden"}), 403

    job_oid = parse_oid(job_id)
    if not job_oid:
        return jsonify({"error": "invalid_job_id"}), 400

    db = get_db(current_app)
    company_user_id = parse_oid(get_jwt_identity())
    if not company_user_id:
        return jsonify({"error": "invalid_token"}), 401

    existing = db.jobs.find_one({"_id": job_oid})
    if not existing:
        return jsonify({"error": "not_found"}), 404
    if existing.get("company_id") != company_user_id:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    now = datetime.now(timezone.utc)
    update = {"updated_at": now}

    text_fields = {
        "title": MAX_TITLE_LEN,
        "description": MAX_TEXT_LEN,
        "stipend_salary": MAX_SHORT_LEN,
        "location": MAX_SHORT_LEN,
        "duration": MAX_SHORT_LEN,
        "eligibility": MAX_TEXT_LEN,
        "deadline": 32,
        "department": MAX_SHORT_LEN,
        "hours_per_week": 32,
        "start_date": 32,
        "perks": MAX_TEXT_LEN,
        "role_contact_email": 254,
    }
    for k, max_len in text_fields.items():
        if k in payload:
            update[k] = clip_str(payload.get(k), max_len)
    if "work_mode" in payload:
        wm = str(payload.get("work_mode", "")).strip()
        if wm in WORK_MODES:
            update["work_mode"] = wm
    if "type" in payload:
        jt = str(payload.get("type", "")).strip()
        if jt in JOB_TYPES:
            update["type"] = jt
    if "status" in payload:
        st = str(payload.get("status", "")).strip()
        if st in JOB_STATUSES:
            update["status"] = st
    if "openings" in payload:
        try:
            update["openings"] = max(1, min(50, int(str(payload.get("openings")).strip())))
        except ValueError:
            pass
    if "required_skills" in payload:
        update["required_skills"] = split_skills(payload.get("required_skills"))
    if "preferred_skills" in payload:
        update["preferred_skills"] = split_skills(payload.get("preferred_skills"))
    if "responsibilities" in payload and isinstance(payload.get("responsibilities"), list):
        update["responsibilities"] = payload.get("responsibilities")[:20]

    db.jobs.update_one({"_id": existing["_id"]}, {"$set": update})
    job = db.jobs.find_one({"_id": existing["_id"]})
    return jsonify({"job": serialize_doc(job)})

