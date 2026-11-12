import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path


def configurar_registro():
    """
    Cuando YAELCORE-OS arranca sin consola (pythonw, inicio automático),
    los mensajes y errores se pierden. Aquí se guardan en
    logs/yaelcore.log para poder ver qué pasó.
    """

    if sys.stdout is not None and sys.stderr is not None:
        return

    carpeta_logs = Path(__file__).resolve().parent / "logs"
    carpeta_logs.mkdir(exist_ok=True)

    archivo = open(
        carpeta_logs / "yaelcore.log",
        "a",
        encoding="utf-8",
        buffering=1
    )

    sys.stdout = archivo
    sys.stderr = archivo

    def registrar_error(tipo, valor, rastro):
        print("ERROR NO CONTROLADO:")
        traceback.print_exception(tipo, valor, rastro)

    def registrar_error_hilo(args):
        registrar_error(
            args.exc_type,
            args.exc_value,
            args.exc_traceback
        )

    sys.excepthook = registrar_error
    threading.excepthook = registrar_error_hilo

    print()
    print(f"===== Inicio de YAELCORE-OS: {datetime.now():%Y-%m-%d %H:%M:%S} =====")


configurar_registro()

from app.core.jarvis import Jarvis
from app.ui.splash import JarvisSplash
from app.ui.core_ui import JarvisCoreUI


def start_jarvis():

    jarvis = Jarvis()

    ui = JarvisCoreUI(
        jarvis
    )

    # Conectar el sistema de voz de JARVIS
    # con la interfaz principal.
    

    def run_jarvis():

        jarvis.start()

    threading.Thread(
        target=run_jarvis,
        daemon=True
    ).start()

    ui.show()


def start_system():

    splash = JarvisSplash(
        on_complete=start_jarvis
    )

    splash.show()


if __name__ == "__main__":

    start_system()