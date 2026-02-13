from openai import OpenAI


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    async def ask(self, messages, customer_context=None):

        system_prompt = self._build_system(customer_context)

        final_messages = [{"role": "system", "content": system_prompt}]
        final_messages += messages

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=final_messages,
            temperature=0.3,
        )

        return response.choices[0].message.content

    def _build_system(self, ctx):
        if not ctx:
            return "You are a telecom voice assistant."

        return f"""
You are a telecom AI voice assistant.

Customer Name: {ctx.get('name')}
Language: {ctx.get('language')}
Package: {ctx.get('package')}
"""