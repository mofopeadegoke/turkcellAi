from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from app.config import Config
from app.voice_handler import handle_incoming_call, process_speech
import json

app = Flask(__name__)
app.config.from_object(Config)

# Load knowledge base
with open('app/knowledge_base.json', 'r', encoding='utf-8') as f:
    KNOWLEDGE_BASE = json.load(f)

def find_relevant_info(message):
    """Search knowledge base for relevant information"""
    message_lower = message.lower()
    
    for topic_key, topic_data in KNOWLEDGE_BASE.items():
        for keyword in topic_data['keywords']:
            if keyword in message_lower:
                return topic_data['content']
    
    return None

@app.route('/')
def home():
    return """
    <h1>Turkcell AI Agent is running! 🚀</h1>
    <p>📱 WhatsApp: Send message to your Twilio number</p>
    <p>📞 Voice: Call your Twilio number</p>
    """

# ===== WHATSAPP ROUTES =====
@app.route('/webhook', methods=['POST'])
def webhook():
    """Receives messages from WhatsApp"""
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    
    print(f"📨 Received from {sender}: {incoming_msg}")
    
    response = MessagingResponse()
    message = response.message()
    
    relevant_info = find_relevant_info(incoming_msg)
    
    if relevant_info:
        reply = relevant_info
    elif incoming_msg.lower() in ['hi', 'hello', 'hey', 'merhaba']:
        reply = '''Hello! 👋 I'm Turkcell AI Assistant.

I can help you with:
📱 SIM activation
🌐 Internet issues
💰 Package pricing
📍 Store locations

Just describe your problem!'''
    else:
        reply = "I'm here to help! Try asking about:\n• SIM activation\n• Internet problems\n• Prices\n• Store locations"
    
    message.body(reply)
    return str(response)


# ===== VOICE ROUTES =====
@app.route('/voice/incoming', methods=['POST'])
def voice_incoming():
    """Handle incoming phone calls"""
    return handle_incoming_call()


@app.route('/voice/process', methods=['POST'])
def voice_process():
    """Process speech from caller"""
    return process_speech()


if __name__ == '__main__':
    app.run(debug=True, port=5000)



