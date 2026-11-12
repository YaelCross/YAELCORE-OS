"""
Copiloto de IA para cada agente del Centro de Mando.

Usa las mismas inteligencias de YAELCORE-OS (Claude y ChatGPT). Antes de
responder, le da a la IA todo lo que el equipo le ha pasado al agente:
su misión, su base de conocimiento y sus tareas abiertas. Así cada
persona que controla un agente recibe ayuda con el contexto completo.
"""

INSTRUCCIONES = (
    "Eres {agente}, un agente de trabajo dentro de YAELCORE-OS, el sistema "
    "de la empresa de Yael. Te controla una persona real: {operador}. "
    "Tu área es: {area}. Tu misión: {mision}\n\n"
    "Hablas siempre en español, de forma clara, práctica y directa. "
    "Usa SOLO la información que el equipo te ha pasado y dilo cuando "
    "te falte información. Cuando veas trabajo repetitivo, propón cómo "
    "automatizarlo (pasos concretos, herramientas y frecuencia).\n\n"
    "=== BASE DE CONOCIMIENTO ===\n{conocimiento}\n\n"
    "=== TAREAS ABIERTAS ===\n{tareas}"
)

ACCIONES = {
    "siguiente": (
        "Revisa mis tareas abiertas y dime en qué orden atacarlas hoy y "
        "por qué. Máximo 6 puntos."
    ),
    "automatizar": (
        "Analiza mis tareas y conocimiento. ¿Qué se puede automatizar? "
        "Para cada idea da: tarea, cómo automatizarla, herramienta sugerida "
        "y tiempo que ahorraría."
    ),
    "resumen": (
        "Haz un resumen ejecutivo para el jefe Yael: avances, bloqueos, "
        "riesgos y qué información me falta para crecer."
    ),
    "faltante": (
        "¿Qué información o documentos me hacen falta para hacer mejor "
        "mi trabajo? Haz una lista de preguntas concretas para Yael."
    ),
}


def _formatear_conocimiento(fichas):
    if not fichas:
        return "(Todavía no hay información. Pídela al equipo.)"
    lineas = []
    for f in fichas[:40]:
        alcance = "GENERAL" if f.get("agente_id") is None else f["tipo"].upper()
        lineas.append(f"- [{alcance}] {f['titulo']}: {f['contenido'][:1200]}")
    return "\n".join(lineas)


def _formatear_tareas(tareas):
    abiertas = [t for t in tareas if t["estado"] != "hecho"]
    if not abiertas:
        return "(Sin tareas abiertas.)"
    lineas = []
    for t in abiertas[:30]:
        extra = []
        if t.get("fecha_limite"):
            extra.append(f"vence {t['fecha_limite']}")
        if t.get("recurrencia") and t["recurrencia"] != "ninguna":
            extra.append(f"se repite {t['recurrencia']}")
        if t.get("automatizable"):
            extra.append("automatizable")
        info = f" ({', '.join(extra)})" if extra else ""
        lineas.append(
            f"- #{t['id']} [{t['estado']}/{t['prioridad']}] {t['titulo']}{info}"
            + (f" — {t['detalle'][:300]}" if t.get("detalle") else "")
        )
    return "\n".join(lineas)


class CopilotoIA:

    def __init__(self):
        self._ias = None

    def _cargar(self):
        if self._ias is not None:
            return self._ias
        self._ias = []
        # Importación perezosa: el Centro de Mando funciona aunque no
        # estén instaladas las librerías de IA o no haya claves.
        try:
            from app.ai.claude_assistant import ClaudeAssistant
            self._ias.append(ClaudeAssistant())
        except Exception as error:
            print(f"AVISO - Claude no disponible en el Centro de Mando: {error}")
        try:
            from app.ai.assistant import Assistant
            self._ias.append(Assistant())
        except Exception as error:
            print(f"AVISO - ChatGPT no disponible en el Centro de Mando: {error}")
        return self._ias

    def disponibles(self):
        return [ia.nombre for ia in self._cargar()]

    def preguntar(self, agente, fichas, tareas, historial, pregunta):
        ias = self._cargar()
        if not ias:
            raise RuntimeError(
                "No hay IA conectada. Agrega ANTHROPIC_API_KEY u "
                "OPENAI_API_KEY en el archivo .env"
            )

        instrucciones = INSTRUCCIONES.format(
            agente=agente["nombre"],
            operador=agente.get("operador") or "sin asignar",
            area=agente["area"],
            mision=agente["mision"] or "(sin misión definida)",
            conocimiento=_formatear_conocimiento(fichas),
            tareas=_formatear_tareas(tareas),
        )

        pregunta = ACCIONES.get(pregunta, pregunta)
        memoria = []
        for m in historial[-10:]:
            rol = "assistant" if m["es_ia"] else "user"
            texto = m["texto"] if m["es_ia"] else f"{m.get('autor') or 'Equipo'}: {m['texto']}"
            if memoria and memoria[-1]["role"] == rol:
                memoria[-1]["content"] += "\n" + texto
            else:
                memoria.append({"role": rol, "content": texto})
        # Las APIs esperan que la conversación empiece con el usuario.
        while memoria and memoria[0]["role"] != "user":
            memoria.pop(0)
        if memoria and memoria[-1]["role"] == "user":
            pregunta = memoria.pop()["content"] + "\n" + pregunta

        ultimo_error = None
        for ia in ias:
            try:
                return ia.nombre, ia.ask(pregunta, instrucciones, memoria)
            except Exception as error:
                print(f"ERROR - {ia.nombre}: {error}")
                ultimo_error = error
        raise RuntimeError(f"La IA no pudo responder: {ultimo_error}")
