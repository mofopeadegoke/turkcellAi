# 🇹🇷 Turkcell AI Agent

An AI-powered customer support system built for the **Turkcell competition**. This project provides an intelligent, multi-channel virtual assistant that helps Turkcell customers (especially tourists) with common telecom tasks — like checking their data balance, looking up account info, getting network status, troubleshooting connectivity issues, and finding the right mobile package — all through **WhatsApp**, **voice calls** (standard & streaming), or a **web chat interface**.

---

## 📖 What Does This Project Do?

Imagine you're a tourist visiting Turkey and you just bought a Turkcell SIM card. You have questions:

- *"How much data do I have left?"*
- *"Is there a network problem in my area?"*
- *"What package should I buy for my budget?"*
- *"My internet isn't working — can you help?"*

Instead of waiting on hold or navigating a website in an unfamiliar language, you can simply **send a WhatsApp message** or **make a phone call**, and an AI agent will understand your question, look up your account, and give you a helpful answer — in your preferred language.

### Key Features

- **📱 WhatsApp Support** — Chat with the AI agent via WhatsApp (powered by Twilio)
- **📞 Voice Call Support (Standard)** — Call and speak naturally; speech is converted to text, processed by AI, and the response is spoken back
- **⚡ Voice Call Support (Streaming)** — Advanced real-time audio streaming via WebSocket for lower-latency voice interactions (BETA)
- **💬 Web Chat Interface** — A Streamlit-based web UI for interactive chat with the AI agent
- **🤖 AI-Powered Responses** — Uses OpenAI GPT-4o to generate smart, context-aware answers
- **🔧 MCP (Model Context Protocol) Server** — Exposes 8 telecom tools (customer lookup, balance check, network status, package recommendations, knowledge base search, subscription management, smart diagnostics, device context) as callable functions for the AI
- **🌐 REST API Integration** — Connects to a dedicated Turkcell backend API (`turkcellaiapi.onrender.com`) for real-time customer data, subscriptions, balances, packages, troubleshooting, and support tickets
- **🌍 Multi-language Support** — Detects the customer's language from their speech content and responds accordingly
- **🔁 Provider Fallback** — If one AI provider fails, the system automatically falls back to another, ensuring reliability
- **🚀 Production-Ready Deployment** — Includes a Procfile for Railway/Heroku deployment with Gunicorn

---

## 🏗️ Project Structure

```
turkcellAi/
├── main.py                      # Main Flask web server (WhatsApp webhook, standard & streaming voice, health checks)
├── requirements.txt             # Python dependencies for the main Flask app
├── procfile                     # Deployment config (Gunicorn web server + MCP server process)
├── keep_alive.py                # Utility script to ping the API and keep it awake (Render free tier)
├── monitor_db.py                # Real-time database interaction monitor (watches interaction_history table)
├── seed_database.py             # Script to populate the database with test data
├── test_connection.py           # Script to test your Supabase database connection
├── test_api.py                  # Test script for API integration and language detection
├── .gitignore                   # Files and folders excluded from version control
│
├── app/                         # Core application modules
│   ├── __init__.py              # Package initializer
│   ├── config.py                # Loads environment variables (API keys, database URL, MCP path, etc.)
│   ├── database.py              # REST API client — wraps all Turkcell backend API calls (customers, packages, balances, troubleshooting, support tickets)
│   ├── voice_handler.py         # Standard voice call handler — speech-to-text, language detection, AI response, text-to-speech via AWS Polly
│   └── streaming_voice_handler.py  # Streaming voice handler — WebSocket-based real-time audio processing (BETA placeholder)
│
├── intelligence/                # AI orchestration layer
│   ├── intelligence_client.py   # Brain orchestrator — manages provider fallback, retries (1 retry), and 10s timeout
│   ├── openai_provider.py       # OpenAI GPT-4o provider — generates context-aware AI responses with customer data
│   ├── mcp_provider.py          # MCP provider — connects to the MCP server for tool-based AI responses with dual-channel formatting
│   └── safe_provider.py         # Safe fallback provider — returns a friendly error message if all providers fail
│
├── mcpsc/                       # MCP (Model Context Protocol) Server
│   ├── main.py                  # MCP server with 8 tool definitions (see table below)
│   ├── README.md                # MCP server readme (placeholder)
│   ├── pyproject.toml           # MCP server project configuration (uses uv package manager)
│   ├── .python-version          # Python version requirement (3.13+)
│   └── uv.lock                  # Locked dependencies for the MCP server
│
├── client/                      # Client applications that connect to the MCP server
│   ├── app.py                   # Streamlit web chat UI — interactive chat with AI + automatic MCP tool discovery
│   └── main.py                  # Simple CLI client example — demonstrates how to connect to the MCP server programmatically
│
└── services/                    # Additional service modules (reserved for future use)
```

---

## ⚙️ How It Works (Simple Explanation)

1. **A customer sends a message** (via WhatsApp, phone call, or web chat)
2. **The system identifies the customer** by looking up their phone number via the Turkcell REST API
3. **The AI processes the message** using OpenAI GPT-4o, with the customer's account info as context
4. **If the AI needs real data** (e.g., balance, network status, diagnostics), it calls tools on the **MCP server**, which fetches live data from the Turkcell backend API
5. **The AI sends back a personalized response** to the customer through the same channel

### The Intelligence Layer

The `IntelligenceClient` is the brain of the system. It:
- Tries the **MCP provider** first (which has access to all tools)
- If it fails, **automatically retries** (up to 1 time)
- If the MCP provider keeps failing, **falls back** to the OpenAI provider (which can chat but has no tools)
- If everything fails, returns a **safe, friendly error message** so the customer is never left hanging
- Has a **10-second timeout** to keep responses reliable

### The MCP Server

The MCP server exposes these tools that the AI can call:

| Tool | What It Does |
|------|-------------|
| `lookup_customer` | Find a customer by phone number or passport number |
| `get_balance_summary` | Check remaining data (GB), minutes, and SMS for a balance ID |
| `get_network_status_per_region` | Check if there are network issues in a specific region |
| `recommend_package` | Suggest the best mobile package based on budget, data needs, or stay duration |
| `search_knowledge_base` | Search Turkcell's internal knowledge base for troubleshooting guides and procedures |
| `get_active_subscriptions` | Fetch the list of active subscriptions for a customer |
| `run_smart_diagnostic` | Run a comprehensive system check (network, device settings, balance) for a subscription |
| `get_device_technical_context` | Get real-time device details (OS, model, roaming status, signal strength) |

### The Database / API Layer

The `app/database.py` module is a **REST API client** that wraps all calls to the Turkcell backend API. It provides functions for:
- **Customers** — Lookup, create, update, delete customers; get subscriptions
- **Packages** — List, filter by type, get recommendations, compare packages
- **Balances** — Get by subscription or phone, update, recharge, view usage history
- **Troubleshooting** — Device context, network status, knowledge base search, smart diagnostics, nearby stores
- **Support Tickets** — Create escalation tickets when the AI can't resolve an issue
- **Interactions** — Log all AI conversations for analytics

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.13+** (for the MCP server); Python 3.10+ should work for the main app
- **An OpenAI API key** — for GPT-4o
- **A Twilio account** — for WhatsApp and voice call integration
- **The Turkcell backend API** — the system connects to `turkcellaiapi.onrender.com` (or your own deployment)
- **uv** (optional) — for managing the MCP server dependencies

### 1. Clone the Repository

```bash
git clone https://github.com/mofopeadegoke/turkcellAi.git
cd turkcellAi
```

### 2. Set Up a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate          # Windows
```

### 3. Install Dependencies

For the main Flask application:

```bash
pip install -r requirements.txt
```

For the MCP server (inside the `mcpsc/` directory):

```bash
cd mcpsc
uv sync        # or: pip install "mcp[cli]>=1.26.0"
cd ..
```

### 4. Create a `.env` File

Create a file called `.env` in the root of the project and add your credentials:

```env
# OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# Twilio
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Turkcell Backend API
API_BASE_URL=https://turkcellaiapi.onrender.com
API_KEY=your_api_key_here

# Database (Supabase PostgreSQL — used by seed/test scripts)
DATABASE_URL=postgresql://postgres:your_password@db.your_project.supabase.co:5432/postgres
DATABASE_URL_DIRECT=postgresql://postgres:your_password@db.your_project.supabase.co:5432/postgres

# MCP Server
MCP_SERVER_PATH=mcpsc/main.py
```

### 5. Set Up the Database

First, test your database connection:

```bash
python test_connection.py
```

You should see a ✅ message confirming the connection. Then seed the database with test data:

```bash
python seed_database.py
```

This creates sample packages, a test customer, a subscription, and balance data so you can start testing right away.

### 6. Wake Up the API (if using Render free tier)

If the backend API is deployed on Render's free tier, it may be sleeping. Wake it up first:

```bash
python keep_alive.py
```

### 7. Run the Application

**Start the main Flask server (development):**

```bash
python main.py
```

The server will start and you can visit `http://localhost:5000` to see the status page.

**Start with Gunicorn (production):**

```bash
gunicorn main:app
```

**Start the Streamlit web chat (optional):**

```bash
cd client
streamlit run app.py
```

This opens an interactive web chat where you can talk to the AI agent directly in your browser.

---

## 🔗 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Home page — shows system status and available webhook endpoints |
| `/health` | GET | Health check — returns JSON with service status and timestamp |
| `/webhook` | POST | Webhook for incoming WhatsApp messages (configured in Twilio) |
| `/voice/incoming` | POST | Entry point for standard voice calls (configured in Twilio) |
| `/voice/process` | POST | Processes speech input from standard voice calls |
| `/voice/streaming` | POST | Entry point for streaming voice calls with WebSocket support (BETA) |
| `/media-stream` | WebSocket | WebSocket endpoint for real-time audio streaming |

---

## 🛠️ Tech Stack

| Technology | Purpose |
|-----------|---------|
| **Python** | Primary programming language |
| **Flask** | Web server for handling webhooks and serving pages |
| **Flask-Sock** | WebSocket support for streaming voice calls |
| **Gunicorn** | Production WSGI server |
| **OpenAI GPT-4o** | AI language model for generating responses |
| **Twilio** | WhatsApp messaging and voice call integration |
| **MCP (Model Context Protocol)** | Standard protocol for exposing tools to AI models |
| **FastMCP** | MCP server framework |
| **httpx** | Async HTTP client for API calls in the MCP server |
| **requests** | HTTP client for synchronous API calls in the database layer |
| **Streamlit** | Web-based chat interface |
| **psycopg2** | PostgreSQL database adapter (used by seed/test scripts) |
| **pydub** | Audio processing for voice calls |
| **python-dotenv** | Environment variable management |

---

## 🚀 Deployment

The project includes a `procfile` for deploying on Railway or Heroku:

```
web: export PYTHONPATH=$PYTHONPATH:. && gunicorn main:app
mcp: python mcpsc/main.py
```

This starts two processes:
1. **web** — The main Flask server via Gunicorn
2. **mcp** — The MCP tool server

---

## 🧰 Utility Scripts

| Script | Purpose |
|--------|---------|
| `keep_alive.py` | Pings the Turkcell backend API to prevent it from sleeping (Render free tier) |
| `monitor_db.py` | Watches the `interaction_history` database table in real-time and prints new interactions |
| `test_api.py` | Tests API integration endpoints and language detection functionality |
| `test_connection.py` | Verifies your Supabase database connection is working |
| `seed_database.py` | Populates the database with sample test data (packages, customers, subscriptions) |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m "Add your feature"`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## 📄 License

This project was built for the Turkcell AI competition.

---

## 💡 Troubleshooting

- **API requests timing out?** The backend API on Render's free tier may be sleeping. Run `python keep_alive.py` to wake it up.
- **OpenAI errors?** Verify your `OPENAI_API_KEY` is valid and has sufficient credits.
- **Twilio not receiving messages?** Make sure your Twilio webhook URLs point to your server's public URL. For WhatsApp, use `/webhook`. For voice, use `/voice/incoming` (standard) or `/voice/streaming` (streaming). You may need a tool like [ngrok](https://ngrok.com/) for local development.
- **MCP server won't start?** Ensure you have Python 3.13+ installed and have run `uv sync` inside the `mcpsc/` directory.
- **Database connection fails?** Double-check your `DATABASE_URL` in the `.env` file, and make sure your IP is allowed in Supabase (Settings → Database → Connection Pooling).
- **Voice streaming not working?** The streaming voice handler is currently a BETA placeholder. Use the standard `/voice/incoming` endpoint for reliable voice interactions.
