"""
Flask application factory for InternMatch.

Creates the Flask app, loads environment configuration, initializes MongoDB,
registers API blueprints, and serves the single-page frontend.
"""

import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from backend.db import get_db, init_db, resolve_mongodb_db, resolve_mongodb_uri
from backend.routes.auth import auth_bp
from backend.routes.students import students_bp
from backend.routes.companies import companies_bp
from backend.routes.jobs import jobs_bp
from backend.routes.applications import applications_bp
from backend.routes.matching import matching_bp
from backend.routes.courses import courses_bp
from backend.routes.tests import tests_bp
from backend.routes.uploads import uploads_bp
from backend.utils.security import cors_origins, is_production, validate_runtime_secrets


def create_app() -> Flask:
    load_dotenv()

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    secret_key = os.getenv("SECRET_KEY", "dev-secret")
    jwt_secret_key = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
    validate_runtime_secrets(secret_key, jwt_secret_key)

    app.config["SECRET_KEY"] = secret_key
    app.config["JWT_SECRET_KEY"] = jwt_secret_key
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(seconds=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", str(60 * 60 * 12))))
    app.config["DEBUG"] = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")

    app.config["MONGODB_URI"] = resolve_mongodb_uri()
    app.config["MONGODB_DB"] = resolve_mongodb_db()

    upload_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
    os.makedirs(upload_dir, exist_ok=True)
    app.config["UPLOAD_DIR"] = upload_dir
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))

    origins = cors_origins()
    if is_production() and not origins:
        raise RuntimeError("Set CORS_ORIGINS in production (comma-separated allowed origins).")
    CORS(app, resources={r"/api/*": {"origins": origins}}, supports_credentials=True)
    JWTManager(app)

    init_db(app)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(students_bp, url_prefix="/api/students")
    app.register_blueprint(companies_bp, url_prefix="/api/companies")
    app.register_blueprint(jobs_bp, url_prefix="/api/jobs")
    app.register_blueprint(applications_bp, url_prefix="/api/applications")
    app.register_blueprint(matching_bp, url_prefix="/api/match")
    app.register_blueprint(courses_bp, url_prefix="/api/courses")
    app.register_blueprint(tests_bp, url_prefix="/api/tests")
    app.register_blueprint(uploads_bp, url_prefix="/api/uploads")

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if is_production():
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(_e):
        return jsonify({"error": "payload_too_large"}), 413

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify({"error": e.name.lower().replace(" ", "_"), "message": e.description}), e.code
        return e

    @app.errorhandler(Exception)
    def handle_unexpected_error(e: Exception):
        if request.path.startswith("/api/"):
            if app.config.get("DEBUG"):
                return jsonify({"error": "internal_error", "message": str(e)}), 500
            return jsonify({"error": "internal_error"}), 500
        raise e

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        try:
            db = get_db(app)
            db.client.admin.command("ping")
            app.extensions.pop("db_error", None)
            payload = {"ok": True, "db": "connected"}
            if not is_production():
                payload["uri_scheme"] = app.config["MONGODB_URI"].split("://", 1)[0]
            return jsonify(payload)
        except Exception as e:
            app.extensions["db_error"] = str(e)
            body = {"ok": False, "db": "disconnected"}
            if not is_production():
                body["error"] = str(e)
            return jsonify(body), 503

    return app
