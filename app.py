import os
import uuid
import json
import requests
from flask import Flask, request, jsonify, render_template_string
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

CLOCKED_API_KEY = os.environ.get("CLOCKED_API_KEY", "")
CLOCKED_BASE_URL = os.environ.get("CLOCKED_BASE_URL", "https://clocked.rezolve.ai/clocked")

def call_clocked_endpoint(endpoint_name, payload, req_api_key=None):
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4())
    }
    api_key = req_api_key or CLOCKED_API_KEY
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["x-api-key"] = api_key

    url = f"{CLOCKED_BASE_URL.rstrip('/')}/{endpoint_name.lstrip('/')}"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        return {
            "status_code": resp.status_code,
            "response": resp.json() if resp.headers.get("Content-Type", "").startswith("application/json") else resp.text
        }
    except Exception as e:
        return {"error": str(e)}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Clocked Dynamic Studio</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f6f9; }
        h1 { color: #333; }
        .grid { display: flex; gap: 20px; margin-bottom: 20px; }
        .card { background: white; padding: 15px; border-radius: 8px; flex: 1; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        textarea, input[type="text"] { width: 95%; margin-top: 5px; margin-bottom: 10px; font-family: monospace; }
        button { background-color: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; width: 100%; font-size: 16px; }
        button:hover { background-color: #0056b3; }
        pre { background: #eef1f6; padding: 10px; border-radius: 4px; white-space: pre-wrap; max-height: 250px; overflow-y: auto; }
        .api-key-container { margin-bottom: 20px; background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    </style>
</head>
<body>
    <h1>Clocked Dynamic Studio</h1>
    <div class="api-key-container">
        <label><strong>Optional API Key:</strong></label><br>
        <input type="text" id="api_key" placeholder="Enter custom API Key if needed">
    </div>
    <div class="grid">
        <div class="card">
            <h3>Extract Builder (/clocked/extract)</h3>
            <label>Document Text</label>
            <textarea id="extract_text" rows="5">John Doe, Senior Engineer at TechCorp. Email: john@example.com, Phone: 555-0199.</textarea>
            <label>Target Schema (JSON)</label>
            <textarea id="extract_schema" rows="5">{"name": "string", "title": "string", "email": "string"}</textarea>
        </div>
        <div class="card">
            <h3>Decide Builder (/clocked/decide)</h3>
            <label>Context Text / JSON</label>
            <textarea id="decide_context" rows="5">{"user_role": "admin", "action": "delete_database", "risk_score": 0.85}</textarea>
            <label>Questions (JSON Dict)</label>
            <textarea id="decide_questions" rows="5">{"question": "Evaluate if user is authorized to delete database given risk score."}</textarea>
        </div>
        <div class="card">
            <h3>Fill Builder (/clocked/fill)</h3>
            <label>Source Context Text</label>
            <textarea id="fill_context" rows="5">Customer onboarding request: Alice Smith, born 1990-05-12, prefers email notification.</textarea>
            <label>Form Fields (JSON)</label>
            <textarea id="fill_fields" rows="5">[{"name": "full_name", "type": "string", "label": "Full Name", "required": true}, {"name": "dob", "type": "date", "label": "Date of Birth", "required": false}, {"name": "notify_pref", "type": "select", "options": ["email", "sms"], "label": "Notification Preference"}]</textarea>
        </div>
    </div>
    <button onclick="runParallel()">Run All Endpoints in Parallel</button>
    <h2>Parallel Execution Results</h2>
    <div class="grid">
        <div class="card">
            <h4>/EXTRACT</h4>
            <pre id="extract_res">Awaiting execution...</pre>
        </div>
        <div class="card">
            <h4>/DECIDE</h4>
            <pre id="decide_res">Awaiting execution...</pre>
        </div>
        <div class="card">
            <h4>/FILL</h4>
            <pre id="fill_res">Awaiting execution...</pre>
        </div>
    </div>
    <script>
        async function runParallel() {
            const apiKey = document.getElementById('api_key').value;
            document.getElementById('extract_res').innerText = "Running...";
            document.getElementById('decide_res').innerText = "Running...";
            document.getElementById('fill_res').innerText = "Running...";

            const payload = {
                api_key: apiKey,
                extract: { text: document.getElementById('extract_text').value, schema: document.getElementById('extract_schema').value },
                decide: { context: document.getElementById('decide_context').value, questions: document.getElementById('decide_questions').value },
                fill: { context: document.getElementById('fill_context').value, fields: document.getElementById('fill_fields').value }
            };

            const response = await fetch('/run_all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await response.json();
            document.getElementById('extract_res').innerText = JSON.stringify(data.extract, null, 2);
            document.getElementById('decide_res').innerText = JSON.stringify(data.decide, null, 2);
            document.getElementById('fill_res').innerText = JSON.stringify(data.fill, null, 2);
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/run_all", methods=["POST"])
def run_all():
    data = request.json or {}
    api_key = data.get("api_key")

    ext_raw = data.get("extract", {})
    ext_text = ext_raw.get("text", "")
    try:
        ext_schema = json.loads(ext_raw.get("schema", "{}"))
    except:
        ext_schema = {}
    if not isinstance(ext_schema, dict):
        ext_schema = {}
    extract_fields = {}
    for k, v in ext_schema.items():
        extract_fields[str(k)] = str(v)
    extract_payload = {"text": ext_text, "fields": extract_fields}

    dec_raw = data.get("decide", {})
    dec_context = dec_raw.get("context", "")
    try:
        dec_q = json.loads(dec_raw.get("questions", "{}"))
    except:
        dec_q = {}
    decide_questions = {}
    if isinstance(dec_q, dict):
        for k, v in dec_q.items():
            q_str = str(v.get("question", v) if isinstance(v, dict) else v)
            decide_questions[str(k)] = {
                "type": "choice",
                "question": q_str,
                "criteria": {"yes": "Meets criteria / true", "no": "Does not meet criteria / false"}
            }
    elif isinstance(dec_q, str):
        decide_questions["q1"] = {
            "type": "choice",
            "question": dec_q,
            "criteria": {"yes": "Meets criteria / true", "no": "Does not meet criteria / false"}
        }

    decide_payload = {"state": dec_context, "questions": decide_questions}

    fill_raw = data.get("fill", {})
    fill_context = fill_raw.get("context", "")
    try:
        fill_fields_in = json.loads(fill_raw.get("fields", "[]"))
    except:
        fill_fields_in = []
    fill_fields = {}
    if isinstance(fill_fields_in, list):
        for item in fill_fields_in:
            if isinstance(item, dict):
                name = str(item.get("name", "field"))
                label = str(item.get("label", name))
                fill_fields[name] = {"type": "extract", "description": label}
    elif isinstance(fill_fields_in, dict):
        for k, v in fill_fields_in.items():
            desc = str(v.get("label", v.get("description", k)) if isinstance(v, dict) else v)
            fill_fields[str(k)] = {"type": "extract", "description": desc}

    fill_payload = {"text": fill_context, "fields": fill_fields}

    with ThreadPoolExecutor(max_workers=3) as executor:
        f_ext = executor.submit(call_clocked_endpoint, "extract", extract_payload, api_key)
        f_dec = executor.submit(call_clocked_endpoint, "decide", decide_payload, api_key)
        f_fill = executor.submit(call_clocked_endpoint, "fill", fill_payload, api_key)

        res_ext = f_ext.result()
        res_dec = f_dec.result()
        res_fill = f_fill.result()

    return jsonify({
        "extract": res_ext,
        "decide": res_dec,
        "fill": res_fill
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
