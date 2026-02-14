from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from app.config import Config
from app.voice_handler import handle_incoming_call, process_speech
from app.database import (
    get_customer_by_phone, 
    log_interaction
)
from intelligence.intelligence_client import IntelligenceClient
from datetime import datetime
import uuid
import asyncio

app = Flask(__name__)
app.config.from_object(Config)

@app.route('/')
def home():
    return """
    <html>
    <head>
        <title>Turkcell AI Agent</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; background: #f5f5f5; }
            .card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #0066cc; }
            .status { color: #00cc66; font-size: 1.2em; }
            .feature { margin: 15px 0; padding: 10px; background: #f9f9f9; border-left: 4px solid #0066cc; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 Turkcell AI Agent</h1>
            <p class="status">✅ System Running</p>
            <p><strong>Intelligence Status:</strong> Connected to OpenAI + MCP Tools</p>
            
            <h2>Available Channels:</h2>
            <div class="feature"><h3>📱 WhatsApp</h3><p>Send a message to your Twilio number.</p></div>
            <div class="feature"><h3>📞 Voice Calls</h3><p>Call your Twilio number.</p></div>
            
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
    health_status = {"status": "healthy", "timestamp": datetime.now().isoformat(), "services": {}}
    
    # Check database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM customers;")
        health_status["services"]["database"] = {"status": "connected", "customers": cursor.fetchone()['count']}
        cursor.close()
        conn.close()
    except Exception as e:
        health_status["services"]["database"] = {"status": "error", "error": str(e)}
        health_status["status"] = "degraded"
    
    return jsonify(health_status)


# ===== WHATSAPP ROUTES (NOW INTELLIGENT) =====

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages SMARTLY using IntelligenceClient"""
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    
    print("="*60)
    print(f"📨 WhatsApp Message Received from {sender}: {incoming_msg}")
    
    response = MessagingResponse()
    message = response.message()
    
    # 1. Get Customer Context (Who is this?)
    customer = get_customer_by_phone(sender)
    
    customer_context = {}
    if customer:
        print(f"✅ Customer Identified: {customer.get('full_name')}")
        customer_context = {
            "name": customer.get('full_name'),
            "language": customer.get('preferred_language', 'English'),
            "package": customer.get('package_name'),
            "phone": sender,
            "balance": customer.get('balance_try')
        }
    else:
        print("⚠️ New/Unknown Customer")
        # Provide minimal context for new users
        customer_context = {
            "name": "Visitor",
            "language": "English",
            "package": "None",
            "phone": sender
        }

    # 2. Initialize the Brain
    # We create a new client for each request to ensure fresh state
    brain = IntelligenceClient(
        openai_api_key=Config.OPENAI_API_KEY,
        mcp_server_path=Config.MCP_SERVER_PATH
    )

    # 3. Ask the AI (Run Async in Sync Flask)
    try:
        print("🧠 Sending to Intelligence Layer...")
        ai_reply = asyncio.run(
            brain.process_user_message(incoming_msg, customer_context)
        )
        print("✅ AI Response Generated")
    except Exception as e:
        print(f"❌ AI Error: {e}")
        ai_reply = "I'm having trouble connecting to the network right now. Please try again in a moment."

    # 4. Send the Smart Response
    message.body(ai_reply)
    
    # 5. Log it
    log_interaction(
        customer_id=customer.get('customer_id') if customer else None,
        channel='WHATSAPP',
        user_message=incoming_msg,
        ai_response=ai_reply,
        session_id=str(uuid.uuid4())
    )
    
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

@app.route('/dashboard')
def dashboard():
    """Live dashboard showing recent interactions"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Turkcell AI - Live Dashboard</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f7fa; }
            h1 { color: #0066cc; border-bottom: 3px solid #0066cc; padding-bottom: 10px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
            .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .stat-number { font-size: 2em; font-weight: bold; color: #0066cc; }
            .interaction { background: white; border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #0066cc; }
            .channel-voice { background: #e3f2fd; color: #1976d2; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
            .channel-whatsapp { background: #e8f5e9; color: #388e3c; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
            .user { color: #0066cc; font-weight: bold; }
            .ai { color: #00cc66; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🎙️ Turkcell AI - Live Dashboard</h1>
        <div class="stats" id="stats">
            <div class="stat-card"><div class="stat-number" id="total-interactions">-</div><div class="stat-label">Total Interactions</div></div>
            <div class="stat-card"><div class="stat-number" id="voice-calls">-</div><div class="stat-label">Voice Calls</div></div>
            <div class="stat-card"><div class="stat-number" id="whatsapp-messages">-</div><div class="stat-label">WhatsApp Messages</div></div>
        </div>
        <h2>Recent Interactions</h2>
        <div id="interactions">Loading...</div>

        <script>
            async function fetchData() {
                try {
                    const response = await fetch('/dashboard/data');
                    const data = await response.json();
                    
                    document.getElementById('total-interactions').textContent = data.stats.total;
                    document.getElementById('voice-calls').textContent = data.stats.voice;
                    document.getElementById('whatsapp-messages').textContent = data.stats.whatsapp;
                    
                    const container = document.getElementById('interactions');
                    container.innerHTML = data.interactions.map(item => `
                        <div class="interaction">
                            <div><span style="color:#999">${item.timestamp}</span> <span class="channel-${item.channel.toLowerCase()}">${item.channel}</span></div>
                            <div style="margin-top:10px">
                                <div><span class="user">Customer (${item.customer}):</span> ${item.user_message}</div>
                                <div style="margin-top:5px"><span class="ai">AI:</span> ${item.ai_response}</div>
                            </div>
                        </div>
                    `).join('');
                } catch (error) { console.error('Error:', error); }
            }
            fetchData();
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
        
        # Get recent interactions
        cursor.execute("""
            SELECT ih.timestamp, ih.channel, ih.user_message, ih.ai_response, c.full_name
            FROM interaction_history ih
            LEFT JOIN customers c ON ih.customer_id = c.customer_id
            ORDER BY ih.timestamp DESC LIMIT 15
        """)
        interactions = cursor.fetchall()
        
        # Get stats
        cursor.execute("SELECT COUNT(*) as count FROM interaction_history")
        total = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM interaction_history WHERE channel = 'VOICE'")
        voice = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM interaction_history WHERE channel = 'WHATSAPP'")
        whatsapp = cursor.fetchone()['count']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'stats': {'total': total, 'voice': voice, 'whatsapp': whatsapp},
            'interactions': [{
                'timestamp': item['timestamp'].strftime('%H:%M:%S'),
                'channel': item['channel'],
                'user_message': item['user_message'] or '',
                'ai_response': item['ai_response'] or '',
                'customer': item['full_name'] or 'Guest'
            } for item in interactions]
        })
    except Exception as e:
        return jsonify({'stats': {'total':0,'voice':0,'whatsapp':0}, 'interactions': []})

if __name__ == '__main__':
    # Use 0.0.0.0 for Railway/Docker compatibility
    app.run(host='0.0.0.0', port=5000)