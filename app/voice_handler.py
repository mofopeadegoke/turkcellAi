from flask import request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import json
from app.config import Config
from app.database import (
    get_customer_by_phone,
    log_interaction
)
from datetime import datetime
import uuid
import asyncio
import time
import traceback
from intelligence.intelligence_client import IntelligenceClient

# Initialize Intelligence Client
# (Ensure primary="openai" or "mcp" matches your setup)
ai_client = IntelligenceClient(
    openai_api_key=Config.OPENAI_API_KEY,
    mcp_server_path=Config.MCP_SERVER_PATH,
    primary="openai", 
)

# In-memory session storage for the hackathon (Use Redis for production)
conversation_memory = {}

def get_polly_voice(language, gender='female'):
    """Get the best Amazon Polly neural voice for the given language"""
    voices = {
        'EN': {'female': 'Polly.Joanna', 'male': 'Polly.Matthew'},
        'TR': {'female': 'Polly.Filiz', 'male': 'Polly.Filiz'},
        'AR': {'female': 'Polly.Zeina', 'male': 'Polly.Zeina'},
        'DE': {'female': 'Polly.Vicki', 'male': 'Polly.Hans'},
        'RU': {'female': 'Polly.Tatyana', 'male': 'Polly.Maxim'}
    }
    # Default to English female if language/gender not found
    return voices.get(language, voices['EN']).get(gender, voices['EN']['female'])

def get_customer_info(phone_number):
    """
    Lookup customer from Database (Optimized for Speed)
    """
    start_time = time.time()
    
    # CRITICAL FIX: Clean the number before lookup
    # Twilio sends "+90532..." but sometimes "whatsapp:+90532..."
    clean_number = phone_number.replace('whatsapp:', '').strip()
    
    print(f"🔍 Looking up customer: {clean_number}")
    
    # FAST PATH: Get essential customer data
    customer = get_customer_by_phone(clean_number)
    
    if customer and customer.get('customer_id'):
        elapsed = time.time() - start_time
        print(f"✅ Customer found in {elapsed:.2f}s: {customer['full_name']}")
        
        return {
            "customer_id": str(customer['customer_id']),
            "name": customer['full_name'],
            "language": customer.get('preferred_language', 'EN'),
            "phone": clean_number,
            "package": customer.get('package_name', 'None'),
            "is_new_customer": False
        }
    else:
        # Unknown customer - detect language from country code
        print(f"⚠️  Customer not found - using default context")
        
        language = 'EN'
        if clean_number.startswith('+90'):
            language = 'TR'
        elif clean_number.startswith('+49'):
            language = 'DE'
        elif clean_number.startswith('+7'):
            language = 'RU'
        elif clean_number.startswith('+966') or clean_number.startswith('+971'):
            language = 'AR'
        
        print(f"   Detected language from country code: {language}")
        
        return {
            "customer_id": None,
            "name": "Valued Customer",
            "language": language,
            "package": "None",
            "phone": clean_number,
            "is_new_customer": True
        }

def handle_incoming_call():
    """
    Handle incoming phone call - NOW WITH AI GREETING
    """
    try:
        response = VoiceResponse()
        caller = request.values.get('From', '')
        call_sid = request.values.get('CallSid', 'N/A')
        
        print("="*60)
        print(f"📞 INCOMING CALL START")
        print(f"   From: {caller}")
        print(f"   CallSid: {call_sid}")
        print("="*60)
        
        # 1. Get customer info (Fast Lookup)
        customer = get_customer_info(caller)
        
        # 2. Determine Voice Settings immediately based on DB profile
        detected_lang = customer.get('language', 'EN')
        voice = get_polly_voice(detected_lang, gender='female')
        
        # 3. Initialize Memory
        session_id = str(uuid.uuid4())
        conversation_memory[caller] = {
            'session_id': session_id,
            'messages': [],
            'escalation_needed': False,
            'detected_language': detected_lang
        }

        # 4. THE MAGIC: Trigger the AI to generate the greeting
        print("🧠 Triggering AI for personalized greeting...")
        
        # We tell the AI "The call started, YOU say hello."
        trigger_message = "[SYSTEM: INCOMING_CALL_CONNECTED]"
        
        # Initialize history with the system trigger
        initial_history = [{"role": "user", "content": trigger_message}]
        
        # Run AI (Async in Sync context)
        # Note: We pass customer context so it knows the NAME
        try:
            greeting_text = asyncio.run(
                ai_client.ask(
                    initial_history, 
                    customer_context=customer
                )
            )
        except Exception as ai_e:
            print(f"❌ AI Greeting Failed: {ai_e}")
            # Fallback if AI is slow or down
            greeting_text = f"Welcome to Turkcell. I am here to help."

        print(f"💬 AI Greeting: {greeting_text}")
        
        # 5. Update Memory
        # We save the AI response so the conversation flows naturally
        conversation_memory[caller]['messages'].append({"role": "assistant", "content": greeting_text})

        # 6. Build Response
        gather = Gather(
            input='speech',
            action='/voice/process',
            language='auto', 
            speech_timeout='auto',
            timeout=5, # Short timeout keeps it snappy
            hints='internet, data, package, help'
        )
        
        gather.say(greeting_text, voice=voice)
        response.append(gather)
        
        # Fallback if they stay silent
        response.say("I am listening. How can I help?", voice=voice)
        response.redirect('/voice/process') # Loop back
        
        return Response(str(response), mimetype='text/xml')
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        traceback.print_exc()
        # Fallback is crucial for voice
        r = VoiceResponse()
        r.say("Welcome to Turkcell. Please hold.", voice='Polly.Joanna')
        return Response(str(r), mimetype='text/xml')

def process_speech():
    """Process speech input and generate AI response"""
    start_time = time.time()
    
    try:
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
            print("⚠️  Empty speech result")
            customer = get_customer_info(caller)
            voice = get_polly_voice(customer['language'])
            
            response.say("I didn't hear that. Can you repeat?", voice=voice)
            response.redirect('/voice/process') # Try again
            return Response(str(response), mimetype='text/xml')
        
        # Get customer info
        customer = get_customer_info(caller)
        voice = get_polly_voice(customer['language'], gender='female')

        # Get conversation history
        if caller not in conversation_memory:
            # Re-init if memory lost (server restart)
            conversation_memory[caller] = {
                'session_id': str(uuid.uuid4()),
                'messages': [],
                'escalation_needed': False
            }
        
        # Generate AI response
        messages = conversation_memory[caller]["messages"]
        messages.append({"role": "user", "content": speech_result})
        
        print("🧠 Sending to Intelligence Layer...")
        
        try:
            # Pass FULL history + Context to the Brain
            ai_response = asyncio.run(
                ai_client.ask(
                    messages[-6:],  # Pass last 6 messages for context
                    customer_context=customer
                )
            )
        except Exception as ai_e:
            print(f"❌ AI Error: {ai_e}")
            ai_response = "I am having trouble connecting. Please try again."

        elapsed = time.time() - start_time
        print(f"🤖 AI Response ({elapsed:.2f}s): {ai_response}")
        
        # Update Memory
        conversation_memory[caller]['messages'].append({"role": "user", "content": speech_result})
        conversation_memory[caller]['messages'].append({"role": "assistant", "content": ai_response})
        
        # Keep only last 20 messages to save RAM
        if len(conversation_memory[caller]['messages']) > 20:
            conversation_memory[caller]['messages'] = conversation_memory[caller]['messages'][-20:]
        
        # Check for end keywords
        end_keywords = ['goodbye', 'bye', 'thank you', 'hoşçakal', 'teşekkürler', 'شكرا', 'danke', 'спасибо']
        should_end = any(keyword in speech_result.lower() for keyword in end_keywords)
        
        if should_end:
            response.say(ai_response, voice=voice)
            response.say("Goodbye!", voice=voice)
            response.hangup()
        else:
            # Continue conversation
            gather = Gather(
                input='speech',
                action='/voice/process',
                language='auto',
                speech_timeout='auto',
                timeout=5
            )
            gather.say(ai_response, voice=voice)
            response.append(gather)
            
            # Loop fallback
            response.say("Are you still there?", voice=voice)
            response.redirect('/voice/process')
        
        # Log Interaction (Fire and Forget)
        if customer.get('customer_id'):
            try:
                log_interaction(
                    customer['customer_id'],
                    'VOICE',
                    speech_result,
                    ai_response,
                    session_id=conversation_memory[caller]['session_id']
                )
            except:
                pass # Don't crash on logging
        
        return Response(str(response), mimetype='text/xml')
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        traceback.print_exc()
        r = VoiceResponse()
        r.say("System error. Please call back later.", voice='Polly.Joanna')
        return Response(str(r), mimetype='text/xml')