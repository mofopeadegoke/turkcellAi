from flask import request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import json
from app.config import Config
from app.database import (
    get_customer_by_phone,
    log_interaction,
    search_knowledge_base,
    check_network_issues,
    get_full_customer_profile,
    create_support_ticket
    
)
from datetime import datetime
import uuid
from openai import OpenAI
import asyncio
from intelligence.intelligence_client import IntelligenceClient

# Global client
ai_client = IntelligenceClient(
    openai_api_key=Config.OPENAI_API_KEY,
    mcp_server_path=Config.MCP_SERVER_PATH,
    primary="openai",
)

# Conversation memory
conversation_memory = {}

def get_openai_client():
    return OpenAI(api_key=Config.OPENAI_API_KEY)


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


def get_customer_info(phone_number):
    """
    Lookup customer from API (instead of direct database access)
    
    This now uses the live API endpoints
    """
    print(f"🔍 Looking up customer via API: {phone_number}")
    
    # Use the full profile function for complete data
    profile = get_full_customer_profile(phone_number)
    
    if profile and profile.get('customer_id'):
        # Calculate days remaining
        days_remaining = 0
        subscription = profile.get('subscription')
        
        if subscription and subscription.get('expiry_date'):
            expiry_date = datetime.fromisoformat(subscription['expiry_date'].replace('Z', '+00:00'))
            days_remaining = (expiry_date - datetime.now()).days
            days_remaining = max(0, days_remaining)
        
        print(f"✅ Customer found via API: {profile['full_name']}")
        
        balance = profile.get('balance', {})
        
        return {
            "customer_id": str(profile['customer_id']),
            "name": profile['full_name'],
            "language": profile.get('preferred_language', 'EN'),
            "phone": profile.get('whatsapp_number') or subscription.get('msisdn') if subscription else phone_number,
            "package": {
                "type": subscription.get('package_name', 'No active package') if subscription else "No active package",
                "data": f"{balance.get('data_remaining_mb', 0) // 1024}GB" if balance else "0GB",
                "days_remaining": days_remaining,
                "price_paid": f"{subscription.get('price_try', 0)} TRY" if subscription else "N/A"
            } if subscription else None,
            "subscription_id": subscription.get('subscription_id') if subscription else None
        }
    else:
        # Unknown customer - detect language from country code
        print(f"⚠️  Customer not found via API - using default")
        
        language = 'EN'
        if phone_number.startswith('+90'):
            language = 'TR'
        elif phone_number.startswith('+49'):
            language = 'DE'
        elif phone_number.startswith('+7'):
            language = 'RU'
        elif phone_number.startswith('+966') or phone_number.startswith('+971'):
            language = 'AR'
        
        print(f"   Detected language from country code: {language}")
        
        return {
            "customer_id": None,
            "name": "Valued Customer",
            "language": language,
            "package": None,
            "phone": phone_number,
            "is_new_customer": True,
            "subscription_id": None
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
    
    if customer_info.get('package'):
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
    try:
        response = VoiceResponse()
        caller = request.values.get('From', '')
        
        print("="*60)
        print(f"📞 INCOMING CALL")
        print(f"   From: {caller}")
        print(f"   CallSid: {request.values.get('CallSid', 'N/A')}")
        print("="*60)
        
        # Get customer info via API
        customer = get_customer_info(caller)
        
        # Initialize conversation memory with session ID
        session_id = str(uuid.uuid4())
        if caller not in conversation_memory:
            conversation_memory[caller] = {
                'session_id': session_id,
                'messages': [],
                'escalation_needed': False
            }
        
        # Different greetings for existing vs new customers
        if customer.get('is_new_customer'):
            greetings = {
                'TR': "Merhaba! Turkcell yapay zeka asistanına hoş geldiniz. Size nasıl yardımcı olabilirim?",
                'AR': "مرحبا! مرحبا بك في مساعد Turkcell الذكي. كيف يمكنني مساعدتك؟",
                'DE': "Hallo! Willkommen beim Turkcell KI-Assistenten. Wie kann ich Ihnen helfen?",
                'RU': "Здравствуйте! Добро пожаловать в ИИ-помощник Turkcell. Чем могу помочь?",
                'EN': "Hello! Welcome to Turkcell's AI assistant. How can I help you today?"
            }
        else:
            greetings = {
                'TR': f"Merhaba {customer['name']}! Ben Turkcell yapay zeka asistanıyım. Size nasıl yardımcı olabilirim?",
                'AR': f"مرحبا {customer['name']}! أنا مساعد الذكاء الاصطناعي من Turkcell. كيف يمكنني مساعدتك؟",
                'DE': f"Hallo {customer['name']}! Ich bin Turkcells KI-Assistent. Wie kann ich Ihnen helfen?",
                'RU': f"Здравствуйте {customer['name']}! Я ИИ-помощник Turkcell. Чем могу помочь?",
                'EN': f"Hello {customer['name']}! I'm Turkcell's AI assistant. How can I help you today?"
            }
        
        greeting = greetings.get(customer['language'], greetings['EN'])
        voice = get_polly_voice(customer['language'], gender='female')
        
        print(f"💬 Greeting ({customer['language']}): {greeting}")
        print(f"🎤 Using voice: {voice}")
        
        # Gather speech input
        gather = Gather(
            input='speech',
            action='/voice/process',
            language='en-US',
            speech_timeout='auto',
            timeout=10,
            hints='internet, SIM card, data, package, price, help, slow, not working'
        )
        
        gather.say(greeting, voice=voice)
        response.append(gather)
        response.say("I didn't hear anything. Please call again if you need help. Goodbye!", voice=voice)
        
        print("✅ Response generated successfully")
        return Response(str(response), mimetype='text/xml')
        
    except Exception as e:
        print("="*60)
        print(f"❌ ERROR IN handle_incoming_call:")
        print(f"   {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        
        response = VoiceResponse()
        response.say("We're sorry, but we're experiencing technical difficulties. Please try again later.", voice='Polly.Joanna')
        return Response(str(response), mimetype='text/xml')


def process_speech():
    """Process speech input and generate AI response"""
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
            print("⚠️  Empty speech result - asking user to repeat")
            
            customer = get_customer_info(caller)
            voice = get_polly_voice(customer['language'], gender='female')
            
            response.say("I'm sorry, I didn't catch that. Could you please repeat?", voice=voice)
            
            gather = Gather(
                input='speech',
                action='/voice/process',
                language='en-US',
                speech_timeout='auto',
                timeout=10
            )
            gather.say("What can I help you with?", voice=voice)
            response.append(gather)
            return Response(str(response), mimetype='text/xml')
        
        # Get customer info via API
        customer = get_customer_info(caller)
        voice = get_polly_voice(customer['language'], gender='female')
        print(f"🎤 Using voice: {voice}")
        
        # Get conversation history
        if caller not in conversation_memory:
            conversation_memory[caller] = {
                'session_id': str(uuid.uuid4()),
                'messages': [],
                'escalation_needed': False
            }
        
        # Generate AI response using your intelligence client
        messages = conversation_memory[caller]["messages"]
        messages.append({"role": "user", "content": speech_result})
        
        ai_response = asyncio.run(
            ai_client.ask(
                messages,
                customer_context=customer
            )
        )
        
        print(f"🤖 AI Response: {ai_response}")
        
        # Update conversation memory
        conversation_memory[caller]['messages'].append({"role": "user", "content": speech_result})
        conversation_memory[caller]['messages'].append({"role": "assistant", "content": ai_response})
        
        # Keep only last 10 exchanges
        if len(conversation_memory[caller]['messages']) > 20:
            conversation_memory[caller]['messages'] = conversation_memory[caller]['messages'][-20:]
        
        # Log to API (only if existing customer)
        if customer.get('customer_id'):
            print(f"💾 Logging interaction via API...")
            try:
                log_interaction(
                    customer['customer_id'],
                    'VOICE',
                    speech_result,
                    ai_response,
                    session_id=conversation_memory[caller]['session_id']
                )
                print(f"✅ Logged successfully via API")
            except Exception as e:
                print(f"⚠️  Failed to log via API: {e}")
        else:
            print(f"ℹ️  New customer - skipping API log")
        
        # Check for escalation keywords
        escalation_keywords = ['speak to human', 'human agent', 'talk to person', 'representative', 
                              'not helping', 'insanları konuş', 'temsilci']
        
        if any(keyword in speech_result.lower() for keyword in escalation_keywords):
            conversation_memory[caller]['escalation_needed'] = True
            
            # Create support ticket via API
            if customer.get('customer_id'):
                ticket_data = {
                    "customer_id": customer['customer_id'],
                    "subscription_id": customer.get('subscription_id'),
                    "issue_type": "ESCALATION_REQUESTED",
                    "priority": "HIGH",
                    "description": f"Customer requested human agent. Last message: {speech_result}",
                    "ai_attempted_resolution": "\n".join([
                        f"{m['role']}: {m['content']}" 
                        for m in conversation_memory[caller]['messages'][-4:]
                    ])
                }
                create_support_ticket(ticket_data)
                print(f"🎫 Support ticket created for escalation")
        
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
                language='en-US',
                speech_timeout='auto',
                timeout=10
            )
            
            gather.say(ai_response, voice=voice)
            response.append(gather)
            response.say("I didn't hear your response. Goodbye!", voice=voice)
        
        print("✅ Response completed successfully")
        return Response(str(response), mimetype='text/xml')
        
    except Exception as e:
        print("="*60)
        print(f"❌ ERROR IN process_speech:")
        print(f"   {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        
        response = VoiceResponse()
        response.say("We're sorry, an error occurred. Please try again.", voice='Polly.Joanna')
        return Response(str(response), mimetype='text/xml')