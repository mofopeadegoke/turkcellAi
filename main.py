from flask import Flask, request, render_template, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from app.config import Config
from app.voice_handler import handle_incoming_call, process_speech
from app.database import (
    get_customer_by_phone, 
    log_interaction, 
    search_knowledge_base,
    check_network_issues
)
from datetime import datetime
import uuid

app = Flask(__name__)
app.config.from_object(Config)

# Session management for WhatsApp conversations
whatsapp_sessions = {}

@app.route('/')
def home():
    return """
    <html>
    <head>
        <title>Turkcell AI Agent</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .card {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { color: #0066cc; }
            .status { color: #00cc66; font-size: 1.2em; }
            .feature {
                margin: 15px 0;
                padding: 10px;
                background: #f9f9f9;
                border-left: 4px solid #0066cc;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 Turkcell AI Agent</h1>
            <p class="status">✅ System Running</p>
            
            <h2>Available Channels:</h2>
            
            <div class="feature">
                <h3>📱 WhatsApp</h3>
                <p>Send a message to your Twilio WhatsApp number</p>
                <p><strong>Features:</strong> Text chat, AI responses, customer lookup</p>
            </div>
            
            <div class="feature">
                <h3>📞 Voice Calls</h3>
                <p>Call your Twilio phone number</p>
                <p><strong>Features:</strong> Speech-to-text, AI conversation, personalized support</p>
            </div>
            
            <div class="feature">
                <h3>💾 Database</h3>
                <p>Connected to Supabase PostgreSQL</p>
                <p><strong>Features:</strong> Customer data, interaction history, knowledge base</p>
            </div>
            
            <h2>Quick Links:</h2>
            <ul>
                <li><a href="/dashboard">Live Call Dashboard</a></li>
                <li><a href="/health">System Health Check</a></li>
            </ul>
        </div>
    </body>
    </html>
    """


@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    from app.database import get_db_connection
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {}
    }
    
    # Check database connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM customers;")
        customer_count = cursor.fetchone()['count']
        cursor.close()
        conn.close()
        
        health_status["services"]["database"] = {
            "status": "connected",
            "customers": customer_count
        }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check OpenAI
    try:
        from app.voice_handler import get_openai_client
        client = get_openai_client()
        health_status["services"]["openai"] = {"status": "configured"}
    except Exception as e:
        health_status["services"]["openai"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check Twilio
    if Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN:
        health_status["services"]["twilio"] = {"status": "configured"}
    else:
        health_status["services"]["twilio"] = {"status": "not_configured"}
    
    return jsonify(health_status)


# ===== WHATSAPP ROUTES =====

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages"""
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    
    print("="*60)
    print(f"📨 WhatsApp Message Received")
    print(f"   From: {sender}")
    print(f"   Message: {incoming_msg}")
    print("="*60)
    
    response = MessagingResponse()
    message = response.message()
    
    # Get or create session for this user
    if sender not in whatsapp_sessions:
        whatsapp_sessions[sender] = {
            'session_id': str(uuid.uuid4()),
            'started_at': datetime.now(),
            'message_count': 0
        }
    
    whatsapp_sessions[sender]['message_count'] += 1
    session_id = whatsapp_sessions[sender]['session_id']
    
    # Get customer info from database
    customer = get_customer_by_phone(sender)
    
    if customer and customer['customer_id']:
        # Existing customer - personalized response
        customer_id = customer['customer_id']
        customer_name = customer['full_name']
        preferred_lang = customer['preferred_language']
        
        print(f"✅ Customer found: {customer_name} (Language: {preferred_lang})")
        
        # Check for greeting
        greetings = ['hi', 'hello', 'hey', 'merhaba', 'hola', 'salut', 'привет']
        if incoming_msg.lower() in greetings:
            if whatsapp_sessions[sender]['message_count'] == 1:
                # First message - welcome
                reply = f"Hello {customer_name}! 👋 Welcome back to Turkcell!\n\n"
                
                if customer['package_name']:
                    days_remaining = (customer['expiry_date'] - datetime.now()).days if customer['expiry_date'] else 0
                    data_remaining_gb = customer['data_remaining_mb'] // 1024 if customer['data_remaining_mb'] else 0
                    
                    reply += f"📦 Your Package: {customer['package_name']}\n"
                    reply += f"📊 Data Remaining: {data_remaining_gb}GB\n"
                    reply += f"📅 Days Left: {days_remaining}\n\n"
                
                reply += "How can I help you today?\n"
                reply += "• Check balance\n"
                reply += "• Internet issues\n"
                reply += "• SIM activation\n"
                reply += "• Package info"
            else:
                reply = f"Hi {customer_name}! What else can I help you with?"
        
        # Check for specific queries
        elif any(word in incoming_msg.lower() for word in ['balance', 'data', 'how much', 'remaining', 'left']):
            if customer['package_name']:
                data_remaining_gb = customer['data_remaining_mb'] // 1024 if customer['data_remaining_mb'] else 0
                days_remaining = (customer['expiry_date'] - datetime.now()).days if customer['expiry_date'] else 0
                
                reply = f"📊 Your Current Balance:\n\n"
                reply += f"📦 Package: {customer['package_name']}\n"
                reply += f"📱 Data: {data_remaining_gb}GB remaining\n"
                reply += f"📞 Voice: {customer['voice_remaining_min']} minutes\n"
                reply += f"📅 Valid for: {days_remaining} more days\n"
                reply += f"💰 Balance: {customer['balance_try']} TRY"
            else:
                reply = "You don't have an active package. Would you like to see available packages?"
        
        # Search knowledge base for other queries
        else:
            kb_results = search_knowledge_base(incoming_msg, preferred_lang, limit=1)
            
            if kb_results:
                reply = f"💡 {kb_results[0]['title']}\n\n{kb_results[0]['content']}"
            else:
                # Check for network issues in their area
                if customer.get('last_location_city'):
                    network_issues = check_network_issues(customer['last_location_city'])
                    if network_issues:
                        issue = network_issues[0]
                        reply = f"⚠️ Network Update:\n\n"
                        reply += f"We're aware of {issue['issue_type']} in {issue['region']}.\n"
                        reply += f"Severity: {issue['severity']}\n"
                        reply += f"Status: {issue['status']}\n\n"
                        reply += "How else can I help you?"
                    else:
                        reply = "I'm here to help! You can ask me about:\n"
                        reply += "• Your data balance\n"
                        reply += "• Internet troubleshooting\n"
                        reply += "• SIM activation\n"
                        reply += "• Package information\n"
                        reply += "• Store locations"
                else:
                    reply = "I'm here to help! What would you like to know about your Turkcell service?"
        
        # Log interaction to database
        log_interaction(
            customer_id=customer_id,
            channel='WHATSAPP',
            user_message=incoming_msg,
            ai_response=reply,
            session_id=session_id
        )
    
    else:
        # New/unknown customer
        print("⚠️  Customer not found in database")
        
        if incoming_msg.lower() in ['hi', 'hello', 'hey', 'merhaba']:
            reply = """Hello! 👋 Welcome to Turkcell!

I'm your AI assistant. I can help you with:

📱 SIM card activation
🌐 Internet troubleshooting
💰 Package information
📍 Store locations
💳 Tourist packages

What would you like help with today?"""
        
        elif 'tourist' in incoming_msg.lower() or 'package' in incoming_msg.lower() or 'price' in incoming_msg.lower():
            reply = """🎯 Turkcell Tourist Packages:

📦 Tourist Welcome 50GB
   • 50GB Data (30 days)
   • Unlimited local calls
   • 400 TRY

📦 Tourist Starter 30GB
   • 30GB Data (30 days)
   • 500 minutes
   • 300 TRY

⚠️ SCAM WARNING:
Official price is 300-400 TRY only!
If charged more, you may have been scammed.

Would you like help finding an official store?"""
        
        elif any(word in incoming_msg.lower() for word in ['internet', 'data', 'slow', 'not working', 'connection']):
            kb_results = search_knowledge_base(incoming_msg, 'EN', limit=1)
            if kb_results:
                reply = f"💡 {kb_results[0]['title']}\n\n{kb_results[0]['content']}"
            else:
                reply = """🌐 Internet Troubleshooting:

Quick checks:
1️⃣ Mobile Data is ON
2️⃣ Airplane mode is OFF
3️⃣ You see "Turkcell" network
4️⃣ You see 4G/5G symbol

📱 iPhone: Settings → Cellular → Mobile Data (ON)
📱 Android: Settings → Network → Mobile Data (ON)

Still not working? Try:
✈️ Airplane mode ON → wait 10 sec → OFF

Need more help?"""
        
        elif 'sim' in incoming_msg.lower() or 'activation' in incoming_msg.lower():
            kb_results = search_knowledge_base('sim activation', 'EN', limit=1)
            if kb_results:
                reply = f"💡 {kb_results[0]['title']}\n\n{kb_results[0]['content']}"
            else:
                reply = """📱 SIM Card Activation:

Steps:
1️⃣ Insert SIM into your phone
2️⃣ Restart your device
3️⃣ Wait 5-10 minutes
4️⃣ Check for "Turkcell" at top

If not activated after 10 min:
- Make sure SIM is inserted correctly
- Check if SIM tray is clean
- Try in another phone to test SIM

Need more help?"""
        
        else:
            reply = """I can help you with:

📱 SIM activation
🌐 Internet issues
💰 Package pricing
📍 Store locations

Just describe your problem and I'll assist you!"""
        
        # Log for unknown customer (no customer_id)
        try:
            log_interaction(
                customer_id=None,
                channel='WHATSAPP',
                user_message=incoming_msg,
                ai_response=reply,
                session_id=session_id
            )
        except:
            print("⚠️  Could not log interaction (no customer_id)")
    
    message.body(reply)
    return str(response)


# ===== VOICE ROUTES =====

@app.route('/voice/incoming', methods=['POST'])
def voice_incoming():
    """Handle incoming phone calls"""
    print("📞 Incoming voice call...")
    return handle_incoming_call()


@app.route('/voice/process', methods=['POST'])
def voice_process():
    """Process speech from caller"""
    return process_speech()


# ===== DASHBOARD ROUTES =====

call_logs = []  # In-memory storage for dashboard (temporary)

@app.route('/dashboard')
def dashboard():
    """Live dashboard showing recent interactions"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Turkcell AI - Live Dashboard</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f7fa;
            }
            h1 {
                color: #0066cc;
                border-bottom: 3px solid #0066cc;
                padding-bottom: 10px;
            }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 20px 0;
            }
            .stat-card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .stat-number {
                font-size: 2em;
                font-weight: bold;
                color: #0066cc;
            }
            .stat-label {
                color: #666;
                margin-top: 5px;
            }
            .interaction {
                background: white;
                border: 1px solid #ddd;
                padding: 15px;
                margin: 10px 0;
                border-radius: 8px;
                border-left: 4px solid #0066cc;
            }
            .timestamp {
                color: #999;
                font-size: 0.9em;
            }
            .channel {
                display: inline-block;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 0.8em;
                font-weight: bold;
                margin-left: 10px;
            }
            .channel-voice { background: #e3f2fd; color: #1976d2; }
            .channel-whatsapp { background: #e8f5e9; color: #388e3c; }
            .user { color: #0066cc; font-weight: bold; }
            .ai { color: #00cc66; font-weight: bold; }
            .message-content {
                margin: 10px 0;
                padding: 10px;
                background: #f9f9f9;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <h1>🎙️ Turkcell AI - Live Dashboard</h1>
        
        <div class="stats" id="stats">
            <div class="stat-card">
                <div class="stat-number" id="total-interactions">0</div>
                <div class="stat-label">Total Interactions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="voice-calls">0</div>
                <div class="stat-label">Voice Calls</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="whatsapp-messages">0</div>
                <div class="stat-label">WhatsApp Messages</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="active-customers">0</div>
                <div class="stat-label">Active Customers</div>
            </div>
        </div>
        
        <h2>Recent Interactions</h2>
        <div id="interactions"></div>

        <script>
            async function fetchData() {
                try {
                    const response = await fetch('/dashboard/data');
                    const data = await response.json();
                    
                    // Update stats
                    document.getElementById('total-interactions').textContent = data.stats.total;
                    document.getElementById('voice-calls').textContent = data.stats.voice;
                    document.getElementById('whatsapp-messages').textContent = data.stats.whatsapp;
                    document.getElementById('active-customers').textContent = data.stats.customers;
                    
                    // Update interactions
                    const container = document.getElementById('interactions');
                    container.innerHTML = data.interactions.map(item => `
                        <div class="interaction">
                            <div>
                                <span class="timestamp">${item.timestamp}</span>
                                <span class="channel channel-${item.channel.toLowerCase()}">${item.channel}</span>
                            </div>
                            <div class="message-content">
                                <div><span class="user">Customer:</span> ${item.user_message}</div>
                                <div><span class="ai">AI:</span> ${item.ai_response}</div>
                            </div>
                        </div>
                    `).join('');
                } catch (error) {
                    console.error('Error fetching data:', error);
                }
            }
            
            // Fetch data every 3 seconds
            fetchData();
            setInterval(fetchData, 3000);
        </script>
    </body>
    </html>
    """


@app.route('/dashboard/data')
def dashboard_data():
    """Provide data for dashboard"""
    from app.database import get_db_connection
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get recent interactions (last 20)
        cursor.execute("""
            SELECT 
                ih.timestamp,
                ih.channel,
                ih.user_message,
                ih.ai_response,
                c.full_name
            FROM interaction_history ih
            LEFT JOIN customers c ON ih.customer_id = c.customer_id
            ORDER BY ih.timestamp DESC
            LIMIT 20
        """)
        
        interactions = cursor.fetchall()
        
        # Get stats
        cursor.execute("SELECT COUNT(*) as count FROM interaction_history")
        total = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM interaction_history WHERE channel = 'VOICE'")
        voice = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM interaction_history WHERE channel = 'WHATSAPP'")
        whatsapp = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM customers")
        customers = cursor.fetchone()['count']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'stats': {
                'total': total,
                'voice': voice,
                'whatsapp': whatsapp,
                'customers': customers
            },
            'interactions': [
                {
                    'timestamp': item['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'channel': item['channel'],
                    'user_message': item['user_message'] or 'N/A',
                    'ai_response': (item['ai_response'][:100] + '...') if item['ai_response'] and len(item['ai_response']) > 100 else (item['ai_response'] or 'N/A'),
                    'customer': item['full_name'] or 'Unknown'
                }
                for item in interactions
            ]
        })
    
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
        return jsonify({
            'stats': {'total': 0, 'voice': 0, 'whatsapp': 0, 'customers': 0},
            'interactions': []
        })


if __name__ == '__main__':
    print("="*60)
    print("🚀 Starting Turkcell AI Agent")
    print("="*60)
    print("📱 WhatsApp: Ready")
    print("📞 Voice: Ready")
    print("💾 Database: Connected to Supabase")
    print("🌐 Dashboard: http://localhost:5000/dashboard")
    print("="*60)
    
    app.run(debug=True, port=5000)