# """
# Streaming voice handler with immediate acknowledgment and sentence-by-sentence TTS
# """
# import json
# import asyncio
# import base64
# from openai import OpenAI
# from app.config import Config
# from app.database import get_customer_by_phone, log_interaction
# from app.voice_handler import detect_language_from_speech, get_polly_voice
# import uuid
# from datetime import datetime

# # Initialize OpenAI
# openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)

# # Session storage
# active_sessions = {}


# class StreamingSession:
#     """Manages a streaming voice call session"""
    
#     def __init__(self, stream_sid, caller_number):
#         self.stream_sid = stream_sid
#         self.caller_number = caller_number
#         self.customer = None
#         self.conversation_history = []
#         self.detected_language = None
#         self.session_id = str(uuid.uuid4())
#         self.audio_buffer = b''
#         self.is_speaking = False
        
#     def add_message(self, role, content):
#         """Add message to conversation history"""
#         self.conversation_history.append({
#             "role": role,
#             "content": content,
#             "timestamp": datetime.now()
#         })
        
#         # Keep only last 10 messages
#         if len(self.conversation_history) > 10:
#             self.conversation_history = self.conversation_history[-10:]


# async def handle_media_stream(ws):
#     """
#     Handle Twilio Media Stream WebSocket connection
    
#     This enables real-time audio streaming for instant responses
#     """
#     print("🎙️ Media stream connected")
    
#     session = None
    
#     try:
#         while True:
#             # Receive message from Twilio
#             message = await ws.receive()
            
#             if message is None:
#                 break
            
#             data = json.loads(message)
#             event = data.get('event')
            
#             # ===== STREAM START =====
#             if event == 'start':
#                 stream_sid = data['start']['streamSid']
#                 caller = data['start']['customParameters'].get('caller', 'unknown')
                
#                 print(f"📞 Stream started: {stream_sid}")
#                 print(f"   Caller: {caller}")
                
#                 # Create session
#                 session = StreamingSession(stream_sid, caller)
#                 active_sessions[stream_sid] = session
                
#                 # Get customer info from API
#                 session.customer = get_customer_by_phone(caller)
#                 if not session.customer:
#                     session.customer = {
#                         'name': 'Valued Customer',
#                         'language': 'EN',
#                         'phone': caller
#                     }
                
#                 # IMMEDIATE MULTILINGUAL GREETING
#                 greeting = "Hello! Merhaba! How can I help you today?"
                
#                 print(f"💬 Greeting: {greeting}")
                
#                 # Send greeting audio immediately
#                 await send_tts_audio(ws, stream_sid, greeting, session.customer.get('language', 'EN'))
            
#             # ===== AUDIO FROM CALLER =====
#             elif event == 'media':
#                 if not session:
#                     continue
                
#                 # Get audio payload (base64 encoded μ-law)
#                 payload = data['media']['payload']
                
#                 # Decode audio chunk
#                 audio_chunk = base64.b64decode(payload)
#                 session.audio_buffer += audio_chunk
                
#                 # When we have enough audio (e.g., 1 second), transcribe
#                 # For now, we'll process on silence detection
#                 # Twilio sends audio continuously, so we need silence detection
                
#             # ===== MARK (Speech boundaries) =====
#             elif event == 'mark':
#                 # Mark events help us know when TTS finished playing
#                 mark_name = data.get('mark', {}).get('name')
#                 print(f"🔊 Mark received: {mark_name}")
#                 session.is_speaking = False
            
#             # ===== STOP =====
#             elif event == 'stop':
#                 print(f"📞 Stream ended: {session.stream_sid if session else 'unknown'}")
                
#                 if session and session.stream_sid in active_sessions:
#                     del active_sessions[session.stream_sid]
                
#                 break
    
#     except Exception as e:
#         print(f"❌ Stream error: {e}")
#         import traceback
#         traceback.print_exc()
    
#     finally:
#         if session and session.stream_sid in active_sessions:
#             del active_sessions[session.stream_sid]


# async def send_tts_audio(ws, stream_sid, text, language='EN'):
#     """
#     Convert text to speech and send to Twilio in real-time
    
#     Uses OpenAI TTS for high-quality, fast audio generation
#     """
#     try:
#         print(f"🔊 Sending TTS: {text[:50]}...")
        
#         # Map language to OpenAI TTS voices
#         voice_map = {
#             'EN': 'alloy',
#             'TR': 'onyx',
#             'AR': 'shimmer',
#             'DE': 'echo',
#             'RU': 'fable'
#         }
        
#         voice = voice_map.get(language, 'alloy')
        
#         # Generate speech with OpenAI TTS
#         response = openai_client.audio.speech.create(
#             model="tts-1",  # Fast model
#             voice=voice,
#             input=text,
#             response_format="pcm"  # Raw PCM for streaming
#         )
        
#         # Get audio bytes
#         audio_bytes = response.content
        
#         # Convert PCM to μ-law (Twilio's format)
#         # For now, send as base64 chunks
#         audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
#         # Split into chunks (Twilio expects chunks, not full audio)
#         chunk_size = 8000  # bytes per chunk
#         for i in range(0, len(audio_base64), chunk_size):
#             chunk = audio_base64[i:i+chunk_size]
            
#             # Send to Twilio
#             await ws.send(json.dumps({
#                 "event": "media",
#                 "streamSid": stream_sid,
#                 "media": {
#                     "payload": chunk
#                 }
#             }))
            
#             # Small delay to match audio timing
#             await asyncio.sleep(0.02)
        
#         # Send mark to know when done
#         await ws.send(json.dumps({
#             "event": "mark",
#             "streamSid": stream_sid,
#             "mark": {
#                 "name": f"done_{uuid.uuid4().hex[:8]}"
#             }
#         }))
        
#     except Exception as e:
#         print(f"❌ TTS error: {e}")


# async def stream_gpt_response(ws, stream_sid, session, user_text):
#     """
#     Stream GPT response sentence by sentence
    
#     As soon as GPT generates a sentence, convert to speech and send
#     """
#     print(f"🤖 Generating streaming response for: {user_text}")
    
#     # Detect language from speech
#     detected_lang = detect_language_from_speech(user_text)
#     session.detected_language = detected_lang
    
#     # Update customer language
#     if session.customer:
#         session.customer['language'] = detected_lang
    
#     # Build prompt
#     system_prompt = f"""You are a helpful Turkcell customer service AI.
# Customer: {session.customer.get('name', 'Customer')}
# Language: {detected_lang}

# Respond in {detected_lang}. Be concise. Max 3 sentences total."""
    
#     messages = [{"role": "system", "content": system_prompt}]
    
#     # Add recent history
#     for msg in session.conversation_history[-4:]:
#         messages.append({
#             "role": msg["role"],
#             "content": msg["content"]
#         })
    
#     messages.append({"role": "user", "content": user_text})
    
#     # Stream from GPT
#     stream = openai_client.chat.completions.create(
#         model="gpt-3.5-turbo",
#         messages=messages,
#         stream=True,
#         temperature=0.7,
#         max_tokens=100
#     )
    
#     # Buffer for sentence building
#     sentence_buffer = ""
#     full_response = ""
    
#     for chunk in stream:
#         if chunk.choices[0].delta.content:
#             content = chunk.choices[0].delta.content
#             sentence_buffer += content
#             full_response += content
            
#             # Check if we have a complete sentence
#             if any(punct in content for punct in ['.', '!', '?', '\n']):
#                 # We have a sentence! Send it immediately
#                 sentence = sentence_buffer.strip()
                
#                 if sentence:
#                     print(f"📢 Sentence ready: {sentence}")
                    
#                     # Convert to speech and send IMMEDIATELY
#                     await send_tts_audio(ws, stream_sid, sentence, detected_lang)
                    
#                     sentence_buffer = ""
    
#     # Send any remaining text
#     if sentence_buffer.strip():
#         await send_tts_audio(ws, stream_sid, sentence_buffer.strip(), detected_lang)
    
#     print(f"✅ Complete response: {full_response}")
    
#     # Update conversation history
#     session.add_message("user", user_text)
#     session.add_message("assistant", full_response)
    
#     # Log to database
#     if session.customer.get('customer_id'):
#         try:
#             log_interaction(
#                 session.customer['customer_id'],
#                 'VOICE_STREAM',
#                 user_text,
#                 full_response,
#                 session_id=session.session_id
#             )
#         except:
#             pass


"""
Simple streaming voice handler with acknowledgment
Uses standard Twilio without complex WebSocket streaming
"""
import asyncio
from app.database import get_customer_by_phone, log_interaction
from app.voice_handler import detect_language_from_speech, get_polly_voice
from intelligence.intelligence_client import IntelligenceClient
from app.config import Config
import uuid

async def handle_media_stream(ws):
    """
    Placeholder for media stream handling
    
    For now, this just logs that streaming was attempted.
    Full implementation requires audio processing setup.
    """
    print("🎙️ Media stream handler called (not fully implemented yet)")
    print("   For now, use /voice/incoming endpoint")
    print("   Full streaming requires additional audio processing setup")
    
    # Close the WebSocket gracefully
    await ws.close()