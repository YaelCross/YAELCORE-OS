from datetime import datetime
import os
import threading
import webbrowser

from app.integrations.whatsapp import WhatsApp, WhatsAppError


class CommandManager:

    def __init__(self):
        self.whatsapp = WhatsApp()

    def execute(self, command):
        original = command
        command = command.lower()

        # WhatsApp: "envía un whatsapp diciendo ..."
        if "whatsapp" in command:
            return self.send_whatsapp(original)

        # Saludo
        elif "hola" in command:
            return "Hola señor Yael. ¿Cómo puedo ayudarle?"

        # Hora
        elif "hora" in command:
            hora = datetime.now().strftime("%H:%M")
            return f"Son las {hora}"

        # Fecha
        elif "fecha" in command:
            fecha = datetime.now().strftime("%d/%m/%Y")
            return f"Hoy es {fecha}"

        # Google
        elif "google" in command:
            webbrowser.open("https://www.google.com")
            return "Abriendo Google."

        # Centro de Mando del equipo
        elif "centro de mando" in command or "mis agentes" in command:
            return self.abrir_centro_de_mando()

        # YouTube
        elif "youtube" in command:
            webbrowser.open("https://www.youtube.com")
            return "Abriendo YouTube."

        else:
            return "Lo siento, todavía no conozco ese comando."

    _centro_iniciado = False

    def abrir_centro_de_mando(self):
        """Arranca el Centro de Mando (si no está corriendo) y lo abre."""

        puerto = os.getenv("CENTRO_PUERTO", "8765")

        if not CommandManager._centro_iniciado:
            CommandManager._centro_iniciado = True

            def correr():
                from app.centro.server import iniciar
                try:
                    iniciar()
                except OSError:
                    # Ya estaba corriendo (por ejemplo con centro_mando.bat)
                    pass

            threading.Thread(target=correr, daemon=True).start()
            threading.Timer(
                1.0, webbrowser.open, args=(f"http://localhost:{puerto}",)
            ).start()
        else:
            webbrowser.open(f"http://localhost:{puerto}")

        return "Abriendo el Centro de Mando de sus agentes."

    def send_whatsapp(self, command):

        if not self.whatsapp.is_configured():
            return "WhatsApp no está configurado en el archivo .env."

        lower = command.lower()

        if "diciendo" not in lower:
            return (
                "Dígame el mensaje, por ejemplo: "
                "envía un WhatsApp diciendo llego en diez minutos."
            )

        mensaje = command[lower.index("diciendo") + len("diciendo"):].strip()

        if not mensaje:
            return "No escuché el mensaje que desea enviar."

        try:
            self.whatsapp.send_text(mensaje)
        except WhatsAppError as e:
            print("WhatsApp:", e)
            return "No pude enviar el mensaje de WhatsApp."

        return "Mensaje de WhatsApp enviado."
