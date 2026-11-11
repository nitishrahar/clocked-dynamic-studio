import os
import requests
import uuid
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
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 20px; }
        .container { max-width: 900px; margin: 0 auto; background: #ffffff; padding: 24px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { margin-top: 0; color: #1e293b; }
        .section { margin-bottom: 24px; padding: 16px; border: 1px solid #e2e8f0; border-radius: 6px; }
        .section h2 { margin-top: 0; font-size: 1.25rem; }
        textarea { width: 100%; height: 100px; font-family: monospace; margin-bottom: 12px; }
        button { background: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
        button:hover { background: #1d4ed8; }
        .result-box { margin-top: 12px; background: #f8fafc; padding: 12px; border: 1px solid #cbd5e1; border-radius: 4px; font-family: monospace; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Clocked Dynamic Studio</h1>
        
        <div class="section">
            <h2>Process Dynamic Studio Workflow</h2>
            <textarea id="promptInput" placeholder="Enter input text or prompt here..."></textarea>
            <button onclick="runWorkflow()">Run Parallel Endpoints (/extract, /decide, /fill)</button>
            <div id="status" style="margin-top: 8px; font-weight: bold;"></div>
            <div id="results" class="result-box" style="display: none;"></div>
        </div>
    </div>

    <script>
        async function runWorkflow() {
            const prompt = document.getElementById('promptInput').value;
            const statusDiv = document.getElementById('status');
            const resultsDiv = document.getElementById('results');

            statusDiv.textContent = 'Processing request across Clocked endpoints...';
            resultsDiv.style.display = 'none';

            try {
                const response = await fetch('/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: prompt })
                });

                const data = await response.json();
                statusDiv.textContent = 'Completed!';
                resultsDiv.style.display = 'block';
                resultsDiv.textContent = JSON.stringify(data, null, 2);
            } catch (err) {
                statusDiv.textContent = 'Error executing workflow: ' + err.message;
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(INDEX_HTML)

def call_clocked_endpoint(endpoint_name, payload):
    headers = {
        "Authorization": f"Bearer {CLOCKED_API_KEY}",
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4())
    }
    url = f"{CLOCKED_BASE_URL}/{endpoint_name}"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        return endpoint_name, resp.json()
    except Exception as e:
        return endpoint_name, {"error": str(e)}

@app.route('/run', methods=['POST'])
def run_all():
    data = request.json or {}
    user_prompt = data.get("prompt", "")

    extract_payload = {"task": "extract", "input": user_prompt}
    decide_payload = {"task": "decide", "input": user_prompt}
    fill_payload = {"task": "fill", "input": user_prompt}

    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_extract = executor.submit(call_clocked_endpoint, "extract", extract_payload)
        f_decide = executor.submit(call_clocked_endpoint, "decide", decide_payload)
        f_fill = executor.submit(call_clocked_endpoint, "fill", fill_payload)

        for f in [f_extract, f_decide, f_fill]:
            name, res = f.result()
            results[name] = res

    return jsonify(results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
