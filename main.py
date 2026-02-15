import asyncio
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, Response
from flask_sock import Sock
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Connect

# --- IMPORTS FROM YOUR MODULES ---
from app.config import Config
from app.database import (
    get_customer_by_phone, 
    log_interaction
)
# Import the Standard Voice functions we just built
from app.voice_handler import handle_incoming_call, process_speech 
from intelligence.intelligence_client import IntelligenceClient

app = Flask(__name__)
app.config.from_object(Config)

# Initialize WebSocket for Streaming
sock = Sock(app)

# ==========================================
# 🏠 HOME & HEALTH
# ==========================================

@app.route('/')
def home():
    return """
    <html>
    <head>
        <title>Turkcell AI Agent</title>
        <style>
            body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; background: #f0f2f5; }
            .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            h1 { color: #004481; margin-bottom: 5px; }
            .status { color: #28a745; font-weight: bold; }
            .endpoint { background: #e9ecef; padding: 10px; border-radius: 6px; font-family: monospace; margin: 5px 0; }
            .badge { background: #ff4757; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 Turkcell AI Agent</h1>
            <p class="status">● System Operational</p>
            <hr>
            <h3>🔗 Webhook Endpoints</h3>
            
            <p><strong>📱 WhatsApp:</strong></p>
            <div class="endpoint">POST /webhook</div>
            
            <p><strong>📞 Voice (Standard - Recommended):</strong></p>
            <div class="endpoint">POST /voice/incoming</div>
            
            <p><strong>⚡ Voice (Streaming - Advanced):</strong> <span class="badge">BETA</span></p>
            <div class="endpoint">POST /voice/streaming</div>
            
            <p><strong>Health Check:</strong> <a href="/health">/health</a></p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "services": {
            "openai": "enabled",
            "mcp_tools": "enabled",
            "database": "connected"
        }
    })

# ==========================================
# 📱 WHATSAPP ROUTE (Intelligent)
# ==========================================

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages with Context Injection"""
    # 1. Get Data
    incoming_msg = request.values.get('Body', '').strip()
    raw_sender = request.values.get('From', '')
    
    # 2. Clean Phone Number (Remove 'whatsapp:' prefix)
    clean_phone = raw_sender.replace('whatsapp:', '').strip()
    
    print(f"\n📨 WHATSAPP from {clean_phone}: {incoming_msg}")
    
    response = MessagingResponse()
    message = response.message()
    
    # 3. Customer Lookup (The "Magic Handoff")
    customer = get_customer_by_phone(clean_phone)
    
    # Build Context
    customer_context = {}
    if customer:
        print(f"   ✅ Identified: {customer.get('full_name')}")
        customer_context = {
            "name": customer.get('full_name'),
            "phone": clean_phone, # Critical for Tools
            "language": customer.get('preferred_language', 'EN'),
            "package": customer.get('package_name'),
            "balance": customer.get('balance_try')
        }
    else:
        print("   ⚠️ New User")
        customer_context = {
            "name": "Visitor",
            "phone": clean_phone,
            "is_new_user": True
        }

    # 4. Generate AI Response
    brain = IntelligenceClient(
        openai_api_key=Config.OPENAI_API_KEY,
        mcp_server_path=Config.MCP_SERVER_PATH
    )

    try:
        # Run async AI in sync Flask
        ai_reply = asyncio.run(
            brain.process_user_message(incoming_msg, customer_context)
        )
    except Exception as e:
        print(f"❌ AI Error: {e}")
        ai_reply = "I'm having trouble connecting to the network. Please try again."

    message.body(ai_reply)
    return str(response)

# ==========================================
# 📞 STANDARD VOICE ROUTES (Reliable)
# ==========================================
# These use the app/voice_handler.py logic we just built.

@app.route('/voice/incoming', methods=['POST'])
def voice_incoming():
    """Entry point for Standard Voice Calls"""
    # This calls the function from app/voice_handler.py
    return handle_incoming_call()

@app.route('/voice/process', methods=['POST'])
def voice_process():
    """Handles user speech input"""
    # This calls the function from app/voice_handler.py
    return process_speech()

# ==========================================
# ⚡ STREAMING VOICE ROUTES (Advanced)
# ==========================================

@app.route('/voice/streaming', methods=['POST'])
def voice_streaming():
    """
    Handle incoming call with STREAMING support.
    Injects Customer Identity into the WebSocket parameters.
    """
    response = VoiceResponse()
    
    # 1. Clean Data
    raw_from = request.values.get('From', '')
    call_sid = request.values.get('CallSid', '')
    caller_phone = raw_from.replace('client:', '').strip()
    
    print(f"\n📞 STREAMING CALL from: {caller_phone}")
    
    # 2. Lookup Customer
    customer = get_customer_by_phone(caller_phone)
    
    customer_name = "Visitor"
    package_name = "None"
    
    if customer:
        customer_name = customer.get('full_name', 'Visitor')
        package_name = customer.get('package_name', 'None')
        print(f"   ✅ Identified: {customer_name}")
    
    # 3. Connect to Media Stream
    connect = Connect()
    
    # Build WebSocket URL
    host = request.host
    protocol = 'wss' if request.is_secure else 'ws'
    ws_url = f"{protocol}://{host}/media-stream"
    
    print(f"   🔌 WebSocket: {ws_url}")
    
    # 4. Pass Context to WebSocket
    stream = connect.stream(url=ws_url)
    stream.parameter(name='phone', value=caller_phone)
    stream.parameter(name='name', value=customer_name)
    stream.parameter(name='package', value=package_name)
    stream.parameter(name='call_sid', value=call_sid)
    
    response.append(connect)
    
    # Fallback if stream fails
    response.say("Streaming unavailable. Switching to standard mode.")
    response.redirect('/voice/incoming')
    
    return Response(str(response), mimetype='text/xml')

@sock.route('/media-stream')
def media_stream_route(ws):
    """WebSocket endpoint for Audio Streaming"""
    # Lazy import to avoid circular dependencies if file missing
    try:
        from app.streaming_voice_handler import handle_media_stream
        print("🎙️ Stream Connected")
        asyncio.run(handle_media_stream(ws))
    except ImportError:
        print("❌ app/streaming_voice_handler.py is missing!")
        ws.close()

# ==========================================
# 🚀 RUNNER
# ==========================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 TURKCELL AI AGENT - STARTED")
    print("="*60)
    print("📡 Server running on http://0.0.0.0:5000")
    print("🔧 Configure your Twilio Webhook to:")
    print("   - Standard: https://<your-ngrok>/voice/incoming")
    print("   - Streaming: https://<your-ngrok>/voice/streaming")
    print("="*60 + "\n")
    
    # Threaded=True is important for handling multiple calls
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)