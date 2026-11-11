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
        textarea { width: 100%; height: 100px; padding: 8px; margin: 8px 0; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box; }
        button { background-color: #2563eb; color: white; border: none; padding: 10px 16px; border-radius: 4px; cursor: pointer; font-weight: 500; }
        button:hover { background-color: #1d4ed8; }
        pre { background: #f8fafc; padding: 12px; border-radius: 4px; overflow-x: auto; border: 1px solid #e2e8f0; }
        .error { color: #dc2626; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Clocked Dynamic Studio</h1>
        <div class="section">
            <h2>User Prompt / Input</h2>
            <textarea id="promptInput" placeholder="Enter input text or context here..."></textarea>
            <button onclick="runAll()">Run Studio Workflow</button>
        </div>
        <div class="section">
            <h2>Results</h2>
            <div id="results">Press 'Run Studio Workflow' to send requests.</div>
        </div>
    </div>
    <script>
        async function runAll() {
            const prompt = document.getElementById('promptInput').value;
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = "Running API endpoints...";
            
            try {
                const response = await fetch('/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: prompt,
                        prompt: prompt,
                        schema: { "extracted_info": "Summary of provided context" },
                        questions: { "decision": prompt || "What is the key decision?" },
                        fields: { "target_field": "Extracted target value" }
                    })
                });
                const data = await response.json();
                resultsDiv.innerHTML = "<pre>" + JSON.stringify(data, null, 2) + "</pre>";
            } catch (err) {
                resultsDiv.innerHTML = "<div class='error'>Error: " + err.message + "</div>";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(INDEX_HTML)

def call_clocked_endpoint(endpoint, payload):
    headers = {
        "Authorization": f"Bearer {CLOCKED_API_KEY}",
        "Content-Type": "application/json"
    }
    url = f"{CLOCKED_BASE_URL}/{endpoint}"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        return {"endpoint": endpoint, "status_code": resp.status_code, "response": resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text}
    except Exception as e:
        return {"endpoint": endpoint, "error": str(e)}

@app.route('/run', methods=['POST'])
def run_all():
    data = request.json or {}
    user_prompt = data.get("prompt", "")
    
    raw_text = data.get("text") or data.get("prompt") or user_prompt
    text_val = raw_text.strip() if (isinstance(raw_text, str) and raw_text.strip()) else "Sample context text for Clocked API processing."

    # /extract payload
    extract_schema = data.get("schema")
    if not isinstance(extract_schema, dict) or not extract_schema:
        extract_schema = {"extracted_info": "Summary and key details extracted from text"}

    extract_payload = {
        "text": text_val,
        "schema": extract_schema
    }

    # /decide payload
    decide_questions = data.get("questions")
    if not isinstance(decide_questions, dict) or not decide_questions:
        decide_questions = {"decision": text_val}

    decide_payload = {
        "text": text_val,
        "questions": decide_questions
    }

    # /fill payload
    fill_fields = data.get("fields") or data.get("schema")
    if not isinstance(fill_fields, dict) or not fill_fields:
        fill_fields = {"field_1": "Value to fill based on text"}

    fill_payload = {
        "text": text_val,
        "fields": fill_fields
    }

    endpoints = [
        ("extract", extract_payload),
        ("decide", decide_payload),
        ("fill", fill_payload)
    ]

    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(call_clocked_endpoint, ep, pl): ep for ep, pl in endpoints}
        for future in futures:
            ep = futures[future]
            try:
                results[ep] = future.result()
            except Exception as e:
                results[ep] = {"error": str(e)}

    return jsonify(results)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
