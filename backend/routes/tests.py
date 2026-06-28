from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from backend.db import get_db
from backend.utils.mongo import parse_oid, serialize_doc


tests_bp = Blueprint("tests", __name__)

VALID_TEST_IDS = frozenset({"python", "mern"})

TESTS = {
    "python": {
        "title": "Python Test",
        "duration_seconds": 15 * 60,
        "marks_per_question": 3,
        "questions": [
            {
                "id": "py1",
                "q": "What is the output of: print(type([]) is list)?",
                "choices": ["True", "False", "list", "<class 'list'>"],
                "answer_index": 0,
            },
            {
                "id": "py2",
                "q": "Which data structure is best for fast membership tests?",
                "choices": ["list", "tuple", "set", "dict (values)"],
                "answer_index": 2,
            },
            {
                "id": "py3",
                "q": "What does 'with open(...) as f:' guarantee?",
                "choices": ["File is encrypted", "File is closed even on errors", "File is global", "File is cached"],
                "answer_index": 1,
            },
            {
                "id": "py4",
                "q": "What is a correct way to create a virtual environment?",
                "choices": ["python -m venv .venv", "pip venv .venv", "venv install", "python install venv"],
                "answer_index": 0,
            },
            {
                "id": "py5",
                "q": "What does list.sort() return?",
                "choices": ["A new sorted list", "None", "True/False", "An iterator"],
                "answer_index": 1,
            },
            {
                "id": "py6",
                "q": "Which statement about Python functions is true?",
                "choices": ["They cannot be passed as arguments", "They are first-class objects", "They must be declared in classes", "They cannot return functions"],
                "answer_index": 1,
            },
            {
                "id": "py7",
                "q": "In Python, what is the time complexity of dict key lookup on average?",
                "choices": ["O(n)", "O(log n)", "O(1)", "O(n log n)"],
                "answer_index": 2,
            },
            {
                "id": "py8",
                "q": "What is the output of: 'a,b=1,2; print(a,b)'?",
                "choices": ["12", "1 2", "(1,2)", "Error"],
                "answer_index": 1,
            },
            {
                "id": "py9",
                "q": "What does `__name__ == \"__main__\"` indicate?",
                "choices": ["Module is imported", "Running as the main script", "Python version", "Thread name"],
                "answer_index": 1,
            },
            {
                "id": "py10",
                "q": "Which creates a generator?",
                "choices": ["[x for x in range(5)]", "(x for x in range(5))", "{x for x in range(5)}", "{x:x for x in range(5)}"],
                "answer_index": 1,
            },
            {
                "id": "py11",
                "q": "What will `len({1,1,2})` return?",
                "choices": ["3", "2", "1", "Error"],
                "answer_index": 1,
            },
            {
                "id": "py12",
                "q": "Which is true about exceptions?",
                "choices": ["They cannot be re-raised", "They can be caught and handled", "They stop the OS", "They only occur in I/O"],
                "answer_index": 1,
            },
            {
                "id": "py13",
                "q": "What does `enumerate(['a','b'])` provide?",
                "choices": ["Only items", "Only indices", "Index-item pairs", "Sorted items"],
                "answer_index": 2,
            },
            {
                "id": "py14",
                "q": "Which statement about `==` vs `is` is correct?",
                "choices": ["Both compare identity", "`is` compares identity, `==` compares value", "`==` compares identity", "Neither exists"],
                "answer_index": 1,
            },
            {
                "id": "py15",
                "q": "What is the result of: bool('False') ?",
                "choices": ["False", "True", "Error", "None"],
                "answer_index": 1,
            },
        ],
    },
    "mern": {
        "title": "Web Development (MERN Stack) Test",
        "duration_seconds": 15 * 60,
        "marks_per_question": 3,
        "questions": [
            {"id": "m1", "q": "In MERN, what does the 'E' stand for?", "choices": ["Elixir", "Express", "EJS", "Edge"], "answer_index": 1},
            {"id": "m2", "q": "Which HTTP method is typically used to update a resource?", "choices": ["GET", "POST", "PUT/PATCH", "TRACE"], "answer_index": 2},
            {"id": "m3", "q": "What is JSX?", "choices": ["A database", "A JavaScript syntax extension used by React", "A Node package manager", "A CSS framework"], "answer_index": 1},
            {"id": "m4", "q": "Which hook is used for side effects in React?", "choices": ["useMemo", "useEffect", "useRef", "useId"], "answer_index": 1},
            {"id": "m5", "q": "What does CORS control?", "choices": ["DB schema", "Cross-origin requests in browsers", "CPU usage", "Cache invalidation"], "answer_index": 1},
            {"id": "m6", "q": "Which is true about MongoDB?", "choices": ["Relational only", "Document-oriented NoSQL database", "Graph database only", "Key-value only"], "answer_index": 1},
            {"id": "m7", "q": "What is the purpose of `express.json()`?", "choices": ["Serve images", "Parse JSON request bodies", "Connect MongoDB", "Handle cookies"], "answer_index": 1},
            {"id": "m8", "q": "What is a JWT mainly used for?", "choices": ["Image compression", "Authentication/authorization tokens", "Database indexing", "UI theming"], "answer_index": 1},
            {"id": "m9", "q": "Which header usually carries a Bearer token?", "choices": ["Host", "Authorization", "Accept", "Content-Length"], "answer_index": 1},
            {"id": "m10", "q": "In REST, what should a 404 response indicate?", "choices": ["Unauthorized", "Not found", "Server error", "Success"], "answer_index": 1},
            {"id": "m11", "q": "What does `npm install` do?", "choices": ["Runs tests", "Installs dependencies", "Deploys app", "Starts DB"], "answer_index": 1},
            {"id": "m12", "q": "Which is best for storing secrets in production?", "choices": ["Hardcode in JS", ".env committed to git", "Environment variables/secret manager", "LocalStorage"], "answer_index": 2},
            {"id": "m13", "q": "What is the purpose of an index in MongoDB?", "choices": ["Encrypt data", "Speed up queries", "Add columns", "Change JSON format"], "answer_index": 1},
            {"id": "m14", "q": "Which status code is best for 'created'?", "choices": ["200", "201", "204", "301"], "answer_index": 1},
            {"id": "m15", "q": "What is the role of middleware in Express?", "choices": ["Database tables", "Functions that run during request handling", "React components", "CSS variables"], "answer_index": 1},
        ],
    },
}


@tests_bp.get("")
def list_tests():
    items = [{"test_id": tid, "title": t["title"], "duration_seconds": t["duration_seconds"], "marks_per_question": t["marks_per_question"], "question_count": len(t["questions"])} for tid, t in TESTS.items()]
    return jsonify({"items": items})


@tests_bp.get("/<test_id>/questions")
def get_questions(test_id: str):
    if test_id not in VALID_TEST_IDS:
        return jsonify({"error": "not_found"}), 404
    t = TESTS.get(test_id)
    if not t:
        return jsonify({"error": "not_found"}), 404
    questions = [{"id": q["id"], "q": q["q"], "choices": q["choices"]} for q in t["questions"]]
    return jsonify({"test": {"test_id": test_id, "title": t["title"], "duration_seconds": t["duration_seconds"], "marks_per_question": t["marks_per_question"], "questions": questions}})


@tests_bp.post("/<test_id>/submit")
@jwt_required()
def submit(test_id: str):
    if test_id not in VALID_TEST_IDS:
        return jsonify({"error": "not_found"}), 404
    t = TESTS.get(test_id)
    if not t:
        return jsonify({"error": "not_found"}), 404

    payload = request.get_json(silent=True) or {}
    answers: dict = payload.get("answers") or {}
    if not isinstance(answers, dict):
        return jsonify({"error": "invalid_answers"}), 400

    total_q = len(t["questions"])
    marks_per = int(t["marks_per_question"])
    total_marks = total_q * marks_per
    valid_ids = {q["id"] for q in t["questions"]}
    choice_counts = {q["id"]: len(q["choices"]) for q in t["questions"]}

    correct = 0
    breakdown = []
    sanitized_answers = {}
    for q in t["questions"]:
        qid = q["id"]
        chosen = answers.get(qid, None)
        if chosen is not None:
            if not isinstance(chosen, int):
                chosen = None
            elif chosen < 0 or chosen >= choice_counts[qid]:
                chosen = None
        sanitized_answers[qid] = chosen
        is_correct = chosen == q["answer_index"]
        if is_correct:
            correct += 1
        breakdown.append({"id": qid, "chosen": chosen, "is_correct": is_correct})

    # Reject unexpected answer keys to limit payload abuse.
    if set(answers.keys()) - valid_ids:
        return jsonify({"error": "invalid_answer_keys"}), 400

    score_marks = correct * marks_per

    now = datetime.now(timezone.utc)
    user_id = parse_oid(get_jwt_identity())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401
    claims = get_jwt()

    db = get_db(current_app)
    attempt = {
        "user_id": user_id,
        "role": claims.get("role"),
        "test_id": test_id,
        "correct": correct,
        "total_questions": total_q,
        "marks_per_question": marks_per,
        "score_marks": score_marks,
        "total_marks": total_marks,
        "answers": sanitized_answers,
        "created_at": now,
    }
    res = db.test_attempts.insert_one(attempt)
    saved = db.test_attempts.find_one({"_id": res.inserted_id})

    return jsonify({"result": serialize_doc(saved), "breakdown": breakdown})


@tests_bp.get("/mine")
@jwt_required()
def my_results():
    user_id = parse_oid(get_jwt_identity())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401
    db = get_db(current_app)
    items = [serialize_doc(d) for d in db.test_attempts.find({"user_id": user_id}).sort("created_at", -1).limit(50)]
    return jsonify({"items": items})
