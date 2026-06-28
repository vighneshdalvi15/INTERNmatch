"""
InternMatch entrypoint.

Run this file to start the Flask server that serves:
- the SPA frontend at `/` (from `backend/templates/index.html`)
- JSON APIs under `/api/*` (from `backend/routes/*`)
"""

import os
from backend.app import create_app

# ✅ CREATE APP AT GLOBAL LEVEL
app = create_app()

# Optional local run
if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=app.config.get("DEBUG", False))
