import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


class Assistant:
    """Conexión con ChatGPT (OpenAI)."""

    nombre = "ChatGPT"

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "No se encontró OPENAI_API_KEY en el archivo .env"
            )

        self.client = OpenAI(api_key=api_key, timeout=float(os.getenv("IA_TIMEOUT", "90")), max_retries=2)
        self.model = os.getenv("OPENAI_MODEL", "gpt-5")

    def ask(self, question, instructions, history=None):

        messages = list(history or [])
        messages.append({"role": "user", "content": question})

        response = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=messages,
        )

        return response.output_text.strip()
