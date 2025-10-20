# AmIABot.com MVP 🤖

A modern Turing Test game built with **Flask** and **Socket.IO**, where players chat in real time and try to guess whether their partner is **a human or an AI**.

This is a functional MVP (minimum viable product) using in-memory state (`FakeRedis`) and OpenAI’s API for the bot’s responses.

---

## 🎯 What It Does

- **Instant Play**: No login — users join and are paired automatically.
- **Real-Time Chat**: Uses Flask-SocketIO for low-latency messaging.
- **Human-First Matching**: Tries to match players with other humans; if none found, pairs with an AI bot after 15–25 seconds.
- **Turing Test Gameplay**: 3-minute chat → 30-second decision → reveal.
- **AI Bot Partner**: Uses GPT-3.5 with human-like tone, timing, and small imperfections.
- **Fallback Mode**: Bot still replies with canned human-like messages if OpenAI API fails.
- **Self-contained**: No database or Redis needed — runs entirely in memory.

---

## 🧩 Project Structure

```
amiabot/
├── app.py              # Flask + Socket.IO server and event handlers
├── bot.py              # GPT-powered Turing bot logic
├── config.py           # Environment-based configuration
├── game_state.py       # Thread-safe in-memory matchmaking and session tracking
├── templates/
│   └── index.html      # Frontend (WebSocket chat UI)
└── README.md
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|-----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | **Required** |
| `SECRET_KEY` | Flask secret key | Randomly generated |
| `PORT` | Port for Flask to bind | `5000` |
| `QUEUE_WAIT_TIME` | How long to wait for human before fallback | `30` |
| `CONVERSATION_TIME` | Chat duration (seconds) | `180` |
| `DECISION_TIME` | Decision phase duration | `30` |

No Redis, database, or API credentials (other than OpenAI) are required.

---

## 🚀 Running Locally

### 1. Install requirements
```bash
pip install -r requirements.txt
```

### 2. Add your OpenAI key
Create a `.env` file:
```
OPENAI_API_KEY=sk-your-key
```

### 3. Run the app
```bash
python app.py
```

### 4. Open your browser
Go to: [http://localhost:5000](http://localhost:5000)

You can open two tabs to test human-to-human matching.

---

## 💬 Game Flow

1. **Queue Phase** – You join a matchmaking queue.  
   If no human is found within ~20 seconds, a bot is assigned.
2. **Chat Phase** – 3-minute real-time conversation.
3. **Decision Phase** – You guess if your partner was a **Bot** or **Human**.
4. **Results** – Truth is revealed!

---

## 🤖 The AI Bot

- Powered by **OpenAI GPT-3.5-Turbo**
- Uses a detailed “personality prompt” to sound natural
- Mimics human delays (1–4 s response)
- Adds casual imperfections (typos, slang, “lol”, etc.)
- Uses canned replies if API fails (no downtime)

---

## 🧠 Architecture

| Layer | Technology |
|-------|-------------|
| Web framework | Flask |
| Realtime engine | Flask-SocketIO |
| Storage | In-memory via FakeRedis |
| AI | OpenAI GPT-3.5-Turbo |
| Frontend | Simple HTML + JS (Socket.IO client) |

---

## 🏗️ Deploying on Render

Render automatically detects Python apps and sets the `$PORT` variable.

### 1. Add `wsgi.py`

```python
from app import app, socketio

if __name__ == "__main__":
    socketio.run(app)
```

### 2. Add `render.yaml`

```yaml
services:
  - type: web
    name: amiabot
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --worker-class eventlet -w 1 wsgi:app
    envVars:
      - key: OPENAI_API_KEY
        sync: false
      - key: SECRET_KEY
        generateValue: true
```

### 3. Add to `requirements.txt`

```
gunicorn
eventlet
```

That’s it — push to GitHub and connect the repo to Render.

---

## 🔍 Debugging & Health Checks

| Endpoint | Description |
|-----------|--------------|
| `/health` | Simple “OK” check |
| `/stats` | Returns queue and session counts |
| `/debug` | Shows active sessions (for development only) |
| `/test_bot` | Tests bot connectivity |

Logs show user connections, match events, and bot activity.

---

## 🧱 Limitations (MVP)

- Data is not persisted — resets on each restart.
- No user accounts or analytics.
- Only one default AI personality.
- Not designed for high concurrency (single server instance).

---

## 🪄 License

MIT License — free to use, modify, and deploy.

---

**Try it out, chat with the AI, and see if you can tell who’s real! 🤖🧠**
