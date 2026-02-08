from flask import request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import json
from app.config import Config

# Load customer database
with open('app/customer_db.json', 'r', encoding='utf-8') as f:
    CUSTOMER_DB = json.load(f)

# Load knowledge base
with open('app/knowledge_base.json', 'r', encoding='utf-8') as f:
    KNOWLEDGE_BASE = json.load(f)

# Conversation memory (in production, use Redis or database)
conversation_memory = {}


def get_openai_client():
    """Lazy load OpenAI client to avoid initialization errors"""
    from openai import OpenAI
    return OpenAI(api_key=Config.OPENAI_API_KEY)


def get_customer_info(phone_number):
    """Lookup customer by phone number"""
    # Remove 'whatsapp:' prefix if present
    phone = phone_number.replace('whatsapp:', '').strip()
    
    customer = CUSTOMER_DB.get(phone)
    if customer:
        return customer
    else:
        # Return default for unknown customers
        return {
            "name": "Valued Customer",
            "language": "English",
            "package": None,
            "phone": phone,
            "issues": []
        }


def generate_ai_response(customer_info, user_message, conversation_history):
    """Generate personalized AI response using GPT-4"""
    
    # Get OpenAI client (lazy load)
    client = get_openai_client()
    
    # Build system prompt with customer context
    system_prompt = f"""You are a helpful Turkcell customer service AI assistant.

CUSTOMER INFORMATION:
- Name: {customer_info['name']}
- Preferred Language: {customer_info['language']}
- Phone: {customer_info['phone']}
"""
    
    if customer_info['package']:
        system_prompt += f"""- Current Package: {customer_info['package']['type']}
- Data Allowance: {customer_info['package']['data']}
- Days Remaining: {customer_info['package']['days_remaining']}
- Price Paid: {customer_info['package']['price_paid']}
"""
    
    system_prompt += f"""
KNOWLEDGE BASE:
{json.dumps(KNOWLEDGE_BASE, indent=2, ensure_ascii=False)}

INSTRUCTIONS:
1. Always respond in the customer's preferred language: {customer_info['language']}
2. Be warm, helpful, and professional
3. Use the customer's name naturally
4. Reference their specific package details when relevant
5. Keep responses concise (2-3 sentences for voice)
6. If you need to give step-by-step instructions, number them clearly
7. If the issue is complex, offer to escalate to a human agent

IMPORTANT FOR VOICE:
- Keep responses SHORT and CLEAR (voice is harder to follow than text)
- Use simple language
- Avoid long lists - max 3 items at a time
- Ask ONE question at a time
"""
    
    # Build conversation history
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})
    
    # Get AI response
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.7,
        max_tokens=150  # Keep responses short for voice
    )
    
    return response.choices[0].message.content


def handle_incoming_call():
    """Handle incoming phone call"""
    response = VoiceResponse()
    
    # Get caller's phone number
    caller = request.values.get('From', '')
    
    # Get customer info
    customer = get_customer_info(caller)
    
    # Initialize conversation memory
    if caller not in conversation_memory:
        conversation_memory[caller] = []
    
    # Personalized greeting
    if customer['language'] == 'Turkish':
        greeting = f"Merhaba {customer['name']}! Ben Turkcell yapay zeka asistanıyım. Size nasıl yardımcı olabilirim?"
    elif customer['language'] == 'Arabic':
        greeting = f"مرحبا {customer['name']}! أنا مساعد الذكاء الاصطناعي من Turkcell. كيف يمكنني مساعدتك؟"
    else:
        greeting = f"Hello {customer['name']}! I'm Turkcell's AI assistant. How can I help you today?"
    
    # Use Gather to collect speech input
    gather = Gather(
        input='speech',
        action='/voice/process',
        language='en-US',  # Will auto-detect language
        speech_timeout='auto',
        timeout=5
    )
    
    gather.say(greeting, voice='Polly.Joanna')  # Using Amazon Polly voice
    
    response.append(gather)
    
    # If no input, repeat
    response.say("I didn't hear anything. Please call again if you need help. Goodbye!")
    
    return Response(str(response), mimetype='text/xml')


def process_speech():
    """Process speech input and generate AI response"""
    response = VoiceResponse()
    
    caller = request.values.get('From', '')
    speech_result = request.values.get('SpeechResult', '')
    
    print(f"🎤 Caller {caller} said: {speech_result}")
    
    # Get customer info
    customer = get_customer_info(caller)
    
    # Get conversation history
    if caller not in conversation_memory:
        conversation_memory[caller] = []
    
    # Generate AI response
    ai_response = generate_ai_response(
        customer, 
        speech_result, 
        conversation_memory[caller]
    )
    
    print(f"🤖 AI responds: {ai_response}")
    
    # Update conversation memory
    conversation_memory[caller].append({"role": "user", "content": speech_result})
    conversation_memory[caller].append({"role": "assistant", "content": ai_response})
    
    # Keep only last 10 exchanges (20 messages)
    if len(conversation_memory[caller]) > 20:
        conversation_memory[caller] = conversation_memory[caller][-20:]
    
    # Check if conversation should end
    end_keywords = ['goodbye', 'bye', 'thank you', 'thanks', 'that\'s all', 
                    'hoşçakal', 'teşekkürler', 'شكرا', 'وداعا']
    
    should_end = any(keyword in speech_result.lower() for keyword in end_keywords)
    
    if should_end:
        response.say(ai_response, voice='Polly.Joanna')
        response.say("Thank you for calling Turkcell. Goodbye!", voice='Polly.Joanna')
        response.hangup()
    else:
        # Continue conversation - gather more input
        gather = Gather(
            input='speech',
            action='/voice/process',
            language='en-US',
            speech_timeout='auto',
            timeout=5
        )
        
        gather.say(ai_response, voice='Polly.Joanna')
        response.append(gather)
        
        # Fallback if no response
        response.say("I didn't hear your response. Goodbye!", voice='Polly.Joanna')
    
    return Response(str(response), mimetype='text/xml')