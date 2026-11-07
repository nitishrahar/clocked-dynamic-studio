import os
import uuid
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

CLOCKED_API_KEY = os.environ.get("CLOCKED_API_KEY", "")
CLOCKED_BASE_URL = "https://clocked.rezolve.ai/clocked"

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Clocked Dynamic Studio</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 800px; margin: auto; }
        textarea { width: 100%; height: 100px; }
        pre { background: #f4f4f4; padding: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Clocked Dynamic Studio</h1>
        
        <h2>Extract Policy Requirements</h2>
        <form action="/extract" method="post">
            <label>Policy Document Text:</label><br>
            <textarea name="document" placeholder="Enter policy text here..."></textarea><br><br>
            <button type="submit">Extract Requirements</button>
        </form>
        
        <hr>
        
        <h2>Compliance Decision</h2>
        <form action="/decide" method="post">
            <label>Context / Decision Payload:</label><br>
            <textarea name="context" placeholder="Enter decision payload or context..."></textarea><br><br>
            <button type="submit">Make Compliance Decision</button>
        </form>
        
        <hr>

        <h2>Custom / Direct Clocked Run</h2>
        <form action="/api/custom-run" method="post">
            <label>Custom Payload (JSON):</label><br>
            <textarea name="payload" placeholder='{"endpoint": "extract", ...}'></textarea><br><br>
            <button type="submit">Execute Custom Run</button>
        </form>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/extract", methods=["POST"])
def extract():
    payload = request.get_json(silent=True) or request.form.to_dict()
    headers = {
        "Authorization": f"Bearer {CLOCKED_API_KEY}",
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4())
    }
    try:
        resp = requests.post(f"{CLOCKED_BASE_URL}/extract", json=payload, headers=headers, timeout=30)
        telemetry = {
            "X-Clocked-Model-Ms": resp.headers.get("X-Clocked-Model-Ms"),
            "X-Clocked-Credits": resp.headers.get("X-Clocked-Credits"),
            "X-Clocked-Cost-Usd": resp.headers.get("X-Clocked-Cost-Usd")
        }
        return jsonify({
            "status_code": resp.status_code,
            "response": resp.json() if resp.headers.get("content-type") == "application/json" else resp.text,
            "telemetry": telemetry
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/decide", methods=["POST"])
def decide():
    payload = request.get_json(silent=True) or request.form.to_dict()
    headers = {
        "Authorization": f"Bearer {CLOCKED_API_KEY}",
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4())
    }
    try:
        resp = requests.post(f"{CLOCKED_BASE_URL}/decide", json=payload, headers=headers, timeout=30)
        telemetry = {
            "X-Clocked-Model-Ms": resp.headers.get("X-Clocked-Model-Ms"),
            "X-Clocked-Credits": resp.headers.get("X-Clocked-Credits"),
            "X-Clocked-Cost-Usd": resp.headers.get("X-Clocked-Cost-Usd")
        }
        return jsonify({
            "status_code": resp.status_code,
            "response": resp.json() if resp.headers.get("content-type") == "application/json" else resp.text,
            "telemetry": telemetry
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/custom-run", methods=["POST"])
def custom_run():
    payload = request.get_json(silent=True) or request.form.to_dict()
    endpoint = payload.pop("endpoint", "") if isinstance(payload, dict) else ""
    target_url = f"{CLOCKED_BASE_URL}/{endpoint}".rstrip("/") if endpoint else CLOCKED_BASE_URL
    headers = {
        "Authorization": f"Bearer {CLOCKED_API_KEY}",
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4())
    }
    try:
        resp = requests.post(target_url, json=payload, headers=headers, timeout=30)
        telemetry = {
            "X-Clocked-Model-Ms": resp.headers.get("X-Clocked-Model-Ms"),
            "X-Clocked-Credits": resp.headers.get("X-Clocked-Credits"),
            "X-Clocked-Cost-Usd": resp.headers.get("X-Clocked-Cost-Usd")
        }
        return jsonify({
            "status_code": resp.status_code,
            "response": resp.json() if resp.headers.get("content-type") == "application/json" else resp.text,
            "telemetry": telemetry
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=PORT)
