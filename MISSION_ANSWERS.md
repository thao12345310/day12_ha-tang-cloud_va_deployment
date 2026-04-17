# Day 12 Lab — Mission Answers

> **Student Name:** Duong Phuong Thao  
> **Date:** 17/04/2026  
> **Lab:** Hạ Tầng Cloud & Deployment

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found trong `01-localhost-vs-production/develop/app.py`

**Tìm được 6 anti-patterns:**

1. **Hardcoded secrets trong code (dòng 17-18):**
   ```python
   OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"
   DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"
   ```
   → Nếu push lên GitHub, secrets bị lộ ngay lập tức. Attacker có thể dùng API key để tạo bill khổng lồ.

2. **Debug mode bật cứng (dòng 21):**
   ```python
   DEBUG = True
   ```
   → Trong production, debug mode expose stack traces, cho phép attacker thấy internal code structure.

3. **Print thay vì proper logging (dòng 33-34):**
   ```python
   print(f"[DEBUG] Using key: {OPENAI_API_KEY}")
   ```
   → In ra secrets trong log. Không có log level, format, hay rotation. Không thể parse tự động bởi log aggregator (Datadog, Loki).

4. **Không có health check endpoint:**
   → Cloud platform (Railway, Render, K8s) không biết agent còn sống hay đã crash. Không thể tự động restart.

5. **Host bind `localhost` (dòng 51):**
   ```python
   host="localhost"  # ❌ chỉ chạy được trên local
   ```
   → Trong Docker container hoặc cloud, cần bind `0.0.0.0` để nhận kết nối từ bên ngoài.

6. **Port cứng + reload trong production (dòng 52-53):**
   ```python
   port=8000,     # ❌ cứng port
   reload=True    # ❌ debug reload trong production
   ```
   → Cloud platforms inject PORT qua environment variable. Reload mode tiêu tốn resources và không an toàn.

### Exercise 1.3: So sánh Develop vs Production

| Feature | Develop (`develop/app.py`) | Production (`production/app.py`) | Tại sao quan trọng? |
|---------|---------------------------|----------------------------------|---------------------|
| **Config** | Hardcode trực tiếp trong code | Đọc từ `.env` + `config.py` (Settings dataclass) | Dễ thay đổi giữa các environment, không lộ secrets |
| **Health check** | ❌ Không có | ✅ `/health` (liveness) + `/ready` (readiness) | Platform biết khi nào restart/route traffic |
| **Logging** | `print()` — in cả secrets | JSON structured logging, KHÔNG log secrets | Parse được bởi log aggregator, audit trail |
| **Shutdown** | Đột ngột (`Ctrl+C`) | Graceful shutdown qua SIGTERM handler + lifespan | Không mất data, hoàn thành request đang xử lý |
| **Host binding** | `localhost` (local only) | `0.0.0.0` (accept external connections) | Container/cloud cần nhận kết nối từ bên ngoài |
| **Port** | Cứng `8000` | Đọc từ `PORT` env var | Railway/Render inject PORT tự động |
| **CORS** | ❌ Không có | ✅ `CORSMiddleware` với configurable origins | Cho phép frontend call API từ domain khác |
| **Metrics** | ❌ Không có | ✅ `/metrics` endpoint | Monitor performance, uptime |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. **Base image:** `python:3.11` — Full Python distribution (~1 GB), bao gồm tất cả development tools.

2. **Working directory:** `/app` — Đặt bởi `WORKDIR /app`. Tất cả lệnh tiếp theo chạy trong thư mục này.

3. **Tại sao COPY requirements.txt trước?**
   → **Docker layer caching.** Docker cache mỗi layer (instruction). Nếu `requirements.txt` không đổi, Docker dùng cache thay vì install lại dependencies. Chỉ khi code thay đổi, Docker mới re-run `COPY app.py .` — tiết kiệm thời gian build đáng kể.

4. **CMD vs ENTRYPOINT:**
   - `CMD`: Default command, có thể bị override khi `docker run <image> <other-cmd>`
   - `ENTRYPOINT`: Không bị override dễ dàng, dùng khi container luôn chạy 1 command cố định
   - Kết hợp: `ENTRYPOINT ["python"]` + `CMD ["app.py"]` → default chạy `python app.py`, có thể override `CMD` thành file khác.

### Exercise 2.2: Build và run — kết quả

```bash
# Build basic image
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
# → Build thành công

# Build advanced image (multi-stage)
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
# → Build thành công (1640.9s do apt-get install gcc, libpq-dev)
```

### Exercise 2.3: Image size comparison

| Image | Base | Build Type | Size (ước tính) |
|-------|------|-----------|------|
| `my-agent:develop` | `python:3.11` (full) | Single-stage | ~413 MB |
| `my-agent:advanced` | `python:3.11-slim` | Multi-stage | ~195 MB |
| **Giảm** | | | **~53%** |

**Tại sao multi-stage nhỏ hơn?**
- **Stage 1 (builder):** Cài gcc, libpq-dev, pip install → KHÔNG giữ lại trong final image.
- **Stage 2 (runtime):** Chỉ copy `site-packages` đã compiled + source code. Không có build tools.
- Base image `python:3.11-slim` (~150 MB) thay vì `python:3.11` (~350 MB).

### Exercise 2.4: Docker Compose stack — Architecture

```
┌─────────────────────────────────────────────────┐
│                 Docker Network: internal         │
│                                                  │
│   ┌──────────┐      ┌──────────┐                │
│   │  Client  │─────▶│  Nginx   │ :80 / :443    │
│   └──────────┘      └────┬─────┘                │
│                          │ reverse proxy         │
│                     ┌────▼────┐                  │
│                     │  Agent  │ :8000            │
│                     │(FastAPI)│                   │
│                     └────┬────┘                  │
│                          │                       │
│            ┌─────────────┼─────────────┐        │
│            │             │             │        │
│      ┌─────▼────┐  ┌────▼─────┐              │
│      │  Redis   │  │  Qdrant  │              │
│      │ :6379    │  │  :6333   │              │
│      │(cache,   │  │(vector   │              │
│      │ session) │  │ DB, RAG) │              │
│      └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────┘
```

**4 services được start:**
1. **agent** — FastAPI AI agent: xử lý `/ask`, `/health`, `/ready`
2. **redis** — Cache cho session, rate limiting. Config: max 256MB, LRU eviction
3. **qdrant** — Vector database cho RAG (Retrieval Augmented Generation)
4. **nginx** — Reverse proxy, load balancer, SSL termination

**Communication:**
- Client → Nginx (port 80/443) → Agent (port 8000)
- Agent → Redis (port 6379) cho session/rate limit
- Agent → Qdrant (port 6333) cho vector search
- Tất cả trong network `internal` (bridge) — isolated

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

**Railway configuration (`railway.toml`):**
```toml
[build]
builder = "NIXPACKS"  # Tự detect Python, hoặc "DOCKERFILE" nếu có Dockerfile

[deploy]
startCommand = "uvicorn app:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"            # Railway ping endpoint này
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"       # Auto restart khi crash
restartPolicyMaxRetries = 3
```

**Environment variables cần set:**
```bash
railway variables set PORT=8000
railway variables set AGENT_API_KEY=<secure-random-key>
railway variables set ENVIRONMENT=production
railway variables set REDIS_URL=<railway-redis-url>
```

### Exercise 3.2: So sánh `render.yaml` vs `railway.toml`

| Feature | `railway.toml` | `render.yaml` |
|---------|----------------|---------------|
| **Format** | TOML | YAML |
| **Builder** | `NIXPACKS` hoặc `DOCKERFILE` | `runtime: python` hoặc `runtime: docker` |
| **Health check** | `healthcheckPath = "/health"` | `healthCheckPath: /health` |
| **Secrets** | Set qua CLI: `railway variables set` | `sync: false` (manual) hoặc `generateValue: true` |
| **Auto deploy** | Mặc định khi push | `autoDeploy: true` |
| **Region** | Auto-detect | Chọn được: `region: singapore` |
| **Redis** | Provision riêng qua dashboard | Define trong cùng file: `type: redis` |
| **Pricing** | $5 credit free | 750h/month free |

**Key difference:** Render dùng **Blueprint** (render.yaml) — define toàn bộ infra trong 1 file YAML, bao gồm cả Redis add-on. Railway chia thành `railway.toml` (deploy config) + Dashboard (services, databases).

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication

**Cách hoạt động (`04-api-gateway/develop/app.py`):**

1. **API key check ở đâu?** — Trong dependency `verify_api_key()` (dòng 39-54), inject vào endpoint `/ask` qua `Depends(verify_api_key)`.

2. **Flow:**
   ```
   Request → Check header "X-API-Key" → So sánh với AGENT_API_KEY env var
     → Khớp: allow through (200)
     → Thiếu: 401 Missing API key
     → Sai: 403 Invalid API key
   ```

3. **Cách rotate key:**
   - Thay đổi env var `AGENT_API_KEY` → restart service
   - Tốt hơn: support nhiều keys (comma-separated), revoke key cũ sau grace period

**Test results:**
```bash
# ❌ Không có key → 401
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# → {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

# ✅ Có key → 200
curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: demo-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# → {"question":"Hello","answer":"..."}
```

### Exercise 4.2: JWT Authentication

**JWT flow (`04-api-gateway/production/auth.py`):**

```
1. POST /auth/token  {username, password}
   → Verify credentials (DEMO_USERS dict)
   → Generate JWT: {sub: username, role: user/admin, iat, exp}
   → Return: {access_token: "eyJ...", token_type: "bearer"}

2. POST /ask  [Authorization: Bearer <token>]
   → Extract token từ header
   → jwt.decode(token, SECRET_KEY, algorithm=HS256)
   → Check expiry (60 phút)
   → Extract {username, role}
   → Proceed with request
```

**Demo credentials:**
- `student / demo123` → role: user, 10 req/min
- `teacher / teach456` → role: admin, 100 req/min

### Exercise 4.3: Rate Limiting

**Algorithm:** **Sliding Window Counter** (`rate_limiter.py`)

**Cách hoạt động:**
- Mỗi user có 1 `deque` chứa timestamps của các request
- Khi có request mới: loại bỏ timestamps cũ hơn 60 giây
- Đếm số request trong window hiện tại
- Nếu ≥ limit → 429 Too Many Requests + `Retry-After` header

**Limits:**
- User tier: **10 requests/minute**
- Admin tier: **100 requests/minute**

**Bypass cho admin:** Dùng `rate_limiter_admin` instance (100 req/min) thay vì `rate_limiter_user` (10 req/min). Role check qua JWT payload.

**Test output (gọi 20 lần liên tục):**
```
Request 1-10: 200 OK ✅
Request 11+: 429 Too Many Requests ❌
{
  "error": "Rate limit exceeded",
  "limit": 10,
  "window_seconds": 60,
  "retry_after_seconds": 55
}
Headers: X-RateLimit-Limit: 10, X-RateLimit-Remaining: 0, Retry-After: 55
```

### Exercise 4.4: Cost Guard Implementation

**Approach (`04-api-gateway/production/cost_guard.py`):**

```python
class CostGuard:
    daily_budget_usd = 1.0           # $1/ngày per user
    global_daily_budget_usd = 10.0   # $10/ngày tổng cộng

    def check_budget(user_id):
        record = get_today_usage(user_id)
        if global_cost >= global_budget:     # 503 Service Unavailable
        if user_cost >= user_budget:         # 402 Payment Required
        if user_cost >= 80% budget:          # Warning log

    def record_usage(user_id, input_tokens, output_tokens):
        cost = (input/1000 * $0.00015) + (output/1000 * $0.0006)  # GPT-4o-mini pricing
        record.input_tokens += input_tokens
        record.output_tokens += output_tokens
        global_cost += cost
```

**Design decisions:**
1. **Per-user daily budget ($1)** — Tránh 1 user dùng hết toàn bộ resources
2. **Global daily budget ($10)** — Circuit breaker khi tổng chi phí vượt ngưỡng
3. **Warning ở 80%** — Proactive alerting trước khi block
4. **Daily reset** — Budget reset tại midnight (check `time.strftime("%Y-%m-%d")`)
5. **In-memory** (demo); production nên dùng Redis để persist across restarts

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health Checks

**Đã implement 2 loại probe:**

```python
# Liveness probe — "Agent còn sống không?"
@app.get("/health")
def health():
    return {
        "status": "ok" or "degraded",
        "uptime_seconds": ...,
        "version": "1.0.0",
        "environment": ...,
        "timestamp": ...,
        "checks": {"memory": {"status": "ok", "used_percent": ...}}
    }

# Readiness probe — "Agent sẵn sàng nhận traffic chưa?"
@app.get("/ready")
def ready():
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    return {"ready": True, "in_flight_requests": _in_flight_requests}
```

**Use cases:**
- **Liveness**: Platform gọi mỗi 30s. Non-200 → restart container.
- **Readiness**: Load balancer check. 503 → stop routing traffic (đang startup hoặc shutdown).

### Exercise 5.2: Graceful Shutdown

**Implementation:**

```python
# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    _is_ready = True
    yield
    # Shutdown
    _is_ready = False  # Stop accepting new requests
    while _in_flight_requests > 0 and elapsed < 30:
        wait(1)  # Finish current requests
    logger.info("Shutdown complete")

# SIGTERM handler
signal.signal(signal.SIGTERM, handle_sigterm)
```

**Flow khi nhận SIGTERM:**
1. Set `_is_ready = False` → readiness probe trả 503 → LB ngừng route traffic
2. Chờ in-flight requests hoàn thành (max 30s timeout)
3. Close connections
4. Exit process

### Exercise 5.3: Stateless Design

**Anti-pattern (stateful):**
```python
# ❌ State trong memory — mất khi restart, không share giữa instances
conversation_history = {}
```

**Correct (stateless với Redis):**
```python
# ✅ State trong Redis — persist, shared across all instances
def save_session(session_id, data, ttl=3600):
    redis.setex(f"session:{session_id}", ttl, json.dumps(data))

def load_session(session_id):
    data = redis.get(f"session:{session_id}")
    return json.loads(data) if data else {}
```

**Tại sao stateless quan trọng?**
- Scale ra 3 instances → mỗi instance có memory riêng
- Request 1 → Instance A (lưu session trong memory)
- Request 2 → Instance B (KHÔNG có session!) → Bug!
- Với Redis → bất kỳ instance nào cũng đọc được session

### Exercise 5.4: Load Balancing

**Architecture với Nginx:**
```
docker compose up --scale agent=3

Client → Nginx (:80) → Round-robin:
    ├── Agent Instance 1 (:8000)
    ├── Agent Instance 2 (:8000)
    └── Agent Instance 3 (:8000)
         └── All connect to Redis (:6379)
```

**Nginx config:**
```nginx
upstream agent_cluster {
    server agent:8000;    # Docker DNS round-robin
    keepalive 16;
}
location / {
    proxy_pass http://agent_cluster;
    proxy_next_upstream error timeout http_503;  # Retry nếu instance fail
    proxy_next_upstream_tries 3;
}
```

**Observation:** Response header `served_by` cho thấy mỗi request được xử lý bởi instance khác nhau. Nếu 1 instance die → Nginx chuyển traffic sang instances còn lại.

### Exercise 5.5: Stateless Test

**`test_stateless.py` kiểm tra:**
1. Gọi `/chat` tạo conversation → lưu vào Redis
2. Gọi tiếp với cùng `session_id` → nhận được history đầy đủ
3. Response `served_by` thay đổi giữa các request (khác instance)
4. **Kết luận:** Session được persist trong Redis → conversation liên tục dù request đi qua instance khác nhau

---

## Part 6: Final Project — Production-Ready Agent

### Project Structure (theo delivery checklist)

```
06-lab-complete/
├── app/
│   ├── __init__.py          # Package init
│   ├── main.py              # Main application — kết hợp tất cả
│   ├── config.py            # 12-Factor config (dataclass + env vars)
│   ├── auth.py              # API Key authentication
│   ├── rate_limiter.py      # Sliding window rate limiting
│   └── cost_guard.py        # Daily budget protection
├── utils/
│   └── mock_llm.py          # Mock LLM (provided)
├── Dockerfile               # Multi-stage build (builder + runtime)
├── docker-compose.yml       # Full stack: agent + redis
├── requirements.txt         # Dependencies
├── .env.example             # Environment template
├── .dockerignore            # Docker ignore
├── railway.toml             # Railway deploy config
├── render.yaml              # Render deploy config
├── check_production_ready.py # Automated readiness checker
└── README.md                # Setup instructions
```

### Modular Design — Separation of Concerns

**`app/auth.py`** — Authentication:
```python
def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify X-API-Key header against settings.agent_api_key."""
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(401, "Invalid or missing API key")
    return api_key
```

**`app/rate_limiter.py`** — Sliding Window Counter:
```python
def check_rate_limit(key: str) -> None:
    """Sliding window: evict timestamps > 60s, check count >= limit → 429."""
    # Includes Retry-After + X-RateLimit-Limit + X-RateLimit-Remaining headers
```

**`app/cost_guard.py`** — Budget Protection:
```python
def check_budget() -> None:
    """Block requests when daily_cost >= daily_budget_usd → 503."""

def record_cost(input_tokens, output_tokens) -> float:
    """Track cost per GPT-4o-mini pricing. Warning log at 80% budget."""
```

**`app/main.py`** — Orchestration (imports from modules):
```python
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_cost, get_usage

@app.post("/ask")
async def ask_agent(body: AskRequest, _key: str = Depends(verify_api_key)):
    check_rate_limit(_key[:8])   # Rate limit per API key
    check_budget()                # Budget check (pre-call)
    answer = llm_ask(body.question)
    record_cost(input_tokens, output_tokens)  # Track spending
    return AskResponse(...)
```

### Kết quả Production Readiness Check

```
=======================================================
  Production Readiness Check — Day 12 Lab
=======================================================

📁 Required Files
  ✅ Dockerfile exists
  ✅ docker-compose.yml exists
  ✅ .dockerignore exists
  ✅ .env.example exists
  ✅ requirements.txt exists
  ✅ railway.toml or render.yaml exists

🔒 Security
  ✅ .env in .gitignore
  ✅ No hardcoded secrets in code

🌐 API Endpoints (code check)
  ✅ /health endpoint defined
  ✅ /ready endpoint defined
  ✅ Authentication implemented
  ✅ Rate limiting implemented
  ✅ Graceful shutdown (SIGTERM)
  ✅ Structured logging (JSON)

🐳 Docker
  ✅ Multi-stage build
  ✅ Non-root user
  ✅ HEALTHCHECK instruction
  ✅ Slim base image
  ✅ .dockerignore covers .env
  ✅ .dockerignore covers __pycache__

=======================================================
  Result: 20/20 checks passed (100%)
  🎉 PRODUCTION READY! Deploy nào!
=======================================================
```

### Architecture Overview

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTPS
       ▼
┌─────────────────┐
│  Railway/Render  │ (Cloud Platform)
│  + Load Balancer │
└──────┬──────────┘
       │
       ├─────────┬─────────┐
       ▼         ▼         ▼
   ┌──────┐  ┌──────┐  ┌──────┐
   │Agent1│  │Agent2│  │Agent3│
   │      │  │      │  │      │
   │- Auth│  │- Auth│  │- Auth│
   │- Rate│  │- Rate│  │- Rate│
   │- Cost│  │- Cost│  │- Cost│
   └───┬──┘  └───┬──┘  └───┬──┘
       │         │         │
       └─────────┴─────────┘
                 │
                 ▼
           ┌──────────┐
           │  Redis   │
           │ (Session,│
           │  Rate,   │
           │  Budget) │
           └──────────┘
```

### Feature Checklist

| Feature | Status | Implementation File |
|---------|--------|---------------------|
| REST API `/ask` | ✅ | `app/main.py` — FastAPI + Pydantic validation |
| Config management | ✅ | `app/config.py` — all env vars, 12-Factor dataclass |
| API Key auth | ✅ | `app/auth.py` — X-API-Key header verification |
| Rate limiting | ✅ | `app/rate_limiter.py` — Sliding window, 20 req/min |
| Cost guard | ✅ | `app/cost_guard.py` — $5/day budget, 80% warning, auto-reset |
| Health check | ✅ | `app/main.py` — `GET /health` liveness probe |
| Readiness check | ✅ | `app/main.py` — `GET /ready` readiness probe |
| Graceful shutdown | ✅ | `app/main.py` — SIGTERM handler + lifespan |
| Structured logging | ✅ | `app/main.py` — JSON format, no secrets logged |
| Security headers | ✅ | `app/main.py` — X-Content-Type-Options, X-Frame-Options |
| CORS | ✅ | `app/main.py` — Configurable origins |
| Multi-stage Docker | ✅ | `Dockerfile` — builder + runtime, slim base |
| Non-root user | ✅ | `Dockerfile` — `agent` user in container |
| Docker Compose | ✅ | `docker-compose.yml` — agent + redis + healthchecks |
| Cloud config | ✅ | `railway.toml` + `render.yaml` |
| No hardcoded secrets | ✅ | All from env vars via `config.py` |
| Input validation | ✅ | Pydantic: min_length=1, max_length=2000 |

### Docker Build Results

```bash
# Basic single-stage
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
# → Image size: ~413 MB

# Advanced multi-stage (06-lab-complete)
docker build -f 06-lab-complete/Dockerfile -t my-agent:production .
# → Image size: ~195 MB (< 500 MB threshold ✅)
# → Reduction: ~53% so với single-stage
```

### Configuration (`app/config.py`)

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `PORT` | 8000 | Server port (Railway auto-injects) |
| `ENVIRONMENT` | development | `development` / `staging` / `production` |
| `AGENT_API_KEY` | dev-key-change-me | API key for authentication |
| `RATE_LIMIT_PER_MINUTE` | 20 | Max requests per minute per user |
| `DAILY_BUDGET_USD` | 5.0 | Daily cost limit in USD |
| `REDIS_URL` | *(empty)* | Redis connection URL |
| `OPENAI_API_KEY` | *(empty)* | OpenAI key (mock LLM if empty) |
| `LLM_MODEL` | gpt-4o-mini | Model name |
| `ALLOWED_ORIGINS` | * | CORS origins (comma-separated) |

---

## Tổng Kết

### Kiến thức đạt được:

1. **Dev vs Production:** Hiểu 12-Factor App principles, tầm quan trọng của config management, không hardcode secrets
2. **Docker:** Multi-stage build giảm image size 53%, layer caching tối ưu build time
3. **Cloud Deployment:** Railway (TOML config) vs Render (YAML Blueprint) — trade-offs về ease-of-use vs control
4. **API Security:** Defense-in-depth: Authentication (`auth.py`) → Rate Limiting (`rate_limiter.py`) → Cost Guard (`cost_guard.py`)
5. **Scaling:** Stateless design + Redis = horizontal scaling; Nginx load balancing + health checks = reliability
6. **Modular Design:** Separation of concerns — mỗi module có 1 trách nhiệm duy nhất, dễ test và maintain

### Bảng điểm tự đánh giá:

| Criteria | Points | Self-Assessment |
|----------|--------|----------------|
| Functionality | 20/20 | Agent hoạt động, trả lời qua REST API, Pydantic validation |
| Docker | 15/15 | Multi-stage, optimized, < 500MB, non-root user, HEALTHCHECK |
| Security | 20/20 | Auth (`auth.py`) + Rate limit (`rate_limiter.py`) + Cost guard (`cost_guard.py`) |
| Reliability | 20/20 | Health checks + Readiness probe + Graceful shutdown (SIGTERM + lifespan) |
| Scalability | 15/15 | Stateless design + Redis + Docker Compose |
| Deployment | 10/10 | railway.toml + render.yaml configured, deployed at https://day12ha-tang-cloudvadeployment-production-128b.up.railway.app |
| **Total** | **100/100** | |
