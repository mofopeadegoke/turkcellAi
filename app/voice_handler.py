from flask import request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import json
from app.config import Config
from app.database import get_customer_by_phone, log_interaction
from datetime import datetime
import uuid
from openai import OpenAI
import asyncio
from app.intelligence.intelligence_client import IntelligenceClient

#global client
ai_client = IntelligenceClient(
    openai_api_key=Config.OPENAI_API_KEY,
    mcp_server_path=Config.MCP_SERVER_PATH,
    primary="openai",
)

# Conversation memory
conversation_memory = {}
# def get_openai_client():
#     # """Lazy load OpenAI client"""
#     # from openai import OpenAI
#     # return OpenAI(api_key=Config.OPENAI_API_KEY)
#     """Lazy load OpenAI client to avoid initialization errors"""
#     import openai
#     import os
    
#     # For Python 3.14 compatibility - use environment variable instead
#     os.environ['OPENAI_API_KEY'] = Config.OPENAI_API_KEY
    
#     # Simple initialization without extra parameters
#     return openai.OpenAI()

def get_openai_client():
    return OpenAI(api_key=Config.OPENAI_API_KEY)


def get_customer_info(phone_number):
    """Lookup customer from Supabase database"""
    print(f"🔍 Looking up phone: {phone_number}")
    
    customer = get_customer_by_phone(phone_number)
    
    if customer and customer['customer_id']:
        # Calculate days remaining
        days_remaining = 0
        if customer['expiry_date']:
            days_remaining = (customer['expiry_date'] - datetime.now()).days
            days_remaining = max(0, days_remaining)
        
        print(f"✅ Customer found in database: {customer['full_name']}")
        
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
        # Unknown customer - create a friendly default response
        print(f"⚠️  Customer not found in database - using default")
        
        # Try to detect language from phone number country code
        language = 'EN'  # Default to English
        if phone_number.startswith('+90'):
            language = 'TR'  # Turkish number
        elif phone_number.startswith('+49'):
            language = 'DE'  # German
        elif phone_number.startswith('+7'):
            language = 'RU'  # Russian
        elif phone_number.startswith('+966') or phone_number.startswith('+971'):
            language = 'AR'  # Arabic (Saudi/UAE)
        
        print(f"   Detected language from country code: {language}")
        
        return {
            "customer_id": None,
            "name": "Valued Customer",
            "language": language,
            "package": None,
            "phone": phone_number,
            "is_new_customer": True  # Flag for different greeting
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
    response = client.responses.create(
    model="gpt-4.1-mini",   # cheaper + fast + good for voice agents
    input=messages,
    temperature=0.7,
    max_output_tokens=150
    )

    return response.output_text

def handle_incoming_call():
    """Handle incoming phone call"""
    try:
        response = VoiceResponse()
        caller = request.values.get('From', '')
        
        print("="*60)
        print(f"📞 INCOMING CALL")
        print(f"   From: {caller}")
        print(f"   CallSid: {request.values.get('CallSid', 'N/A')}")
        print("="*60)
        
        # Get customer info from database
        customer = get_customer_info(caller)
        
        # Initialize conversation memory with session ID
        session_id = str(uuid.uuid4())
        if caller not in conversation_memory:
            conversation_memory[caller] = {
                'session_id': session_id,
                'messages': []
            }
        
        # Different greetings for existing vs new customers
        if customer.get('is_new_customer'):
            # New customer - generic greeting
            greetings = {
                'TR': "Merhaba! Turkcell yapay zeka asistanına hoş geldiniz. Size nasıl yardımcı olabilirim?",
                'AR': "مرحبا! مرحبا بك في مساعد Turkcell الذكي. كيف يمكنني مساعدتك؟",
                'DE': "Hallo! Willkommen beim Turkcell KI-Assistenten. Wie kann ich Ihnen helfen?",
                'RU': "Здравствуйте! Добро пожаловать в ИИ-помощник Turkcell. Чем могу помочь?",
                'EN': "Hello! Welcome to Turkcell's AI assistant. How can I help you today?"
            }
        else:
            # Existing customer - personalized greeting
            greetings = {
                'TR': f"Merhaba {customer['name']}! Ben Turkcell yapay zeka asistanıyım. Size nasıl yardımcı olabilirim?",
                'AR': f"مرحبا {customer['name']}! أنا مساعد الذكاء الاصطناعي من Turkcell. كيف يمكنني مساعدتك؟",
                'DE': f"Hallo {customer['name']}! Ich bin Turkcells KI-Assistent. Wie kann ich Ihnen helfen?",
                'RU': f"Здравствуйте {customer['name']}! Я ИИ-помощник Turkcell. Чем могу помочь?",
                'EN': f"Hello {customer['name']}! I'm Turkcell's AI assistant. How can I help you today?"
            }
        
        greeting = greetings.get(customer['language'], greetings['EN'])
        print(f"💬 Greeting ({customer['language']}): {greeting}")
        
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
        
        print("✅ Response generated successfully")
        return Response(str(response), mimetype='text/xml')
        
    except Exception as e:
        print("="*60)
        print(f"❌ ERROR IN handle_incoming_call:")
        print(f"   {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        
        # Return a safe error message to caller
        response = VoiceResponse()
        response.say("We're sorry, but we're experiencing technical difficulties. Please try again later.", voice='Polly.Joanna')
        return Response(str(response), mimetype='text/xml')

# def simple_ai_reply(user_text):
#     client = get_openai_client()

#     response = client.chat.completions.create(
#         model="gpt-4",
#         messages=[
#             {"role": "system", "content": "You are a helpful Turkcell voice assistant. Keep answers under 2 sentences."},
#             {"role": "user", "content": user_text}
#         ],
#         max_tokens=80
#     )

#     return response.choices[0].message.content

# def handle_incoming_call():
#     response = VoiceResponse()
#     caller = request.values.get('From', '')

#     customer = get_customer_info(caller)

#     if customer.get("is_new_customer"):
#         greeting = "Hello. Welcome to Turkcell AI assistant. How can I help you today?"
#     else:
#         greeting = f"Hello {customer['name']}. How can I help you today?"

#     gather = Gather(
#         input='speech',
#         action='/voice/process',
#         speech_timeout='auto'
#     )

#     gather.say(greeting)
#     response.append(gather)

#     return Response(str(response), mimetype='text/xml')


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
    
    # # Generate AI response
    # ai_response = generate_ai_response(
    #     customer,
    #     speech_result,
    #     conversation_memory[caller]['messages']
    # )
    
    # print(f"🤖 AI: {ai_response}")

    messages = conversation_memory[caller]["messages"]
    messages.append({"role": "user", "content": speech_result})

    ai_response = asyncio.run(
        ai_client.ask(
            messages,
            customer_context=customer
        )
    )
    
    # Update conversation memory
    conversation_memory[caller]['messages'].append({"role": "user", "content": speech_result})
    conversation_memory[caller]['messages'].append({"role": "assistant", "content": ai_response})
    
    # Keep only last 10 exchanges
    if len(conversation_memory[caller]['messages']) > 20:
        conversation_memory[caller]['messages'] = conversation_memory[caller]['messages'][-20:]
    
    # # Log to database
    # if customer['customer_id']:
    #     log_interaction(
    #         customer['customer_id'],
    #         'VOICE',
    #         speech_result,
    #         ai_response,
    #         session_id=conversation_memory[caller]['session_id']
    #     )

    # In process_speech(), update the logging section:

    # Log to database (only if existing customer)
    if customer.get('customer_id'):
        print(f"💾 Logging to database...")
        try:
            log_interaction(
                customer['customer_id'],
                'VOICE',
                speech_result,
                ai_response,
                session_id=conversation_memory[caller]['session_id']
            )
            print(f"✅ Logged successfully")
        except Exception as e:
            print(f"⚠️  Failed to log: {e}")
    else:
        print(f"ℹ️  New customer - skipping database log")
    
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

