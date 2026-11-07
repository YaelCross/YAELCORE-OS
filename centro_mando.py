"""
YAELCORE-OS · Centro de Mando

Interfaz web donde el equipo (Yael, Frida, Efren, Nova…) trabaja con
sus agentes: les pasa información, asigna tareas, automatiza lo
repetitivo y consulta al copiloto de IA.

Uso:
    python centro_mando.py            -> abre el navegador en esta PC
    python centro_mando.py --sin-navegador
"""

import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.centro.server import iniciar


if __name__ == "__main__":
    iniciar(abrir_navegador="--sin-navegador" not in sys.argv)
