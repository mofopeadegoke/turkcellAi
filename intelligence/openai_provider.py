from openai import OpenAI

# --- THE BRAIN: System Instructions ---
SYSTEM_PROMPT_TEMPLATE = """
You are the Turkcell AI Assistant, a helpful and professional virtual agent for Turkey's leading telecom provider.

YOUR GOAL:
Help international tourists and local customers with their mobile connectivity needs.
You must be polite, concise, and accurate.

CUSTOMER CONTEXT:
- Name: {name}
- Language: {language}
- Current Package: {package}

RULES FOR VOICE INTERACTION:
1. KEEP IT SHORT: You are speaking on a phone call. Responses must be under 2-3 sentences.
2. NO MARKDOWN: Do not use **bold** or # headings. Speak naturally.
3. BE HELPFUL: If you don't know an answer, suggest visiting a Turkcell store or using the mobile app.
4. EMERGENCY: If the user mentions "emergency" or "police", tell them to dial 112 immediately.
5. SCAM ALERT: If a user mentions paying high prices (over 1000 TRY) for a SIM, warn them it might be a scam. Official tourist SIMs are around 400-600 TRY.

TONE:
- Warm, welcoming, and professional.
- Speak in the user's preferred language ({language}).
"""

class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    async def ask(self, messages, customer_context=None):
        # 1. Build the smart prompt with real customer data
        system_prompt = self._build_system(customer_context)

        # 2. Insert it as the very first message
        final_messages = [{"role": "system", "content": system_prompt}]
        final_messages += messages

        # 3. Call OpenAI with a slightly lower temperature for consistency
        response = self.client.chat.completions.create(
            model="gpt-4o",  # Use the smart model
            messages=final_messages,
            temperature=0.3, 
            max_tokens=150,  # Keep voice answers short!
        )

        return response.choices[0].message.content

    def _build_system(self, ctx):
        # Default values if context is missing
        if not ctx:
            ctx = {"name": "Valued Customer", "language": "English", "package": "Unknown"}
        
        # Fill in the template
        return SYSTEM_PROMPT_TEMPLATE.format(
            name=ctx.get('name', 'Valued Customer'),
            language=ctx.get('language', 'English'),
            package=ctx.get('package', 'Unknown')
        )