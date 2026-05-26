# 🤖 Gemini AI Chatbot Backend

A clean, modular, production-style FastAPI backend powered by **Google Gemini AI**.  
Built for scalability — ready to grow from MVP to enterprise with minimal refactoring.

---

## ✨ Features

- **Google Gemini AI** — Powered by `gemini-1.5-flash` (fast, free-tier friendly)
- **Multi-turn Memory** — Session-based conversation history
- **Intent Classification** — Detects SIMPLE vs COMPLEX requests
- **Agent Escalation** — COMPLEX requests get `[ESCALATE_TO_AGENT]` signal
- **Input Sanitization** — Cleans and validates every user message
- **Rate Limiting** — Per-IP sliding-window rate limiter
- **CORS Ready** — Frontend can connect from any origin (configurable)
- **Auto API Docs** — Swagger UI at `/docs`, ReDoc at `/redoc`
- **SQLite → PostgreSQL** — Swap DB with one environment variable

---

## 📁 Project Structure

```
backend/
├── app/
│   ├── main.py                       ← App bootstrap, CORS, startup
│   ├── routes/
│   │   └── chat.py                   ← HTTP endpoints (thin layer)
│   ├── services/
│   │   ├── gemini_service.py         ← All Gemini API communication
│   │   ├── intent_classifier.py      ← SIMPLE / COMPLEX detection
│   │   └── memory_service.py         ← Session conversation memory
│   ├── core/
│   │   ├── config.py                 ← All settings from .env
│   │   └── security.py               ← Sanitization + rate limiting
│   ├── models/
│   │   └── chat_models.py            ← Pydantic request/response schemas
│   ├── utils/
│   │   └── helpers.py                ← Logging, text utilities
│   └── database/
│       └── db.py                     ← SQLAlchemy engine + session
├── requirements.txt
├── .env                              ← Your secrets (NEVER commit this)
└── README.md
```

---

## ⚡ Quick Start

### Prerequisites
- Python **3.11+**
- A **Gemini API key** (free) → [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

---

### Step 1 — Navigate to the backend folder

```bash
cd backend
```

### Step 2 — Create a virtual environment

```bash
# Create
python -m venv venv

# Activate — macOS / Linux
source venv/bin/activate

# Activate — Windows
venv\Scripts\activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Configure environment variables

Open `.env` and set your Gemini API key:

```env
GEMINI_API_KEY=your-actual-api-key-here
```

Optionally customize your bot's personality:

```env
SYSTEM_INSTRUCTION="You are a helpful support agent for Acme Corp..."
```

### Step 5 — Run the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**The server is now running at:** `http://localhost:8000`

| URL | Purpose |
|-----|---------|
| http://localhost:8000/ | Health check |
| http://localhost:8000/docs | Swagger UI (interactive testing) |
| http://localhost:8000/redoc | ReDoc API documentation |
| http://localhost:8000/health | Health check for monitoring tools |

---

## 📡 API Reference

### `POST /api/v1/chat` — Send a message

**Request:**
```json
{
  "message": "Hello! What can you help me with?",
  "session_id": "sess-abc-123"
}
```

**Response (SIMPLE intent):**
```json
{
  "reply": "Hello! I'm your AI assistant powered by Gemini. I can help you with...",
  "intent": "SIMPLE",
  "session_id": "sess-abc-123",
  "escalate": false,
  "model_used": "gemini-1.5-flash",
  "turn_count": 2
}
```

**Response (COMPLEX intent — escalation):**
```json
{
  "reply": "[ESCALATE_TO_AGENT] Your request involves a complex task...",
  "intent": "COMPLEX",
  "session_id": "sess-abc-123",
  "escalate": true,
  "model_used": null,
  "turn_count": 0
}
```

---

### `GET /api/v1/chat/session/{session_id}` — Session info

```bash
curl http://localhost:8000/api/v1/chat/session/sess-abc-123
```

**Response:**
```json
{
  "session_id": "sess-abc-123",
  "exists": true,
  "turn_count": 4,
  "message": "Session has 4 stored turns."
}
```

---

### `DELETE /api/v1/chat/session/{session_id}` — Clear memory

```bash
curl -X DELETE http://localhost:8000/api/v1/chat/session/sess-abc-123
```

**Response:**
```json
{
  "success": true,
  "session_id": "sess-abc-123",
  "message": "Session 'sess-abc-123' cleared successfully."
}
```

---

## 🧪 Testing the API

### With curl:

```bash
# Basic chat (server generates a new session_id)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Google Gemini?"}'

# Multi-turn conversation (reuse session_id from previous response)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "My favourite colour is blue.", "session_id": "sess-test-001"}'

curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is my favourite colour?", "session_id": "sess-test-001"}'

# Complex request (triggers ESCALATE_TO_AGENT)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Build me a complete e-commerce web application with payment integration"}'
```

### With Swagger UI:

1. Open **http://localhost:8000/docs**
2. Click `POST /api/v1/chat`
3. Click **"Try it out"**
4. Enter your message JSON and click **Execute**

---

## 🌐 Frontend Integration

Replace the `getBotReply()` function in your `chatbot.js` with:

```javascript
// ─────────────────────────────────────────────────────────────
// chatbot.js — Gemini Backend Integration
// Replace your existing getBotReply() function with this.
// ─────────────────────────────────────────────────────────────

const BACKEND_URL = "http://localhost:8000/api/v1";

// Persist session ID across messages (same tab session)
let sessionId = null;

async function getBotReply(userMessage) {
  try {
    const response = await fetch(`${BACKEND_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: userMessage,
        session_id: sessionId,       // null on first message → backend creates one
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error("Backend error:", response.status, errorData);
      return "Sorry, something went wrong. Please try again.";
    }

    const data = await response.json();

    // Save the session_id for subsequent messages (enables memory)
    if (data.session_id) {
      sessionId = data.session_id;
    }

    // Handle agent escalation (COMPLEX intent)
    if (data.escalate) {
      console.log("Complex request — escalating to agent");
      // Future: trigger human-handoff UI, show special message style, etc.
    }

    return data.reply;

  } catch (networkError) {
    console.error("Network error:", networkError);
    return "I'm having trouble connecting. Please check your internet and try again.";
  }
}

// Optional: call when user clicks "New Chat" button
async function startNewChat() {
  if (!sessionId) return;
  try {
    await fetch(`${BACKEND_URL}/chat/session/${sessionId}`, {
      method: "DELETE",
    });
    console.log("Session cleared:", sessionId);
    sessionId = null;
  } catch (err) {
    console.error("Failed to clear session:", err);
  }
}
```

---

## 🚀 Scalability Roadmap

### Phase 1 — Current (MVP) ✅
- FastAPI + Gemini 1.5 Flash
- In-memory session history
- Intent classification (SIMPLE / COMPLEX)
- Input sanitization + rate limiting

### Phase 2 — Production Hardening
- [ ] Redis for session storage (TTL-based, multi-instance)
- [ ] PostgreSQL for persistent conversation logs
- [ ] Redis + slowapi for distributed rate limiting
- [ ] JWT authentication for user accounts
- [ ] Docker + docker-compose deployment
- [ ] Structured JSON logging (Datadog, CloudWatch)

### Phase 3 — Agentic Upgrade
- [ ] LangChain + Gemini for multi-step agents
- [ ] Tool calling: web search, code execution, calendar
- [ ] Gemini function calling API integration
- [ ] Streaming responses (Server-Sent Events)
- [ ] Specialized sub-agents per intent category

### Phase 4 — Enterprise
- [ ] RAG with vector DB (Pinecone, pgvector) for knowledge base
- [ ] Fine-tuned Gemini models for your domain
- [ ] Multi-tenant architecture (per-org configs)
- [ ] Human-in-the-loop handoff (Intercom, Zendesk)
- [ ] Analytics dashboard (conversation insights)

---

## 🛡️ Security Checklist

- [x] API key loaded from .env (never hardcoded)
- [x] Input sanitization on every request
- [x] CORS restricted to known origins
- [x] Rate limiting per IP address
- [x] Max message length enforced (2000 chars)
- [x] Control character removal from inputs
- [ ] Add `.env` to `.gitignore` ← **Do this now**
- [ ] HTTPS (handle at reverse proxy — nginx / Caddy)
- [ ] JWT auth for protected routes (Phase 2)

---

## 🐳 Docker (Optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build
docker build -t gemini-chatbot-backend .

# Run (with .env file)
docker run -p 8000:8000 --env-file .env gemini-chatbot-backend
```

---

## 🔧 Changing the AI Model

Update `GEMINI_MODEL` in `.env`:

| Model | Speed | Quality | Cost |
|-------|-------|---------|------|
| `gemini-1.5-flash` | ⚡⚡⚡ | ⭐⭐⭐ | Free tier |
| `gemini-1.5-pro` | ⚡⚡ | ⭐⭐⭐⭐⭐ | Paid |
| `gemini-2.0-flash-exp` | ⚡⚡⚡ | ⭐⭐⭐⭐ | Experimental |

No code changes needed — just update `.env` and restart.

---

## 📜 License

MIT — free for personal and commercial use.