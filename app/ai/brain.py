"""
Cerebro de JARVIS: coordina a ChatGPT y Claude.

Modos:
  - equipo  -> ChatGPT hace un borrador y Claude lo revisa, corrige y
               entrega la respuesta final (trabajan de la mano).
  - claude  -> solo Claude responde.
  - chatgpt -> solo ChatGPT responde.

Si una de las dos IAs falla o no tiene clave, la otra responde sola,
así JARVIS nunca se queda callado.
"""

import os
import re
import unicodedata

from app.ai.assistant import Assistant
from app.ai.claude_assistant import ClaudeAssistant


PERSONALIDAD = (
    "Eres JARVIS, el asistente personal de Yael dentro de YAELCORE-OS. "
    "Hablas siempre en español. "
    "Eres profesional, elegante, claro y directo. "
    "Ayudas a Yael de forma práctica. "
    "Tus respuestas se leen en voz alta: sé breve (máximo 4 frases), "
    "sin listas, sin markdown, sin emojis y sin enlaces."
)

INSTRUCCIONES_REVISOR = (
    PERSONALIDAD
    + " Trabajas en equipo con ChatGPT. Recibirás la pregunta de Yael y "
    "el borrador de ChatGPT. Verifica que sea correcto, corrige errores, "
    "agrega lo que falte y entrega SOLO la respuesta final para Yael, "
    "sin mencionar el borrador ni el proceso."
)

MODOS = ("equipo", "claude", "chatgpt")
MAX_TURNOS_MEMORIA = 6


def _normalizar(texto):
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    # "chat gpt", "chat g p t", "chat-gpt" -> "chatgpt"
    texto = re.sub(r"chat\s*-?\s*g\s*\.?\s*p\s*\.?\s*t", "chatgpt", texto)
    # El reconocimiento de voz a veces oye "cloud", "clod" o "claud"
    texto = re.sub(r"\b(cloud|clod|claud|clau)\b", "claude", texto)
    return texto


class Brain:

    def __init__(self):
        self.chatgpt = self._conectar(Assistant)
        self.claude = self._conectar(ClaudeAssistant)

        if not self.chatgpt and not self.claude:
            raise ValueError(
                "No hay ninguna IA disponible. Agrega OPENAI_API_KEY "
                "y/o ANTHROPIC_API_KEY en el archivo .env"
            )

        modo = os.getenv("JARVIS_MODO", "equipo").lower()
        self.modo = modo if modo in MODOS else "equipo"
        self.historial = []

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    @staticmethod
    def _conectar(clase):
        try:
            return clase()
        except Exception as error:
            print(f"AVISO - {clase.nombre} no disponible: {error}")
            return None

    def disponibles(self):
        return [ia.nombre for ia in (self.chatgpt, self.claude) if ia]

    # ------------------------------------------------------------------
    # Comandos de voz para controlar el cerebro
    # ------------------------------------------------------------------

    def handle_control(self, comando):
        """Devuelve una respuesta si el comando es de control; si no, None."""

        texto = _normalizar(comando)

        # Preguntar directo a una IA: "pregúntale a claude ..."
        directo = re.search(
            r"preguntale a (claude|chatgpt)\s*(.*)", texto
        )
        if directo:
            ia = self.claude if directo.group(1) == "claude" else self.chatgpt
            pregunta = directo.group(2).strip(" ,.:")
            if not pregunta:
                return "¿Qué quiere que le pregunte, señor?"
            if not ia:
                return f"{directo.group(1).title()} no está conectado."
            return self._preguntar_a(ia, pregunta)

        if "modo equipo" in texto or "trabajen juntos" in texto:
            return self._cambiar_modo("equipo")

        if re.search(r"\b(usa|modo|activa)\s+claude\b", texto):
            return self._cambiar_modo("claude")

        if re.search(r"\b(usa|modo|activa)\s+chatgpt\b", texto):
            return self._cambiar_modo("chatgpt")

        if "que modo" in texto or "que inteligencia" in texto:
            return self._describir_modo()

        if "olvida la conversacion" in texto:
            self.historial = []
            return "Listo, empecemos desde cero."

        return None

    def _cambiar_modo(self, modo):
        if modo == "claude" and not self.claude:
            return "Claude no está conectado. Revise ANTHROPIC_API_KEY."
        if modo == "chatgpt" and not self.chatgpt:
            return "ChatGPT no está conectado. Revise OPENAI_API_KEY."
        if modo == "equipo" and not (self.claude and self.chatgpt):
            return (
                "Para el modo equipo necesito a Claude y a ChatGPT "
                "conectados. Solo tengo a " + self.disponibles()[0] + "."
            )
        self.modo = modo
        return self._describir_modo()

    def _describir_modo(self):
        if self.modo == "equipo":
            return (
                "Modo equipo activo: ChatGPT prepara la respuesta "
                "y Claude la revisa antes de entregársela."
            )
        nombre = "Claude" if self.modo == "claude" else "ChatGPT"
        return f"Modo {nombre} activo. Solo {nombre} responde."

    # ------------------------------------------------------------------
    # Pensar
    # ------------------------------------------------------------------

    def ask(self, pregunta):

        if self.modo == "equipo" and self.chatgpt and self.claude:
            respuesta = self._en_equipo(pregunta)
        elif self.modo == "chatgpt" and self.chatgpt:
            respuesta = self._con_respaldo(self.chatgpt, self.claude, pregunta)
        else:
            respuesta = self._con_respaldo(self.claude, self.chatgpt, pregunta)

        self._recordar(pregunta, respuesta)
        return respuesta

    def _preguntar_a(self, ia, pregunta):
        try:
            respuesta = ia.ask(pregunta, PERSONALIDAD, self.historial)
        except Exception as error:
            print(f"ERROR - {ia.nombre}: {error}")
            return f"{ia.nombre} no pudo responder en este momento."
        self._recordar(pregunta, respuesta)
        return respuesta

    def _en_equipo(self, pregunta):

        # 1. ChatGPT prepara el borrador
        try:
            borrador = self.chatgpt.ask(
                pregunta, PERSONALIDAD, self.historial
            )
            print("DEBUG - Borrador de ChatGPT:", borrador)
        except Exception as error:
            print(f"ERROR - ChatGPT: {error}. Claude responde solo.")
            return self._con_respaldo(self.claude, None, pregunta)

        # 2. Claude revisa y entrega la versión final
        try:
            revision = (
                f"Pregunta de Yael:\n{pregunta}\n\n"
                f"Borrador de ChatGPT:\n{borrador}"
            )
            final = self.claude.ask(
                revision, INSTRUCCIONES_REVISOR, self.historial
            )
            print("DEBUG - Versión final de Claude:", final)
            return final
        except Exception as error:
            print(f"ERROR - Claude: {error}. Se usa el borrador de ChatGPT.")
            return borrador

    def _con_respaldo(self, principal, respaldo, pregunta):
        for ia in (principal, respaldo):
            if not ia:
                continue
            try:
                return ia.ask(pregunta, PERSONALIDAD, self.historial)
            except Exception as error:
                print(f"ERROR - {ia.nombre}: {error}")
        return "Lo siento, señor. No pude conectar con ninguna inteligencia."

    def _recordar(self, pregunta, respuesta):
        self.historial.extend([
            {"role": "user", "content": pregunta},
            {"role": "assistant", "content": respuesta},
        ])
        self.historial = self.historial[-MAX_TURNOS_MEMORIA * 2:]
