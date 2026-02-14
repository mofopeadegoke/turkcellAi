# 🇹🇷 Turkcell AI Agent

An AI-powered customer support system built for the **Turkcell competition**. This project provides an intelligent, multi-channel virtual assistant that helps Turkcell customers (especially tourists) with common telecom tasks — like checking their data balance, looking up account info, getting network status, and finding the right mobile package — all through **WhatsApp**, **voice calls**, or a **web chat interface**.

---

## 📖 What Does This Project Do?

Imagine you're a tourist visiting Turkey and you just bought a Turkcell SIM card. You have questions:

- *"How much data do I have left?"*
- *"Is there a network problem in my area?"*
- *"What package should I buy for my budget?"*

Instead of waiting on hold or navigating a website in an unfamiliar language, you can simply **send a WhatsApp message** or **make a phone call**, and an AI agent will understand your question, look up your account, and give you a helpful answer — in your preferred language.

### Key Features

- **📱 WhatsApp Support** — Chat with the AI agent via WhatsApp (powered by Twilio)
- **📞 Voice Call Support** — Call and speak naturally; speech is converted to text, processed by AI, and the response is spoken back to you
- **💬 Web Chat Interface** — A Streamlit-based web UI for interactive chat with the AI agent
- **🤖 AI-Powered Responses** — Uses OpenAI GPT-4o / GPT-4o-mini to generate smart, context-aware answers
- **🔧 MCP (Model Context Protocol) Server** — Exposes telecom tools (customer lookup, balance check, network status, package recommendations) as callable functions for the AI
- **💾 Database Integration** — Connects to a Supabase PostgreSQL database storing customer data, subscriptions, balances, packages, interaction history, and a knowledge base
- **🌍 Multi-language Support** — Detects the customer's language from their phone number country code and responds accordingly
- **🔁 Provider Fallback** — If one AI provider fails, the system automatically falls back to another, ensuring reliability

---

## 🏗️ Project Structure

```
turkcellAi/
├── main.py                  # Main Flask web server (WhatsApp webhooks, voice endpoints, health checks, dashboard)
├── requirements.txt         # Python dependencies for the main Flask app
├── seed_database.py         # Script to populate the database with test data (packages, customers, subscriptions)
├── test_connection.py       # Script to test your Supabase database connection
├── .gitignore               # Files and folders excluded from version control
│
├── app/                     # Core application modules
│   ├── config.py            # Loads environment variables (API keys, database URL, etc.)
│   ├── database.py          # Database helper functions (customer lookup, interaction logging, knowledge base search)
│   └── voice_handler.py     # Handles incoming voice calls, speech-to-text, AI response generation
│
├── intelligence/            # AI orchestration layer
│   ├── intelligence_client.py  # Main orchestrator — manages provider fallback, retries, and timeouts
│   ├── openai_provider.py      # OpenAI GPT provider — generates AI responses using GPT-4o-mini
│   ├── mcp_provider.py         # MCP provider — connects to the MCP server for tool-based AI responses
│   └── safe_provider.py        # Safe fallback provider — returns a friendly error message if all providers fail
│
├── mcpsc/                   # MCP (Model Context Protocol) Server
│   ├── main.py              # MCP server with tool definitions (customer lookup, balance, network status, package recommendations)
│   ├── pyproject.toml       # MCP server project configuration (uses uv package manager)
│   ├── .python-version      # Python version requirement (3.13+)
│   └── uv.lock              # Locked dependencies for the MCP server
│
├── client/                  # Client applications that connect to the MCP server
│   ├── app.py               # Streamlit web chat UI — interactive chat with AI + automatic MCP tool discovery
│   └── main.py              # Simple CLI client example — demonstrates how to connect to the MCP server programmatically
│
└── services/                # Additional service modules (reserved for future use)
```

---

## ⚙️ How It Works (Simple Explanation)

1. **A customer sends a message** (via WhatsApp, phone call, or web chat)
2. **The system identifies the customer** by looking up their phone number in the database
3. **The AI processes the message** using OpenAI GPT, with the customer's account info as context
4. **If the AI needs real data** (e.g., balance, network status), it calls tools on the **MCP server**, which fetches live data from the Turkcell API
5. **The AI sends back a personalized response** to the customer through the same channel

### The Intelligence Layer

The `IntelligenceClient` is the brain of the system. It:
- Tries the **primary AI provider** first (OpenAI or MCP)
- If it fails, **automatically retries** (up to 2 times)
- If the primary provider keeps failing, **falls back** to the next provider
- If everything fails, returns a **safe, friendly error message** so the customer is never left hanging
- Has a **7-second timeout** to keep responses fast

### The MCP Server

The MCP server exposes these tools that the AI can call:

| Tool | What It Does |
|------|-------------|
| `lookup_customer` | Find a customer by phone number or passport number |
| `get_balance_summary` | Check remaining data (GB), minutes, and SMS |
| `get_network_status_per_region` | Check if there are network issues in a specific region |
| `recommend_package` | Suggest the best mobile package based on budget or data needs |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.13+** (for the MCP server); Python 3.10+ should work for the main app
- **A Supabase account** (free tier works) — for the PostgreSQL database
- **An OpenAI API key** — for GPT-4o / GPT-4o-mini
- **A Twilio account** — for WhatsApp and voice call integration
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

# Database (Supabase PostgreSQL connection string)
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

### 6. Run the Application

**Start the main Flask server:**

```bash
python main.py
```

The server will start and you can visit `http://localhost:5000` to see the status page.

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
| `/` | GET | Home page — shows system status and available channels |
| `/health` | GET | Health check — shows database connection status and customer count |
| `/dashboard` | GET | Live call dashboard for monitoring |
| `/whatsapp` | POST | Webhook for incoming WhatsApp messages (configured in Twilio) |
| `/voice` | POST | Webhook for incoming voice calls (configured in Twilio) |
| `/voice/process` | POST | Processes speech input from voice calls |

---

## 🛠️ Tech Stack

| Technology | Purpose |
|-----------|---------|
| **Python** | Primary programming language |
| **Flask** | Web server for handling webhooks and serving pages |
| **OpenAI GPT-4o / GPT-4o-mini** | AI language model for generating responses |
| **Twilio** | WhatsApp messaging and voice call integration |
| **Supabase (PostgreSQL)** | Cloud database for customer data, subscriptions, and knowledge base |
| **MCP (Model Context Protocol)** | Standard protocol for exposing tools to AI models |
| **Streamlit** | Web-based chat interface |
| **httpx** | Async HTTP client for API calls in the MCP server |
| **psycopg2** | PostgreSQL database adapter for Python |

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

- **Database connection fails?** Double-check your `DATABASE_URL` in the `.env` file, and make sure your IP is allowed in Supabase (Settings → Database → Connection Pooling).
- **OpenAI errors?** Verify your `OPENAI_API_KEY` is valid and has sufficient credits.
- **Twilio not receiving messages?** Make sure your Twilio webhook URLs point to your server's public URL (you may need a tool like [ngrok](https://ngrok.com/) for local development).
- **MCP server won't start?** Ensure you have Python 3.13+ installed and have run `uv sync` inside the `mcpsc/` directory.
