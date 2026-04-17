# Deployment Information

## Public URL
🔗 **https://day12ha-tang-cloudvadeployment-production-128b.up.railway.app**

## Platform
Railway (với Dockerfile builder)

## Deployed Configuration

### Railway Config (`railway.toml`)
```toml
[build]
builder = "DOCKERFILE"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 60
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

## Live Test Results

### Root Info
```bash
curl https://day12ha-tang-cloudvadeployment-production-128b.up.railway.app/
# ✅ {"app":"Production AI Agent","version":"1.0.0","environment":"production","endpoints":{...}}
```

### Health Check
```bash
curl https://day12ha-tang-cloudvadeployment-production-128b.up.railway.app/health
# ✅ {"status":"ok","version":"1.0.0","environment":"production","uptime_seconds":254.8,...}
```

### Readiness Check
```bash
curl https://day12ha-tang-cloudvadeployment-production-128b.up.railway.app/ready
# ✅ {"ready":true}
```

### API Test (with authentication)
```bash
curl -X POST https://day12ha-tang-cloudvadeployment-production-128b.up.railway.app/ask \
  -H "X-API-Key: <YOUR_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# ✅ Returns answer with authentication
```

### Auth Rejection (no key)
```bash
curl -X POST https://day12ha-tang-cloudvadeployment-production-128b.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# ✅ {"detail":"Invalid or missing API key. Include header: X-API-Key: <key>"}
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

## Docker Image Details
- **Base:** `python:3.11-slim` (multi-stage build)
- **Final image size:** ~195 MB (< 500 MB requirement ✅)
- **User:** Non-root `agent` user
- **Health check:** Built-in Docker HEALTHCHECK instruction

## Security Features
- ✅ API Key authentication (`X-API-Key` header)
- ✅ Rate limiting (20 req/min per user)
- ✅ Cost guard ($5/day budget)
- ✅ Security headers (nosniff, DENY frame)
- ✅ No hardcoded secrets
- ✅ Non-root container user
- ✅ `.env` files in `.gitignore`
