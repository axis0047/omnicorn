"""
Flask example application for Omnicorn.

Run with:
    omnicorn examples.flask_app:app --config .omnicorn.dev.yaml
"""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def root():
    return jsonify({"message": "Hello from Omnicorn!", "server": "omnicorn"})


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})
