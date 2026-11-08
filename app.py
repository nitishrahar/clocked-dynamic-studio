import os
import requests
from concurrent.futures import ThreadPoolExecutor
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
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 20px; background: #f9fafb; color: #111827; }
        .container { max-width: 900px; margin: 0 auto; background: #ffffff; padding: 24px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        h1 { margin-top: 0; color: #1e293b; }
        .section { margin-bottom: 24px; padding: 16px; border: 1px solid #e2e8f0; border-radius: 6px; }
        .section h2 { margin-top: 0; font-size: 1.25rem; }
        textarea, input[type="text"] { width: 100%; padding: 8px; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 4px; font-family: monospace; }
        textarea { height: 80px; }
        button { background: #2563eb; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        button:hover { background: #1d4ed8; }
        pre { background: #f1f5f9; padding: 12px; border-radius: 4px; overflow-x: auto; }
        .telemetry { background: #ecfdf5; border: 1px solid #a7f3d0; padding: 10px; border-radius: 4px; margin-top: 10px; color: #065f46; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Clocked Dynamic Studio</h1>
        <p>Interactive studio integrating Clocked API endpoints: /clocked/extract, /clocked/decide, and /clocked/fill.</p>
        
        <form id="clocked-form">
            <div class="section">
                <h2>1. Extract Builder (/clocked/extract)</h2>
                <label>Document Text:</label>
                <textarea id="extract-doc">John Doe, Senior Engineer at TechCorp. Email: john@example.com, Phone: 555-0199.</textarea>
                <label>Target Schema (JSON):</label>
                <textarea id="extract-schema">{"name": "string", "title": "string", "email": "string"}</textarea>
            </div>

            <div class="section">
                <h2>2. Decide Builder (/clocked/decide)</h2>
                <label>Context (JSON):</label>
                <textarea id="decide-context">{"user_role": "admin", "action": "delete_database", "risk_score": 0.85}</textarea>
                <label>Policy / Prompt:</label>
                <textarea id="decide-prompt">Evaluate if user is authorized to delete database given risk score.</textarea>
            </div>

            <div class="section">
                <h2>3. Fill Builder (/clocked/fill)</h2>
                <p>Configure structured form fields matching /clocked/fill schema:</p>
                <label>Unstructured Source Context:</label>
                <textarea id="fill-context">Customer onboarding request: Alice Smith, born 1990-05-12, prefers email notification.</textarea>
                <label>Target Form Fields (JSON schema):</label>
                <textarea id="fill-fields">[
  {"name": "full_name", "type": "string", "label": "Full Name", "required": true},
  {"name": "dob", "type": "date", "label": "Date of Birth", "required": false},
  {"name": "notify_pref", "type": "select", "options": ["email", "sms"], "label": "Notification Preference"}
]</textarea>
            </div>

            <button type="button" onclick="runParallel()">Run All Endpoints in Parallel</button>
        </form>

        <div id="results" style="margin-top: 24px;"></div>
    </div>

    <script>
        async function runParallel() {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<p>Executing /clocked/extract, /clocked/decide, and /clocked/fill in parallel...</p>';
            
            const payload = {
                extract: {
                    document: document.getElementById('extract-doc').value,
                    schema: JSON.parse(document.getElementById('extract-schema').value || '{}')
                },
                decide: {
                    context: JSON.parse(document.getElementById('decide-context').value || '{}'),
                    policy: document.getElementById('decide-prompt').value
                },
                fill: {
                    context: document.getElementById('fill-context').value,
                    fields: JSON.parse(document.getElementById('fill-fields').value || '[]')
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
                    html += `<div class="section">
                        <h3>/${key.toUpperCase()}</h3>
                        <div class="telemetry">
                            <strong>Telemetry:</strong> 
                            Model Time: ${item.telemetry?.['X-Clocked-Model-Ms'] || 'N/A'} ms | 
                            Credits: ${item.telemetry?.['X-Clocked-Credits'] || 'N/A'} | 
                            Cost: $${item.telemetry?.['X-Clocked-Cost-Usd'] || 'N/A'}
                        </div>
                        <h4>Result:</h4>
                        <pre>${JSON.stringify(item.result || item.error, null, 2)}</pre>
                    </div>`;
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
    headers = {
        "Authorization": f"Bearer {CLOCKED_API_KEY}",
        "Content-Type": "application/json"
    }
    url = f"{CLOCKED_BASE_URL}/{endpoint_name}"
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

@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML)

@app.route("/run", methods=["POST"])
def run_all():
    data = request.json or {}
    extract_payload = data.get("extract", {})
    decide_payload = data.get("decide", {})
    fill_payload = data.get("fill", {})

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
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=PORT)
