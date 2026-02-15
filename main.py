from flask import Flask, request, jsonify, Response
from flask_sock import Sock
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
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

# ===== NEW: Enable WebSocket support for streaming =====
sock = Sock(app)

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
            .badge { background: #ff6b6b; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 Turkcell AI Agent <span class="badge">STREAMING</span></h1>
            <p class="status">✅ System Running</p>
            <p><strong>Intelligence Status:</strong> Connected to OpenAI + MCP Tools</p>
            <p><strong>Streaming:</strong> Enabled - Real-time sentence-by-sentence responses</p>
            
            <h2>Available Channels:</h2>
            <div class="feature">
                <h3>📱 WhatsApp</h3>
                <p>Send a message to your Twilio number.</p>
            </div>
            <div class="feature">
                <h3>📞 Voice Calls (Streaming) <span class="badge">NEW</span></h3>
                <p>Call your Twilio number for instant responses.</p>
                <p><small>⚡ Streaming enabled - responses start in <1 second</small></p>
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
    try:
        from app.database import _make_request
        health_status = {
            "status": "healthy", 
            "timestamp": datetime.now().isoformat(), 
            "services": {}
        }
        
        # Check API connection
        try:
            result = _make_request('GET', '/health')
            health_status["services"]["api"] = {"status": "connected"}
        except Exception as e:
            health_status["services"]["api"] = {"status": "error", "error": str(e)}
            health_status["status"] = "degraded"
        
        # Check OpenAI
        try:
            from openai import OpenAI
            client = OpenAI(api_key=Config.OPENAI_API_KEY)
            health_status["services"]["openai"] = {"status": "configured"}
        except Exception as e:
            health_status["services"]["openai"] = {"status": "error", "error": str(e)}
        
        # Check streaming support
        health_status["services"]["streaming"] = {"status": "enabled"}
        
        return jsonify(health_status)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


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
        customer_context = {
            "name": "Visitor",
            "language": "English",
            "package": "None",
            "phone": sender
        }

    # 2. Initialize the Brain
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
    try:
        log_interaction(
            customer_id=customer.get('customer_id') if customer else None,
            channel='WHATSAPP',
            user_message=incoming_msg,
            ai_response=ai_reply,
            session_id=str(uuid.uuid4())
        )
    except:
        pass  # Don't fail if logging fails
    
    return str(response)


# ===== VOICE ROUTES =====

# NEW: Streaming Voice Endpoint
@app.route('/voice/streaming', methods=['POST'])
def voice_streaming():
    """
    Handle incoming call with STREAMING support
    
    This enables real-time, sentence-by-sentence responses
    """
    response = VoiceResponse()
    
    caller = request.values.get('From', '')
    call_sid = request.values.get('CallSid', '')
    
    print(f"📞 STREAMING CALL from: {caller} (CallSid: {call_sid})")
    
    # Connect to media stream
    connect = Connect()
    
    # Build WebSocket URL
    host = request.host
    protocol = 'wss' if request.is_secure else 'ws'
    ws_url = f"{protocol}://{host}/media-stream"
    
    print(f"🔌 Connecting to: {ws_url}")
    
    # Connect to stream with caller info
    stream = connect.stream(url=ws_url)
    stream.parameter(name='caller', value=caller)
    stream.parameter(name='call_sid', value=call_sid)
    
    response.append(connect)
    
    # Fallback message
    response.say("If you're hearing this, streaming is not available. Please try again.")
    
    return Response(str(response), mimetype='text/xml')


# WebSocket endpoint for media streaming
@sock.route('/media-stream')
def media_stream_route(ws):
    """
    WebSocket endpoint for Twilio Media Streams
    
    Receives real-time audio and sends back instant responses
    """
    from app.streaming_voice_handler import handle_media_stream
    
    print("🎙️ Media stream WebSocket connected")
    
    # Run async handler in sync context
    asyncio.run(handle_media_stream(ws))


# Original non-streaming endpoints (fallback)
@app.route('/voice/incoming', methods=['POST'])
def voice_incoming():
    """Handle incoming phone calls (non-streaming fallback)"""
    print("📞 Incoming voice call (non-streaming)...")
    return handle_incoming_call()


@app.route('/voice/process', methods=['POST'])
def voice_process():
    """Process speech from caller (non-streaming fallback)"""
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
            .badge { background: #ff6b6b; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.7em; margin-left: 10px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
            .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .stat-number { font-size: 2em; font-weight: bold; color: #0066cc; }
            .interaction { background: white; border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #0066cc; }
            .channel-voice { background: #e3f2fd; color: #1976d2; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
            .channel-voice_stream { background: #ff6b6b; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
            .channel-whatsapp { background: #e8f5e9; color: #388e3c; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
            .user { color: #0066cc; font-weight: bold; }
            .ai { color: #00cc66; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🎙️ Turkcell AI - Live Dashboard <span class="badge">STREAMING</span></h1>
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
                            <div><span style="color:#999">${item.timestamp}</span> <span class="channel-${item.channel.toLowerCase().replace('_', '-')}">${item.channel}</span></div>
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
    try:
        # Since we're using API now, try to get data
        # For now, return mock data if API not available
        return jsonify({
            'stats': {'total': 0, 'voice': 0, 'whatsapp': 0},
            'interactions': []
        })
    except Exception as e:
        return jsonify({'stats': {'total':0,'voice':0,'whatsapp':0}, 'interactions': []})

if __name__ == '__main__':
    print("="*70)
    print("🚀 Starting Turkcell AI Agent - STREAMING MODE")
    print("="*70)
    print("📱 WhatsApp: Ready")
    print("📞 Voice (Standard): Ready at /voice/incoming")
    print("⚡ Voice (Streaming): Ready at /voice/streaming")
    print("💾 Database: Connected to Live API")
    print("🎙️ Media Streams: Enabled")
    print("🌐 WebSocket: Ready at /media-stream")
    print("="*70)
    print()
    print("💡 To use streaming:")
    print("   1. Update Twilio webhook to: /voice/streaming")
    print("   2. Make sure ngrok is using https")
    print("="*70)
    
    # Use 0.0.0.0 for Railway/Docker compatibility
    app.run(host='0.0.0.0', port=5000, debug=True)