import os
import uuid
import json
import requests
from flask import Flask, request, jsonify, render_template_string
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

CLOCKED_API_KEY = os.environ.get("CLOCKED_API_KEY", "")
CLOCKED_BASE_URL = os.environ.get("CLOCKED_BASE_URL", "https://clocked.rezolve.ai/clocked")

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clocked Dynamic Studio</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: #f4f6f8; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { margin-bottom: 20px; font-size: 24px; color: #1e293b; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 20px; }
        .card { background: white; border-radius: 8px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .card h2 { font-size: 18px; margin-top: 0; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 10px; color: #0066cc; }
        .form-group { margin-bottom: 15px; }
        label { display: block; font-weight: 600; margin-bottom: 5px; font-size: 14px; }
        textarea, input { width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-family: monospace; font-size: 13px; }
        textarea { height: 120px; resize: vertical; }
        button { background: #0066cc; color: white; border: none; padding: 12px 24px; font-size: 16px; border-radius: 4px; cursor: pointer; width: 100%; font-weight: 600; }
        button:hover { background: #0052a3; }
        .results { margin-top: 20px; }
        .section { background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .telemetry { background: #eef6ff; border-left: 4px solid #0066cc; padding: 10px; margin-bottom: 10px; font-size: 14px; }
        pre { background: #272822; color: #f8f8f2; padding: 10px; border-radius: 4px; overflow-x: auto; margin: 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Clocked Dynamic Studio</h1>
        <div class="grid">
            <!-- Extract Builder -->
            <div class="card">
                <h2>Extract Builder (/clocked/extract)</h2>
                <div class="form-group">
                    <label for="extract-doc">Document Text</label>
                    <textarea id="extract-doc">John Doe, Senior Engineer at TechCorp. Email: john@example.com, Phone: 555-0199.</textarea>
                </div>
                <div class="form-group">
                    <label for="extract-schema">Target Schema (JSON)</label>
                    <textarea id="extract-schema">{"name": "string", "title": "string", "email": "string"}</textarea>
                </div>
            </div>
            <!-- Decide Builder -->
            <div class="card">
                <h2>Decide Builder (/clocked/decide)</h2>
                <div class="form-group">
                    <label for="decide-context">Context Text / JSON</label>
                    <textarea id="decide-context">{"user_role": "admin", "action": "delete_database", "risk_score": 0.85}</textarea>
                </div>
                <div class="form-group">
                    <label for="decide-prompt">Questions (JSON Dict)</label>
                    <textarea id="decide-prompt">{"question": "Evaluate if user is authorized to delete database given risk score."}</textarea>
                </div>
            </div>
            <!-- Fill Builder -->
            <div class="card">
                <h2>Fill Builder (/clocked/fill)</h2>
                <div class="form-group">
                    <label for="fill-context">Source Context Text</label>
                    <textarea id="fill-context">Customer onboarding request: Alice Smith, born 1990-05-12, prefers email notification.</textarea>
                </div>
                <div class="form-group">
                    <label for="fill-fields">Form Fields (JSON)</label>
                    <textarea id="fill-fields">[
  {"name": "full_name", "type": "string", "label": "Full Name", "required": true},
  {"name": "dob", "type": "date", "label": "Date of Birth", "required": false},
  {"name": "notify_pref", "type": "select", "options": ["email", "sms"], "label": "Notification Preference"}
]</textarea>
                </div>
            </div>
        </div>
        <button type="button" onclick="runParallel()">Run All Endpoints in Parallel</button>
        <div id="results" class="results"></div>
    </div>
    <script>
        async function runParallel() {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<p>Executing /extract, /decide, and /fill in parallel...</p>';
            
            let extractSchema = {};
            try { extractSchema = JSON.parse(document.getElementById('extract-schema').value || '{}'); } catch(e) {}

            let decideContext = document.getElementById('decide-context').value;

            let decideQuestions = {};
            try {
                let parsed = JSON.parse(document.getElementById('decide-prompt').value);
                if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
                    decideQuestions = parsed;
                } else {
                    decideQuestions = {"question": String(parsed)};
                }
            } catch(e) {
                decideQuestions = {"question": document.getElementById('decide-prompt').value || "Default question"};
            }

            let fillFields = [];
            try { fillFields = JSON.parse(document.getElementById('fill-fields').value || '[]'); } catch(e) {}

            const payload = {
                extract: {
                    text: document.getElementById('extract-doc').value,
                    document: document.getElementById('extract-doc').value,
                    schema: extractSchema
                },
                decide: {
                    text: decideContext,
                    context: decideContext,
                    questions: decideQuestions,
                    policy: document.getElementById('decide-prompt').value
                },
                fill: {
                    text: document.getElementById('fill-context').value,
                    context: document.getElementById('fill-context').value,
                    fields: fillFields
                }
            };

            try {
                const res = await fetch('/run', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                let html = '<h2>Parallel Execution Results</h2>';

                ['extract', 'decide', 'fill'].forEach(key => {
                    const item = data[key] || {};
                    html += `
                        <div class="section">
                            <h3>/${key.toUpperCase()}</h3>
                            <div class="telemetry">
                                <strong>Telemetry:</strong> 
                                Model Time: ${item.telemetry?.['X-Clocked-Model-Ms'] || 'N/A'} ms | 
                                Credits: ${item.telemetry?.['X-Clocked-Credits'] || 'N/A'} | 
                                Cost: $${item.telemetry?.['X-Clocked-Cost-Usd'] || 'N/A'}
                            </div>
                            <h4>Result:</h4>
                            <pre>${JSON.stringify(item.result || item.error, null, 2)}</pre>
                        </div>
                    `;
                });

                resultsDiv.innerHTML = html;
            } catch (err) {
                resultsDiv.innerHTML = `<pre>Error: ${err.message}</pre>`;
            }
        }
    </script>
</body>
</html>
"""

def call_clocked_endpoint(endpoint_name, payload):
    url = f"{CLOCKED_BASE_URL}/{endpoint_name}"
    headers = {
        "Authorization": f"Bearer {CLOCKED_API_KEY}",
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4())
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        telemetry = {
            "X-Clocked-Model-Ms": resp.headers.get("X-Clocked-Model-Ms", "0"),
            "X-Clocked-Credits": resp.headers.get("X-Clocked-Credits", "0"),
            "X-Clocked-Cost-Usd": resp.headers.get("X-Clocked-Cost-Usd", "0.000")
        }
        try:
            res_data = resp.json()
        except Exception:
            res_data = resp.text
        return {
            "endpoint": endpoint_name,
            "telemetry": telemetry,
            "result": res_data,
            "status_code": resp.status_code
        }
    except Exception as e:
        return {
            "endpoint": endpoint_name,
            "error": str(e),
            "telemetry": {
                "X-Clocked-Model-Ms": "0",
                "X-Clocked-Credits": "0",
                "X-Clocked-Cost-Usd": "0.000"
            }
        }

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/run", methods=["POST"])
def run_all():
    data = request.json or {}
    
    raw_extract = data.get("extract", {})
    raw_decide = data.get("decide", {})
    raw_fill = data.get("fill", {})

    # 1. /extract payload mapping:
    # 'text' must be a non-empty string (document text)
    # schema/fields in valid format
    ext_text = raw_extract.get("text") or raw_extract.get("document") or ""
    if isinstance(ext_text, (dict, list)):
        ext_text = json.dumps(ext_text)
    else:
        ext_text = str(ext_text)
    if not ext_text.strip():
        ext_text = "Sample document text."

    ext_schema = raw_extract.get("schema") or raw_extract.get("fields") or {}
    if isinstance(ext_schema, str):
        try:
            ext_schema = json.loads(ext_schema)
        except Exception:
            ext_schema = {}

    extract_payload = {
        "text": ext_text,
        "schema": ext_schema
    }

    # 2. /decide payload mapping:
    # 'text' must be string (context JSON stringified or text)
    # 'questions' must be a non-empty JSON object (dict)
    dec_text = raw_decide.get("text") or raw_decide.get("context") or ""
    if isinstance(dec_text, (dict, list)):
        dec_text = json.dumps(dec_text)
    else:
        dec_text = str(dec_text)
    if not dec_text.strip():
        dec_text = "Sample decision context."

    dec_questions = raw_decide.get("questions") or raw_decide.get("policy") or {}
    if isinstance(dec_questions, str):
        try:
            parsed_q = json.loads(dec_questions)
            if isinstance(parsed_q, dict):
                dec_questions = parsed_q
            else:
                dec_questions = {"query": str(parsed_q)}
        except Exception:
            dec_questions = {"query": dec_questions}
    elif not isinstance(dec_questions, dict):
        dec_questions = {"query": str(dec_questions)}
    if not dec_questions:
        dec_questions = {"question": "Evaluate request."}

    decide_payload = {
        "text": dec_text,
        "questions": dec_questions
    }

    # 3. /fill payload mapping:
    # 'text' must be non-empty string (unstructured source context)
    # form fields in expected format
    fill_text = raw_fill.get("text") or raw_fill.get("context") or ""
    if isinstance(fill_text, (dict, list)):
        fill_text = json.dumps(fill_text)
    else:
        fill_text = str(fill_text)
    if not fill_text.strip():
        fill_text = "Sample source context for filling."

    fill_fields = raw_fill.get("fields") or raw_fill.get("schema") or {}
    if isinstance(fill_fields, str):
        try:
            fill_fields = json.loads(fill_fields)
        except Exception:
            fill_fields = []

    fill_payload = {
        "text": fill_text,
        "fields": fill_fields
    }

    with ThreadPoolExecutor(max_workers=4) as executor:
        f_extract = executor.submit(call_clocked_endpoint, "extract", extract_payload)
        f_decide = executor.submit(call_clocked_endpoint, "decide", decide_payload)
        f_fill = executor.submit(call_clocked_endpoint, "fill", fill_payload)

        results = {
            "extract": f_extract.result(),
            "decide": f_decide.result(),
            "fill": f_fill.result()
        }

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
