class SafeProvider:
    name = "safe"

    def ask(self, messages, customer_context=None):
        return (
            "I'm sorry, I am having trouble accessing my systems right now. "
            "Please try again later or contact customer support."
        )