# Deployment Information

## Platform
Railway (với Dockerfile builder)

## Deployed Configuration

### Railway Config (`railway.toml`)
```toml
[build]
builder = "DOCKERFILE"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

## Test Commands

### Health Check
```bash
curl https://<your-app>.railway.app/health
# Expected: {"status": "ok", "version": "1.0.0", ...}
```

### API Test (with authentication)
```bash
curl -X POST https://<your-app>.railway.app/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: {"question": "Hello", "answer": "...", "model": "gpt-4o-mini", ...}
```

### Readiness Check
```bash
curl https://<your-app>.railway.app/ready
# Expected: {"ready": true}
```

### Root Info
```bash
curl https://<your-app>.railway.app/
# Expected: {"app": "Production AI Agent", "version": "1.0.0", ...}
```

## Environment Variables Set
- `PORT` — Auto-injected by Railway
- `ENVIRONMENT` — production
- `AGENT_API_KEY` — Secret API key for authentication
- `APP_NAME` — Production AI Agent
- `APP_VERSION` — 1.0.0
- `LLM_MODEL` — gpt-4o-mini
- `RATE_LIMIT_PER_MINUTE` — 20
- `DAILY_BUDGET_USD` — 5.0
- `REDIS_URL` — Railway Redis add-on URL (if provisioned)

## Docker Image Details
- **Base:** `python:3.11-slim` (multi-stage build)
- **Final image size:** ~195 MB (< 500 MB requirement ✅)
- **User:** Non-root `agent` user
- **Health check:** Built-in Docker HEALTHCHECK instruction

## Security Features
- ✅ API Key authentication (`X-API-Key` header)
- ✅ Rate limiting (20 req/min per user)
- ✅ Cost guard ($5/day budget)
- ✅ Security headers (nosniff, DENY frame, XSS protection)
- ✅ No hardcoded secrets
- ✅ Non-root container user
- ✅ `.env` files in `.gitignore`
