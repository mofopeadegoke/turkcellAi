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
ai_client = IntelligenceClient(
    openai_api_key=Config.OPENAI_API_KEY,
    mcp_server_path=Config.MCP_SERVER_PATH,
    primary="openai", 
)

# In-memory session storage
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
    return voices.get(language, voices['EN']).get(gender, voices['EN']['female'])


def detect_language_from_speech(text):
    """
    Detect language from the actual speech content
    Uses simple keyword detection + character analysis
    """
    text_lower = text.lower()
    
    # Quick language detection by common words
    language_indicators = {
        'EN': ['hello', 'hi', 'help', 'internet', 'data', 'package', 'problem', 'my', 'the', 'is', 'not', 'working'],
        'TR': ['merhaba', 'yardım', 'paket', 'internet', 'benim', 'için', 'var', 'yok', 'nasıl', 'ne'],
        'AR': ['مرحبا', 'مساعدة', 'الإنترنت', 'بيانات', 'باقة'],
        'DE': ['hallo', 'hilfe', 'internet', 'daten', 'paket', 'mein', 'nicht'],
        'RU': ['привет', 'помощь', 'интернет', 'пакет', 'мой']
    }
    
    # Count matches for each language
    scores = {}
    for lang, indicators in language_indicators.items():
        score = sum(1 for word in indicators if word in text_lower)
        if score > 0:
            scores[lang] = score
    
    # Return language with highest score
    if scores:
        detected = max(scores, key=scores.get)
        print(f"   🌍 Language detected from speech: {detected} (confidence: {scores[detected]} words)")
        return detected
    
    # Fallback: ASCII ratio detection
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / len(text) if text else 0
    
    if ascii_ratio > 0.9:
        print(f"   🌍 Language detected: EN (ASCII ratio: {ascii_ratio:.2f})")
        return 'EN'
    
    print(f"   🌍 Language detection uncertain, defaulting to EN")
    return 'EN'


def get_customer_info(phone_number):
    """
    Lookup customer from Database (Optimized for Speed)
    """
    start_time = time.time()
    
    # CRITICAL FIX: Clean the number before lookup
    clean_number = phone_number.replace('whatsapp:', '').strip()
    
    print(f"🔍 Looking up customer: {clean_number}")
    
    # FAST PATH: Get essential customer data
    customer = get_customer_by_phone(clean_number)
    
    if customer and customer.get('customer_id'):
        elapsed = time.time() - start_time
        print(f"✅ Customer found in {elapsed:.2f}s: {customer.get('full_name', 'Unknown')}")
        
        return {
            "customer_id": str(customer['customer_id']),
            "name": customer.get('full_name', 'Valued Customer'),
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
    Handle incoming phone call - WITH AI-GENERATED PERSONALIZED GREETING
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
        
        # 2. Determine Voice Settings based on customer profile
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

        # 4. AI-GENERATED PERSONALIZED GREETING
        print("🧠 Generating AI personalized greeting...")
        
        # Tell the AI to greet the customer
        trigger_message = f"[SYSTEM: Call connected. Greet the customer. Their name is {customer['name']}. Speak in {detected_lang} language. Be brief and welcoming.]"
        
        # Initialize history
        initial_history = [{"role": "user", "content": trigger_message}]
        
        # Run AI (with timeout protection)
        try:
            greeting_text = asyncio.wait_for(
                ai_client.ask(initial_history, customer_context=customer),
                timeout=3.0  # 3 second timeout for greeting
            )
            greeting_text = asyncio.run(greeting_text)
        except asyncio.TimeoutError:
            print("⚠️  AI greeting timeout - using fallback")
            # Fallback greeting
            if customer.get('is_new_customer'):
                greeting_text = "Hello! Merhaba! I'm Turkcell's AI assistant. How can I help you?"
            else:
                greetings = {
                    'TR': f"Merhaba {customer['name']}! Size nasıl yardımcı olabilirim?",
                    'AR': f"مرحبا {customer['name']}! كيف يمكنني مساعدتك؟",
                    'DE': f"Hallo {customer['name']}! Wie kann ich Ihnen helfen?",
                    'RU': f"Здравствуйте {customer['name']}! Чем могу помочь?",
                    'EN': f"Hello {customer['name']}! How can I help you today?"
                }
                greeting_text = greetings.get(detected_lang, greetings['EN'])
        except Exception as ai_e:
            print(f"❌ AI Greeting Failed: {ai_e}")
            # Fallback
            greeting_text = f"Welcome to Turkcell. How can I help you?"

        print(f"💬 Greeting: {greeting_text}")
        print(f"🎤 Using voice: {voice}")
        
        # 5. Update Memory with greeting
        conversation_memory[caller]['messages'].append({
            "role": "assistant", 
            "content": greeting_text
        })

        # 6. Build Response with Speech Gathering
        gather = Gather(
            input='speech',
            action='/voice/process',
            language='auto',  # Auto-detect language from speech
            speech_timeout='auto',
            timeout=10,
            hints='internet, data, package, help, slow, not working'
        )
        
        gather.say(greeting_text, voice=voice)
        response.append(gather)
        
        # Fallback if no speech detected
        response.say("I didn't hear anything. Please call again if you need help. Goodbye!", voice=voice)
        
        print("✅ Greeting sent successfully")
        return Response(str(response), mimetype='text/xml')
        
    except Exception as e:
        print("="*60)
        print(f"❌ ERROR IN handle_incoming_call:")
        print(f"   {e}")
        print("="*60)
        traceback.print_exc()
        
        # Fallback response
        r = VoiceResponse()
        r.say("Welcome to Turkcell. Please hold.", voice='Polly.Joanna')
        return Response(str(r), mimetype='text/xml')


def process_speech():
    """
    Process speech input with:
    1. Language detection from speech
    2. Immediate acknowledgment
    3. AI response generation
    """
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
            voice = get_polly_voice(customer['language'], gender='female')
            
            response.say("I'm sorry, I didn't catch that. Could you please repeat?", voice=voice)
            
            gather = Gather(
                input='speech',
                action='/voice/process',
                language='auto',
                speech_timeout='auto',
                timeout=10
            )
            gather.say("What can I help you with?", voice=voice)
            response.append(gather)
            return Response(str(response), mimetype='text/xml')
        
        # Get customer info
        customer = get_customer_info(caller)
        
        # CRITICAL: Detect language from actual speech, not just phone number
        detected_language = detect_language_from_speech(speech_result)
        
        # Override customer language with detected language if different
        if detected_language != customer['language']:
            print(f"   🔄 Overriding customer language {customer['language']} → {detected_language}")
            customer['language'] = detected_language
        
        voice = get_polly_voice(customer['language'], gender='female')
        print(f"🎤 Using voice: {voice} for language: {customer['language']}")
        
        # IMMEDIATE ACKNOWLEDGMENT (plays while AI thinks)
        acknowledgments = {
            'EN': "Let me help you with that.",
            'TR': "Size yardımcı olayım.",
            'AR': "دعني أساعدك.",
            'DE': "Ich helfe Ihnen gerne.",
            'RU': "Позвольте мне помочь."
        }
        
        response.say(acknowledgments.get(customer['language'], acknowledgments['EN']), voice=voice)
        
        # Get conversation history
        if caller not in conversation_memory:
            # Re-init if memory lost
            conversation_memory[caller] = {
                'session_id': str(uuid.uuid4()),
                'messages': [],
                'escalation_needed': False,
                'detected_language': detected_language
            }
        else:
            # Update detected language in session
            conversation_memory[caller]['detected_language'] = detected_language
        
        # Build conversation context
        messages = conversation_memory[caller]["messages"]
        messages.append({"role": "user", "content": speech_result})
        
        # Generate AI response
        ai_start = time.time()
        print("🧠 Sending to Intelligence Layer...")
        
        try:
            # Pass last 6 messages for context efficiency
            ai_response = asyncio.run(
                ai_client.ask(
                    messages[-6:],
                    customer_context=customer
                )
            )
        except Exception as ai_e:
            print(f"❌ AI Error: {ai_e}")
            traceback.print_exc()
            ai_response = "I'm having trouble connecting to the network right now. Please try again in a moment."

        ai_elapsed = time.time() - ai_start
        total_elapsed = time.time() - start_time
        print(f"🤖 AI Response ({ai_elapsed:.2f}s, total: {total_elapsed:.2f}s): {ai_response}")
        
        # Update Memory
        conversation_memory[caller]['messages'].append({"role": "user", "content": speech_result})
        conversation_memory[caller]['messages'].append({"role": "assistant", "content": ai_response})
        
        # Keep only last 20 messages to save memory
        if len(conversation_memory[caller]['messages']) > 20:
            conversation_memory[caller]['messages'] = conversation_memory[caller]['messages'][-20:]
        
        # Log to API (fire and forget - don't block)
        if customer.get('customer_id'):
            try:
                log_interaction(
                    customer['customer_id'],
                    'VOICE',
                    speech_result,
                    ai_response,
                    session_id=conversation_memory[caller]['session_id']
                )
            except Exception as log_e:
                print(f"⚠️  Log failed: {log_e}")
        
        # Check for end keywords
        end_keywords = ['goodbye', 'bye', 'thank you', 'thanks', 'that\'s all', 
                        'hoşçakal', 'teşekkürler', 'شكرا', 'وداعا', 'danke', 'спасибо']
        
        should_end = any(keyword in speech_result.lower() for keyword in end_keywords)
        
        if should_end:
            response.say(ai_response, voice=voice)
            response.say("Thank you for calling Turkcell. Goodbye!", voice=voice)
            response.hangup()
        else:
            # Continue conversation
            gather = Gather(
                input='speech',
                action='/voice/process',
                language='auto',
                speech_timeout='auto',
                timeout=10
            )
            
            gather.say(ai_response, voice=voice)
            response.append(gather)
            
            # Fallback if no response
            response.say("I didn't hear your response. Goodbye!", voice=voice)
        
        print("✅ Response completed successfully")
        return Response(str(response), mimetype='text/xml')
        
    except Exception as e:
        print("="*60)
        print(f"❌ CRITICAL ERROR IN process_speech:")
        print(f"   {e}")
        print("="*60)
        traceback.print_exc()
        
        r = VoiceResponse()
        r.say("We're sorry, an error occurred. Please try again.", voice='Polly.Joanna')
        return Response(str(r), mimetype='text/xml')