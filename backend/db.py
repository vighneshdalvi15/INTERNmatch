from __future__ import annotations

import os
from dataclasses import dataclass

from flask import Flask
from pymongo import MongoClient
from pymongo.collection import Collection


@dataclass(frozen=True)
class Db:
    client: MongoClient
    db_name: str

    @property
    def database(self):
        return self.client[self.db_name]

    @property
    def users(self) -> Collection:
        return self.database["users"]

    @property
    def student_profiles(self) -> Collection:
        return self.database["student_profiles"]

    @property
    def company_profiles(self) -> Collection:
        return self.database["company_profiles"]

    @property
    def jobs(self) -> Collection:
        return self.database["jobs"]

    @property
    def applications(self) -> Collection:
        return self.database["applications"]

    @property
    def courses(self) -> Collection:
        return self.database["courses"]

    @property
    def test_attempts(self) -> Collection:
        return self.database["test_attempts"]


def resolve_mongodb_uri() -> str:
    """Prefer MONGODB_URI; fall back to MONGO_URI for older .env files."""
    return (
        os.getenv("MONGODB_URI", "").strip()
        or os.getenv("MONGO_URI", "").strip()
        or "mongodb://127.0.0.1:27017"
    )


def resolve_mongodb_db() -> str:
    return (
        os.getenv("MONGODB_DB", "").strip()
        or os.getenv("MONGO_DB", "").strip()
        or "internmatch"
    )


def _client_options(uri: str) -> dict:
    """Atlas (mongodb+srv) needs longer timeouts than local Compass."""
    is_remote = uri.startswith("mongodb+srv://") or ".mongodb.net" in uri
    if is_remote:
        return {
            "serverSelectionTimeoutMS": 10000,
            "connectTimeoutMS": 10000,
            "socketTimeoutMS": 30000,
            "retryWrites": True,
            "maxPoolSize": 50,
        }
    return {
        "serverSelectionTimeoutMS": 3000,
        "connectTimeoutMS": 3000,
        "socketTimeoutMS": 20000,
        "retryWrites": True,
        "maxPoolSize": 20,
    }


def init_db(app: Flask) -> None:
    uri = app.config["MONGODB_URI"]
    name = app.config["MONGODB_DB"]
    client = MongoClient(uri, **_client_options(uri))
    app.extensions["db"] = Db(client=client, db_name=name)

    try:
        client.admin.command("ping")
        db = client[name]
        db["users"].create_index("email", unique=True)
        db["jobs"].create_index([("created_at", -1)])
        db["jobs"].create_index([("company_id", 1), ("created_at", -1)])
        db["jobs"].create_index("seed_key", unique=True, sparse=True)
        db["applications"].create_index([("job_id", 1), ("student_id", 1)], unique=True)
        db["courses"].create_index([("created_at", -1)])
        db["courses"].create_index("youtube_id", unique=True)
        db["courses"].create_index([("skills", 1)])
        db["test_attempts"].create_index([("user_id", 1), ("test_id", 1), ("created_at", -1)])
        db["student_profiles"].create_index("user_id", unique=True)
        db["company_profiles"].create_index("user_id", unique=True)
        app.extensions.pop("db_error", None)
    except Exception as e:
        # Keep app booting; surface in /api/health.
        app.extensions["db_error"] = str(e)


def get_db(app: Flask) -> Db:
    return app.extensions["db"]
