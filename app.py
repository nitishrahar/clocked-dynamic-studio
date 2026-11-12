import os
import uuid
import json
import requests
from flask import Flask, request, jsonify, render_template_string
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

CLOCKED_API_KEY = os.environ.get("CLOCKED_API_KEY", "")
CLOCKED_BASE_URL = os.environ.get("CLOCKED_BASE_URL", "https://clocked.rezolve.ai/clocked")
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
        telemetry = {
            "X-Clocked-Model-Ms": resp.headers.get("X-Clocked-Model-Ms", resp.headers.get("x-clocked-model-ms", "0")),
            "X-Clocked-Credits": resp.headers.get("X-Clocked-Credits", resp.headers.get("x-clocked-credits", "0")),
            "X-Clocked-Cost-Usd": resp.headers.get("X-Clocked-Cost-Usd", resp.headers.get("x-clocked-cost-usd", "0.000")),
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
            },
            "status_code": 500
        }

def prepare_extract_payload(raw_data):
    text = raw_data.get("text") or raw_data.get("context") or "Sample text for extraction: Invoice #12345 total is $500 due on 2026-12-01."
    if isinstance(text, (dict, list)):
        text = json.dumps(text)
    else:
        text = str(text)

    fields_raw = raw_data.get("fields") or raw_data.get("schema") or {}
    if isinstance(fields_raw, str):
        try:
            fields_raw = json.loads(fields_raw)
        except Exception:
            fields_raw = {}

    ext_fields = {}
    if isinstance(fields_raw, dict):
        for k, v in fields_raw.items():
            ext_fields[str(k)] = str(v) if v is not None else str(k)
    elif isinstance(fields_raw, list):
        for item in fields_raw:
            if isinstance(item, dict):
                fname = item.get("name") or item.get("label") or item.get("field") or "field"
                fdesc = item.get("description") or item.get("desc") or fname
                ext_fields[str(fname)] = str(fdesc)
            elif isinstance(item, str):
                ext_fields[item] = item

    if not ext_fields:
        ext_fields = {
            "invoice_number": "Invoice reference number",
            "total_amount": "Total amount due",
            "due_date": "Due date of invoice"
        }

    return {"text": text, "fields": ext_fields}

def prepare_decide_payload(raw_data):
    state = raw_data.get("state") or raw_data.get("text") or raw_data.get("context") or ""
    if isinstance(state, str):
        if state.strip().startswith("{") or state.strip().startswith("["):
            try:
                state = json.loads(state)
            except Exception:
                pass
    if not state:
        state = {
            "user_status": "active",
            "account_age_days": 120,
            "verification_complete": True
        }

    questions = raw_data.get("questions") or raw_data.get("policy") or raw_data.get("query")
    if isinstance(questions, str):
        try:
            questions = json.loads(questions)
        except Exception:
            questions = [questions]

    if not isinstance(questions, (list, dict)):
        questions = [str(questions)] if questions else ["Is the request approved?"]

    if not questions:
        questions = ["Is the account eligible for upgrade?", "Does user meet security requirements?"]

    return {"state": state, "questions": questions}

def prepare_fill_payload(raw_data):
    text = raw_data.get("text") or raw_data.get("context") or "Applicant John Doe, email john@example.com, phone 555-0199."
    if isinstance(text, (dict, list)):
        text = json.dumps(text)
    else:
        text = str(text)

    fields_raw = raw_data.get("fields") or raw_data.get("schema") or {}
    if isinstance(fields_raw, str):
        try:
            fields_raw = json.loads(fields_raw)
        except Exception:
            fields_raw = {}

    fill_fields_obj = {}
    if isinstance(fields_raw, list):
        for item in fields_raw:
            if isinstance(item, dict):
                fname = item.get("name") or item.get("field") or item.get("label") or "field"
                ftype = item.get("type", "string")
                fdesc = item.get("description") or item.get("desc") or fname
                fill_fields_obj[str(fname)] = {"type": str(ftype), "description": str(fdesc)}
            elif isinstance(item, str):
                fill_fields_obj[item] = {"type": "string", "description": item}
    elif isinstance(fields_raw, dict):
        for k, v in fields_raw.items():
            if isinstance(v, dict):
                v_copy = dict(v)
                if "type" not in v_copy:
                    v_copy["type"] = "string"
                fill_fields_obj[str(k)] = v_copy
            elif isinstance(v, str):
                fill_fields_obj[str(k)] = {"type": "string", "description": v}
            else:
                fill_fields_obj[str(k)] = {"type": "string"}

    if not fill_fields_obj:
        fill_fields_obj = {
            "full_name": {"type": "string", "description": "Full legal name"},
            "email": {"type": "string", "description": "Email address"},
            "phone": {"type": "string", "description": "Phone number"}
        }

    return {"text": text, "fields": fill_fields_obj}

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clocked Dynamic Studio</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: #f4f6f8; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .header h1 { margin: 0; font-size: 24px; color: #111; }
        .api-key-box { display: flex; align-items: center; gap: 10px; }
        .api-key-box input { padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; width: 250px; font-size: 14px; }
        .main-btn { background: #0066cc; color: #fff; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; width: 100%; margin-bottom: 20px; transition: background 0.2s; }
        .main-btn:hover { background: #0052a3; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        .card { background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; flex-direction: column; }
        .card h2 { margin-top: 0; font-size: 18px; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px; color: #0066cc; }
        .form-group { margin-bottom: 12px; }
        .form-group label { display: block; font-weight: 600; margin-bottom: 4px; font-size: 13px; color: #555; }
        .form-group textarea { width: 100%; height: 90px; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; font-size: 12px; box-sizing: border-box; resize: vertical; }
        .run-btn { background: #28a745; color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: bold; margin-bottom: 12px; }
        .run-btn:hover { background: #218838; }
        .telemetry { background: #eef7ff; border: 1px solid #bce0fd; border-radius: 4px; padding: 8px; font-size: 11px; margin-bottom: 10px; font-family: monospace; }
        .output { background: #1e1e1e; color: #4ec9b0; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 11px; height: 160px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }
        .error { color: #f48771; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>Clocked Dynamic Studio</h1>
                <small style="color: #666;">Live API Telemetry & Payload Testing</small>
            </div>
            <div class="api-key-box">
                <label for="apiKey">API Key (Optional):</label>
                <input type="password" id="apiKey" placeholder="Enter Clocked API Key">
            </div>
        </div>

        <button class="main-btn" onclick="runAllEndpoints()">⚡ Run All Endpoints in Parallel</button>

        <div class="grid">
            <!-- /extract -->
            <div class="card">
                <h2>1. /extract</h2>
                <div class="form-group">
                    <label>Source Text:</label>
                    <textarea id="extText">Invoice #INV-2026-099 generated for Acme Corp. Total amount due is $1,450.00 by 2026-12-15. Contact support@acme.com.</textarea>
                </div>
                <div class="form-group">
                    <label>Fields Schema (JSON Object):</label>
                    <textarea id="extSchema">{\n  "invoice_number": "Invoice reference number",\n  "total_amount": "Total amount due",\n  "due_date": "Due date of invoice",\n  "contact_email": "Support email address"\n}</textarea>
                </div>
                <button class="run-btn" onclick="runSingle('extract')">Run /extract</button>
                <div class="telemetry" id="telemetry-extract">Ms: - | Credits: - | Cost: -</div>
                <div class="output" id="output-extract">Ready...</div>
            </div>

            <!-- /decide -->
            <div class="card">
                <h2>2. /decide</h2>
                <div class="form-group">
                    <label>State (JSON / Text):</label>
                    <textarea id="decState">{\n  "user_status": "active",\n  "account_age_days": 150,\n  "kyc_verified": true,\n  "risk_score": 0.05\n}</textarea>
                </div>
                <div class="form-group">
                    <label>Questions (JSON Array):</label>
                    <textarea id="decQuestions">[\n  "Is the account eligible for instant credit line extension?",\n  "Is manual compliance review required?"\n]</textarea>
                </div>
                <button class="run-btn" onclick="runSingle('decide')">Run /decide</button>
                <div class="telemetry" id="telemetry-decide">Ms: - | Credits: - | Cost: -</div>
                <div class="output" id="output-decide">Ready...</div>
            </div>

            <!-- /fill -->
            <div class="card">
                <h2>3. /fill</h2>
                <div class="form-group">
                    <label>Source Context:</label>
                    <textarea id="fillText">Applicant: Jane Doe, DOB: 1994-05-20, Email: jane.doe@example.com, Phone: +1-555-0144.</textarea>
                </div>
                <div class="form-group">
                    <label>Form Fields (JSON Object of Typed Fields):</label>
                    <textarea id="fillFields">{\n  "full_name": {\n    "type": "string",\n    "description": "Full legal name"\n  },\n  "email": {\n    "type": "string",\n    "description": "Email address"\n  },\n  "phone": {\n    "type": "string",\n    "description": "Phone number"\n  }\n}</textarea>
                </div>
                <button class="run-btn" onclick="runSingle('fill')">Run /fill</button>
                <div class="telemetry" id="telemetry-fill">Ms: - | Credits: - | Cost: -</div>
                <div class="output" id="output-fill">Ready...</div>
            </div>
        </div>
    </div>

    <script>
        function getApiKey() {
            return document.getElementById('apiKey').value.trim();
        }

        function updateTelemetry(ep, telemetry) {
            if (!telemetry) return;
            const ms = telemetry['X-Clocked-Model-Ms'] || telemetry['x-clocked-model-ms'] || '0';
            const credits = telemetry['X-Clocked-Credits'] || telemetry['x-clocked-credits'] || '0';
            const cost = telemetry['X-Clocked-Cost-Usd'] || telemetry['x-clocked-cost-usd'] || '0.000';
            document.getElementById(`telemetry-${ep}`).innerText = `Ms: ${ms}ms | Credits: ${credits} | Cost: $${cost}`;
        }

        function renderResult(ep, data) {
            const outEl = document.getElementById(`output-${ep}`);
            if (data.telemetry) {
                updateTelemetry(ep, data.telemetry);
            }
            if (data.result !== undefined) {
                outEl.classList.remove('error');
                outEl.innerText = typeof data.result === 'object' ? JSON.stringify(data.result, null, 2) : data.result;
            } else if (data.error) {
                outEl.classList.add('error');
                outEl.innerText = `Error: ${data.error}`;
            } else {
                outEl.innerText = JSON.stringify(data, null, 2);
            }
        }

        async function runSingle(ep) {
            const outEl = document.getElementById(`output-${ep}`);
            outEl.innerText = 'Calling Clocked API...';
            outEl.classList.remove('error');

            let payload = {};
            if (ep === 'extract') {
                payload = {
                    text: document.getElementById('extText').value,
                    fields: document.getElementById('extSchema').value
                };
            } else if (ep === 'decide') {
                payload = {
                    state: document.getElementById('decState').value,
                    questions: document.getElementById('decQuestions').value
                };
            } else if (ep === 'fill') {
                payload = {
                    text: document.getElementById('fillText').value,
                    fields: document.getElementById('fillFields').value
                };
            }

            try {
                const resp = await fetch(`/api/${ep}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': getApiKey()
                    },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                renderResult(ep, data);
            } catch (err) {
                outEl.classList.add('error');
                outEl.innerText = `Network Error: ${err.message}`;
            }
        }

        async function runAllEndpoints() {
            ['extract', 'decide', 'fill'].forEach(ep => {
                const outEl = document.getElementById(`output-${ep}`);
                outEl.innerText = 'Executing in parallel...';
                outEl.classList.remove('error');
            });

            let extFields, decState, decQuestions, fillFields;
            try { extFields = JSON.parse(document.getElementById('extSchema').value); } catch(e) { extFields = document.getElementById('extSchema').value; }
            try { decState = JSON.parse(document.getElementById('decState').value); } catch(e) { decState = document.getElementById('decState').value; }
            try { decQuestions = JSON.parse(document.getElementById('decQuestions').value); } catch(e) { decQuestions = document.getElementById('decQuestions').value; }
            try { fillFields = JSON.parse(document.getElementById('fillFields').value); } catch(e) { fillFields = document.getElementById('fillFields').value; }

            const payload = {
                api_key: getApiKey(),
                extract: { text: document.getElementById('extText').value, fields: extFields },
                decide: { state: decState, questions: decQuestions },
                fill: { text: document.getElementById('fillText').value, fields: fillFields }
            };

            try {
                const resp = await fetch('/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                if (data.extract) renderResult('extract', data.extract);
                if (data.decide) renderResult('decide', data.decide);
                if (data.fill) renderResult('fill', data.fill);
            } catch (err) {
                ['extract', 'decide', 'fill'].forEach(ep => {
                    const outEl = document.getElementById(`output-${ep}`);
                    outEl.classList.add('error');
                    outEl.innerText = `Execution Error: ${err.message}`;
                });
            }
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/api/extract", methods=["POST"])
def api_extract():
    req_data = request.get_json() or {}
    api_key = request.headers.get("X-API-Key") or req_data.get("api_key")
    payload = prepare_extract_payload(req_data)
    res = call_clocked_endpoint("extract", payload, req_api_key=api_key)
    return jsonify(res)

@app.route("/api/decide", methods=["POST"])
def api_decide():
    req_data = request.get_json() or {}
    api_key = request.headers.get("X-API-Key") or req_data.get("api_key")
    payload = prepare_decide_payload(req_data)
    res = call_clocked_endpoint("decide", payload, req_api_key=api_key)
    return jsonify(res)

@app.route("/api/fill", methods=["POST"])
def api_fill():
    req_data = request.get_json() or {}
    api_key = request.headers.get("X-API-Key") or req_data.get("api_key")
    payload = prepare_fill_payload(req_data)
    res = call_clocked_endpoint("fill", payload, req_api_key=api_key)
    return jsonify(res)

@app.route("/run", methods=["POST"])
@app.route("/api/run_all", methods=["POST"])
def run_all():
    req_data = request.get_json() or {}
    api_key = req_data.get("api_key") or request.headers.get("X-API-Key")

    raw_extract = req_data.get("extract") or {}
    raw_decide = req_data.get("decide") or {}
    raw_fill = req_data.get("fill") or {}

    extract_payload = prepare_extract_payload(raw_extract)
    decide_payload = prepare_decide_payload(raw_decide)
    fill_payload = prepare_fill_payload(raw_fill)

    with ThreadPoolExecutor(max_workers=4) as executor:
        f_extract = executor.submit(call_clocked_endpoint, "extract", extract_payload, api_key)
        f_decide = executor.submit(call_clocked_endpoint, "decide", decide_payload, api_key)
        f_fill = executor.submit(call_clocked_endpoint, "fill", fill_payload, api_key)

    results = {
        "extract": f_extract.result(),
        "decide": f_decide.result(),
        "fill": f_fill.result()
    }
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
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
