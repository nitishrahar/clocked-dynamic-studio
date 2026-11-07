# Clocked Dynamic Studio

Interactive schema builder, document extraction studio, and autonomous AI compliance gatekeeper built on Clocked API (`/clocked/extract` & `/clocked/decide`).

## Overview

Clocked Dynamic Studio provides an interactive platform for schema building, document extraction via `/clocked/extract`, and autonomous AI compliance gatekeeping using `/clocked/decide`.

## Clocked API Integration & Telemetry

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
