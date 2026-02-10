from flask import request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import json
from app.config import Config
from app.database import get_customer_by_phone, log_interaction
from datetime import datetime
import uuid

# Conversation memory
conversation_memory = {}

def get_openai_client():
    """Lazy load OpenAI client"""
    from openai import OpenAI
    return OpenAI(api_key=Config.OPENAI_API_KEY)


def get_customer_info(phone_number):
    """Lookup customer from Supabase database"""
    customer = get_customer_by_phone(phone_number)
    
    if customer and customer['customer_id']:
        # Calculate days remaining
        days_remaining = 0
        if customer['expiry_date']:
            days_remaining = (customer['expiry_date'] - datetime.now()).days
            days_remaining = max(0, days_remaining)  # Don't show negative days
        
        return {
            "customer_id": str(customer['customer_id']),
            "name": customer['full_name'],
            "language": customer['preferred_language'],
            "phone": customer['whatsapp_number'] or customer['msisdn'],
            "package": {
                "type": customer['package_name'] or "No active package",
                "data": f"{customer['data_remaining_mb'] // 1024}GB" if customer['data_remaining_mb'] else "0GB",
                "days_remaining": days_remaining,
                "price_paid": f"{customer['price_try']} TRY" if customer['price_try'] else "N/A"
            } if customer['package_name'] else None
        }
    else:
        # Unknown customer
        return {
            "customer_id": None,
            "name": "Valued Customer",
            "language": "EN",
            "package": None,
            "phone": phone_number
        }


def generate_ai_response(customer_info, user_message, conversation_history):
    """Generate personalized AI response using GPT-4"""
    client = get_openai_client()
    
    # Build system prompt
    system_prompt = f"""You are a helpful Turkcell customer service AI assistant.

CUSTOMER INFORMATION:
- Name: {customer_info['name']}
- Preferred Language: {customer_info['language']}
- Phone: {customer_info['phone']}
"""
    
    if customer_info['package']:
        system_prompt += f"""- Current Package: {customer_info['package']['type']}
- Data Remaining: {customer_info['package']['data']}
- Days Remaining: {customer_info['package']['days_remaining']}
- Price Paid: {customer_info['package']['price_paid']}
"""
    
    system_prompt += """
INSTRUCTIONS:
1. Always respond in the customer's preferred language
2. Be warm, helpful, and professional
3. Keep responses SHORT for voice (2-3 sentences maximum)
4. Use simple language
5. Ask ONE question at a time
6. If complex issue, offer to escalate to human

IMPORTANT: This is a VOICE call, so keep everything concise and clear.
"""
    
    # Build messages
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})
    
    # Get AI response
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.7,
        max_tokens=150
    )
    
    return response.choices[0].message.content


def handle_incoming_call():
    """Handle incoming phone call"""
    response = VoiceResponse()
    caller = request.values.get('From', '')
    
    # Get customer info from database
    customer = get_customer_info(caller)
    
    # Initialize conversation memory with session ID
    session_id = str(uuid.uuid4())
    if caller not in conversation_memory:
        conversation_memory[caller] = {
            'session_id': session_id,
            'messages': []
        }
    
    # Personalized greeting based on language
    greetings = {
        'TR': f"Merhaba {customer['name']}! Ben Turkcell yapay zeka asistanıyım. Size nasıl yardımcı olabilirim?",
        'AR': f"مرحبا {customer['name']}! أنا مساعد الذكاء الاصطناعي من Turkcell. كيف يمكنني مساعدتك؟",
        'DE': f"Hallo {customer['name']}! Ich bin Turkcells KI-Assistent. Wie kann ich Ihnen helfen?",
        'RU': f"Здравствуйте {customer['name']}! Я ИИ-помощник Turkcell. Чем могу помочь?",
        'EN': f"Hello {customer['name']}! I'm Turkcell's AI assistant. How can I help you today?"
    }
    
    greeting = greetings.get(customer['language'], greetings['EN'])
    
    # Gather speech input
    gather = Gather(
        input='speech',
        action='/voice/process',
        language='en-US',
        speech_timeout='auto',
        timeout=10,
        hints='internet, SIM card, data, package, price, help, slow, not working'
    )
    
    gather.say(greeting, voice='Polly.Joanna')
    response.append(gather)
    
    # Fallback
    response.say("I didn't hear anything. Please call again if you need help. Goodbye!")
    
    return Response(str(response), mimetype='text/xml')


def process_speech():
    """Process speech input and generate AI response"""
    response = VoiceResponse()
    caller = request.values.get('From', '')
    speech_result = request.values.get('SpeechResult', '')
    
    print("="*60)
    print(f"🎤 Caller: {caller}")
    print(f"🗣️  Speech: '{speech_result}'")
    print(f"📊 Confidence: {request.values.get('Confidence', 'N/A')}")
    print("="*60)
    
    # Check for empty speech
    if not speech_result or speech_result.strip() == '':
        print("⚠️  Empty speech result - asking user to repeat")
        response.say("I'm sorry, I didn't catch that. Could you please repeat?", voice='Polly.Joanna')
        
        gather = Gather(
            input='speech',
            action='/voice/process',
            language='en-US',
            speech_timeout='auto',
            timeout=10
        )
        gather.say("What can I help you with?", voice='Polly.Joanna')
        response.append(gather)
        return Response(str(response), mimetype='text/xml')
    
    # Get customer info
    customer = get_customer_info(caller)
    
    # Get conversation history
    if caller not in conversation_memory:
        conversation_memory[caller] = {
            'session_id': str(uuid.uuid4()),
            'messages': []
        }
    
    # Generate AI response
    ai_response = generate_ai_response(
        customer,
        speech_result,
        conversation_memory[caller]['messages']
    )
    
    print(f"🤖 AI: {ai_response}")
    
    # Update conversation memory
    conversation_memory[caller]['messages'].append({"role": "user", "content": speech_result})
    conversation_memory[caller]['messages'].append({"role": "assistant", "content": ai_response})
    
    # Keep only last 10 exchanges
    if len(conversation_memory[caller]['messages']) > 20:
        conversation_memory[caller]['messages'] = conversation_memory[caller]['messages'][-20:]
    
    # Log to database
    if customer['customer_id']:
        log_interaction(
            customer['customer_id'],
            'VOICE',
            speech_result,
            ai_response,
            session_id=conversation_memory[caller]['session_id']
        )
    
    # Check for end keywords
    end_keywords = ['goodbye', 'bye', 'thank you', 'thanks', 'that\'s all', 
                    'hoşçakal', 'teşekkürler', 'شكرا', 'وداعا', 'danke', 'спасибо']
    
    should_end = any(keyword in speech_result.lower() for keyword in end_keywords)
    
    if should_end:
        response.say(ai_response, voice='Polly.Joanna')
        response.say("Thank you for calling Turkcell. Goodbye!", voice='Polly.Joanna')
        response.hangup()
    else:
        # Continue conversation
        gather = Gather(
            input='speech',
            action='/voice/process',
            language='en-US',
            speech_timeout='auto',
            timeout=10
        )
        
        gather.say(ai_response, voice='Polly.Joanna')
        response.append(gather)
        
        response.say("I didn't hear your response. Goodbye!", voice='Polly.Joanna')
    
    return Response(str(response), mimetype='text/xml')