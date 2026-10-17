import os

from dotenv import load_dotenv
from anthropic import Anthropic


load_dotenv()


class ClaudeAssistant:
    """Conexión con Claude (Anthropic)."""

    nombre = "Claude"

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            raise ValueError(
                "No se encontró ANTHROPIC_API_KEY en el archivo .env"
            )

        self.client = Anthropic(api_key=api_key)
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")

    def ask(self, question, instructions, history=None):

        messages = list(history or [])
        messages.append({"role": "user", "content": question})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=instructions,
            messages=messages,
        )

        return "".join(
            block.text
            for block in response.content
            if block.type == "text"
        ).strip()
