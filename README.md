# Clocked Dynamic Studio

Interactive schema builder, document extraction studio, and autonomous AI compliance gatekeeper built on Clocked API (`/clocked/extract` & `/clocked/decide`).

## Overview

Clocked Dynamic Studio provides an interactive platform for schema building, document extraction via `/clocked/extract`, and autonomous AI compliance gatekeeping using `/clocked/decide`.

## Clocked API Integration & Telemetry
# Clocked Dynamic Studio

Interactive schema builder, document extraction studio, autonomous AI compliance gatekeeper, and automated form filler built on Clocked API (`/clocked/extract`, `/clocked/decide`, and `/clocked/fill`).

## Overview

Clocked Dynamic Studio provides an interactive platform for:
- Structured schema extraction via `/clocked/extract`.
- Autonomous AI compliance gatekeeping using `/clocked/decide`.
- Dynamic form filling using `/clocked/fill`.

All three endpoints can be run concurrently in parallel via Python `ThreadPoolExecutor(max_workers=4)`.

## Clocked API Integration & Telemetry

- **`/clocked/extract`**: Extracts structured data based on custom schemas.
- **`/clocked/decide`**: Evaluates policy decisions and compliance logic.
- **`/clocked/fill`**: Fills structured form fields dynamically matching schema definitions.
- **Telemetry Headers**:
  - `X-Clocked-Model-Ms`: Model processing latency in milliseconds.
  - `X-Clocked-Credits`: Credits used per request.
  - `X-Clocked-Cost-Usd`: Request cost in USD.

## Usage

Set environment variables and launch:
```bash
export CLOCKED_API_KEY="your_api_key"
export PORT=8080
python app.py
```
- **`/clocked/extract`**: Extracts structured data based on custom schemas.
- **`/clocked/decide`**: Evaluates policy decisions and compliance logic.
- **`Idempotency-Key`**: Header passed with requests for safe idempotent retries.
- **Telemetry Headers**:
  - `X-Clocked-Model-Ms`: Model processing latency in milliseconds.
  - `X-Clocked-Credits`: Credits used per request.
  - `X-Clocked-Cost-Usd`: Request cost in USD.

## How to Run

1. **Export API Key:**
   ```bash
   export CLOCKED_API_KEY="your_key"
   ```

2. **Run Server:**
   ```bash
   python app.py
   ```
