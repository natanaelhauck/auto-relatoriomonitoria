"""Optional Flask healthcheck app for portfolio/Render deployments."""

from __future__ import annotations

from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def index() -> str:
    """Return the project name for a minimal landing response."""
    return "Auto Relatório Monitoria"


@app.get("/health")
def health():
    """Return a small healthcheck payload."""
    return jsonify({"status": "ok", "mode": "docs"})


if __name__ == "__main__":
    app.run()
