"""
Servidor web del Centro de Mando de YAELCORE-OS.

Sin dependencias externas (solo la librería estándar de Python).
Se ejecuta en la computadora de Yael y el equipo entra desde su
navegador en la misma red: http://<ip-de-la-pc>:8765
"""

import hmac
from datetime import datetime
import time
import json
import mimetypes
import os
import re
import secrets
import socket
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from app.centro.db import (
    Almacen, ESTADOS_TAREA, PRIORIDADES, RECURRENCIAS, TIPOS_CONOCIMIENTO,
)
from app.centro.ia import CopilotoIA, ACCIONES


CARPETA_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
AREAS = ("frente", "front", "back", "interfaz", "nucleo", "mkt")
MAX_CUERPO = 2 * 1024 * 1024


class ErrorAPI(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def _pin_de(nombre):
    """PIN de acceso de un miembro, definido en .env (CENTRO_PIN_YAEL=...)."""
    clave = "CENTRO_PIN_" + re.sub(r"[^A-Z0-9]", "_", nombre.upper())
    return os.getenv(clave, "")


class CentroDeMando:
    """Lógica de la API, separada del transporte HTTP para poder probarla."""

    def __init__(self, almacen=None, copiloto=None):
        self.db = almacen or Almacen()
        self.ia = copiloto or CopilotoIA()
        self.sesiones = {}
        self.fallos = {}

    # ------------------------------------------------------------------
    # Sesión y permisos
    # ------------------------------------------------------------------

    def login(self, datos):
        miembro = self.db.miembro_por_nombre(str(datos.get("nombre", "")).strip())
        if not miembro:
            raise ErrorAPI(401, "Ese integrante no existe.")
        clave = miembro["nombre"].lower()
        ahora_ = time.monotonic()
        recientes = [t for t in self.fallos.get(clave, []) if ahora_ - t < 600]
        if len(recientes) >= 5:
            raise ErrorAPI(429, "Demasiados intentos. Espera 10 minutos.")
        esperado = _pin_de(miembro["nombre"])
        if esperado and not hmac.compare_digest(str(datos.get("pin", "")), esperado):
            self.fallos[clave] = recientes + [ahora_]
            raise ErrorAPI(401, "PIN incorrecto.")
        self.fallos.pop(clave, None)
        token = secrets.token_urlsafe(32)
        self.sesiones[token] = miembro["id"]
        self.db.registrar(miembro["id"], f"{miembro['nombre']} entró al Centro de Mando.")
        return token, miembro

    def usuario(self, token):
        miembro_id = self.sesiones.get(token or "")
        return self.db.miembro(miembro_id) if miembro_id else None

    @staticmethod
    def _es_jefe(yo):
        return yo["rol"] == "jefe"

    def _puede_operar(self, yo, agente):
        return self._es_jefe(yo) or agente["operador_id"] == yo["id"]

    def _puede_ver_tarea(self, yo, tarea):
        # Privacidad: el jefe ve todo; cada integrante ve solo las tareas de
        # sus propios agentes y las que él mismo creó.
        return (self._es_jefe(yo) or tarea["operador_id"] == yo["id"]
                or tarea["creador_id"] == yo["id"])

    def tareas(self, yo, agente_id=None):
        return [t for t in self.db.tareas(agente_id) if self._puede_ver_tarea(yo, t)]

    def _agente_o_404(self, agente_id):
        agente = self.db.agente(agente_id)
        if not agente:
            raise ErrorAPI(404, "Agente no encontrado.")
        return agente

    def _exigir_jefe(self, yo):
        if not self._es_jefe(yo):
            raise ErrorAPI(403, "Solo el jefe puede hacer esto.")

    def _exigir_operador(self, yo, agente):
        if not self._puede_operar(yo, agente):
            raise ErrorAPI(403, f"Solo {agente['operador'] or 'su operador'} o el jefe pueden modificar este agente.")

    # ------------------------------------------------------------------
    # Lecturas
    # ------------------------------------------------------------------

    def _resumen_propio(self, yo):
        hoy = datetime.now().date().isoformat()
        mias = self.tareas(yo)
        abiertas = [t for t in mias if t["estado"] != "hecho"]
        base = self.db.resumen()
        base.update({
            "abiertas": len(abiertas),
            "hechas": len(mias) - len(abiertas),
            "vencidas": sum(1 for t in abiertas if t["fecha_limite"] and t["fecha_limite"] < hoy),
            "automatizables": sum(1 for t in abiertas if t["automatizable"]),
            "recurrentes": sum(1 for t in abiertas if t["recurrencia"] != "ninguna"),
        })
        return base

    def estado(self, yo):
        jefe = self._es_jefe(yo)
        return {
            "yo": yo,
            "miembros": self.db.miembros(),
            "agentes": self.db.agentes(),
            "resumen": self.db.resumen() if jefe else self._resumen_propio(yo),
            "actividad": self.db.actividad() if jefe else
                         [x for x in self.db.actividad(200) if x["autor_id"] == yo["id"]][:40],
            "ia": self.ia.disponibles(),
            "catalogos": {
                "estados": ESTADOS_TAREA, "prioridades": PRIORIDADES,
                "recurrencias": RECURRENCIAS, "tipos": TIPOS_CONOCIMIENTO,
                "areas": AREAS, "acciones_ia": list(ACCIONES),
            },
        }

    def detalle_agente(self, yo, agente_id):
        agente = self._agente_o_404(agente_id)
        propio = self._puede_operar(yo, agente)
        return {
            "agente": agente,
            "puede_operar": propio,
            "tareas": self.tareas(yo, agente_id),
            "conocimiento": self.db.conocimiento(agente_id),
            "mensajes": self.db.mensajes(agente_id) if propio else [],
        }

    # ------------------------------------------------------------------
    # Miembros y agentes
    # ------------------------------------------------------------------

    def crear_miembro(self, yo, d):
        self._exigir_jefe(yo)
        nombre = _texto(d, "nombre", obligatorio=True, maximo=40)
        if self.db.miembro_por_nombre(nombre):
            raise ErrorAPI(400, "Ya existe un integrante con ese nombre.")
        m = self.db.crear_miembro(nombre, _texto(d, "puesto", maximo=60),
                                  _color(d.get("color")))
        self.db.registrar(yo["id"], f"Nuevo integrante: {nombre}.")
        return m

    def crear_agente(self, yo, d):
        self._exigir_jefe(yo)
        operador = self.db.miembro(_entero(d.get("operador_id")))
        if not operador:
            raise ErrorAPI(400, "Elige quién va a controlar al agente.")
        agente = self.db.crear_agente(
            _texto(d, "nombre", obligatorio=True, maximo=60),
            _opcion(d.get("area"), AREAS, "nucleo"),
            operador["id"],
            _texto(d, "mision", maximo=2000),
        )
        self.db.registrar(yo["id"], f"Creó el agente {agente['nombre']} (lo controla {operador['nombre']}).")
        return agente

    def actualizar_agente(self, yo, agente_id, d):
        agente = self._agente_o_404(agente_id)
        self._exigir_operador(yo, agente)
        cambios = {}
        if "mision" in d:
            cambios["mision"] = _texto(d, "mision", maximo=2000)
        if "estado" in d:
            cambios["estado"] = _opcion(d["estado"], ("activo", "pausado"), "activo")
        if self._es_jefe(yo):
            if "nombre" in d:
                cambios["nombre"] = _texto(d, "nombre", obligatorio=True, maximo=60)
            if "area" in d:
                cambios["area"] = _opcion(d["area"], AREAS, agente["area"])
            if "operador_id" in d:
                if not self.db.miembro(_entero(d["operador_id"])):
                    raise ErrorAPI(400, "Operador no válido.")
                cambios["operador_id"] = _entero(d["operador_id"])
        nuevo = self.db.actualizar_agente(agente_id, **cambios)
        self.db.registrar(yo["id"], f"Actualizó el agente {nuevo['nombre']}.")
        return nuevo

    def borrar_agente(self, yo, agente_id):
        self._exigir_jefe(yo)
        agente = self._agente_o_404(agente_id)
        self.db.borrar_agente(agente_id)
        self.db.registrar(yo["id"], f"Eliminó el agente {agente['nombre']}.")
        return {"ok": True}

    # ------------------------------------------------------------------
    # Conocimiento
    # ------------------------------------------------------------------

    def crear_ficha(self, yo, d):
        agente_id = d.get("agente_id")
        if agente_id in (None, "", "todos"):
            # Información general para TODOS los agentes: solo el jefe.
            self._exigir_jefe(yo)
            agente_id, destino = None, "todos los agentes"
        else:
            agente = self._agente_o_404(_entero(agente_id))
            agente_id, destino = agente["id"], agente["nombre"]
        ficha = self.db.crear_ficha(
            agente_id, yo["id"],
            _opcion(d.get("tipo"), TIPOS_CONOCIMIENTO, "contexto"),
            _texto(d, "titulo", obligatorio=True, maximo=120),
            _texto(d, "contenido", maximo=20000),
        )
        self.db.registrar(yo["id"], f"Pasó información a {destino}: «{ficha['titulo']}».")
        return ficha

    def borrar_ficha(self, yo, ficha_id):
        ficha = self.db.ficha(ficha_id)
        if not ficha:
            raise ErrorAPI(404, "Ficha no encontrada.")
        if not (self._es_jefe(yo) or ficha["autor_id"] == yo["id"]):
            raise ErrorAPI(403, "Solo el autor o el jefe pueden borrarla.")
        self.db.borrar_ficha(ficha_id)
        return {"ok": True}

    # ------------------------------------------------------------------
    # Tareas
    # ------------------------------------------------------------------

    def crear_tarea(self, yo, d):
        # Cualquiera puede pasarle trabajo a cualquier agente: así el
        # equipo se coordina como en el diagrama.
        agente = self._agente_o_404(_entero(d.get("agente_id")))
        tarea = self.db.crear_tarea(
            agente["id"], yo["id"],
            _texto(d, "titulo", obligatorio=True, maximo=160),
            _texto(d, "detalle", maximo=10000),
            _opcion(d.get("prioridad"), PRIORIDADES, "media"),
            _fecha(d.get("fecha_limite")),
            bool(d.get("automatizable")),
            _opcion(d.get("recurrencia"), RECURRENCIAS, "ninguna"),
        )
        self.db.registrar(yo["id"], f"Asignó a {agente['nombre']}: «{tarea['titulo']}».")
        return tarea

    def actualizar_tarea(self, yo, tarea_id, d):
        tarea = self.db.tarea(tarea_id)
        if not tarea or not self._puede_ver_tarea(yo, tarea):
            raise ErrorAPI(404, "Tarea no encontrada.")
        agente = self._agente_o_404(tarea["agente_id"])
        if not (self._puede_operar(yo, agente) or tarea["creador_id"] == yo["id"]):
            raise ErrorAPI(403, "Solo el operador del agente, quien la creó o el jefe pueden cambiarla.")

        cambios = {}
        for campo, maximo in (("titulo", 160), ("detalle", 10000), ("resultado", 10000)):
            if campo in d:
                cambios[campo] = _texto(d, campo, obligatorio=(campo == "titulo"), maximo=maximo)
        if "estado" in d:
            cambios["estado"] = _opcion(d["estado"], ESTADOS_TAREA, tarea["estado"])
        if "prioridad" in d:
            cambios["prioridad"] = _opcion(d["prioridad"], PRIORIDADES, tarea["prioridad"])
        if "recurrencia" in d:
            cambios["recurrencia"] = _opcion(d["recurrencia"], RECURRENCIAS, tarea["recurrencia"])
        if "fecha_limite" in d:
            cambios["fecha_limite"] = _fecha(d["fecha_limite"])
        if "automatizable" in d:
            cambios["automatizable"] = bool(d["automatizable"])
        if "agente_id" in d and self._es_jefe(yo):
            cambios["agente_id"] = self._agente_o_404(_entero(d["agente_id"]))["id"]

        nueva_tarea, siguiente = self.db.actualizar_tarea(tarea_id, **cambios)
        if "estado" in cambios and cambios["estado"] != tarea["estado"]:
            self.db.registrar(
                yo["id"],
                f"«{nueva_tarea['titulo']}» pasó a {cambios['estado'].replace('_', ' ')}.",
            )
        if siguiente:
            self.db.registrar(
                yo["id"],
                f"Automatización: se programó de nuevo «{siguiente['titulo']}» para {siguiente['fecha_limite']}.",
            )
        return {"tarea": nueva_tarea, "siguiente": siguiente}

    def borrar_tarea(self, yo, tarea_id):
        tarea = self.db.tarea(tarea_id)
        if not tarea or not self._puede_ver_tarea(yo, tarea):
            raise ErrorAPI(404, "Tarea no encontrada.")
        if not (self._es_jefe(yo) or tarea["creador_id"] == yo["id"]):
            raise ErrorAPI(403, "Solo quien la creó o el jefe pueden borrarla.")
        self.db.borrar_tarea(tarea_id)
        return {"ok": True}

    # ------------------------------------------------------------------
    # Canal y copiloto IA
    # ------------------------------------------------------------------

    def enviar_mensaje(self, yo, agente_id, d):
        self._exigir_operador(yo, self._agente_o_404(agente_id))
        texto = _texto(d, "texto", obligatorio=True, maximo=5000)
        return self.db.crear_mensaje(agente_id, yo["id"], texto)

    def consultar_ia(self, yo, agente_id, d):
        agente = self._agente_o_404(agente_id)
        self._exigir_operador(yo, agente)
        pregunta = _texto(d, "pregunta", obligatorio=True, maximo=5000)
        historial = self.db.mensajes(agente_id, limite=20)
        if pregunta not in ACCIONES:
            self.db.crear_mensaje(agente_id, yo["id"], pregunta)
        else:
            self.db.crear_mensaje(agente_id, yo["id"], "⚡ " + ACCIONES[pregunta])
        try:
            nombre_ia, respuesta = self.ia.preguntar(
                agente, self.db.conocimiento(agente_id), self.db.tareas(agente_id),
                historial, pregunta,
            )
        except RuntimeError as error:
            raise ErrorAPI(503, str(error))
        return self.db.crear_mensaje(agente_id, None, f"[{nombre_ia}] {respuesta}", es_ia=True)


# ----------------------------------------------------------------------
# Validación
# ----------------------------------------------------------------------

def _texto(d, campo, obligatorio=False, maximo=500):
    valor = str(d.get(campo) or "").strip()
    if obligatorio and not valor:
        raise ErrorAPI(400, f"Falta el campo «{campo}».")
    return valor[:maximo]


def _opcion(valor, opciones, defecto):
    return valor if valor in opciones else defecto


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ErrorAPI(400, "Identificador no válido.")


def _fecha(valor):
    valor = str(valor or "").strip()
    if not valor:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        raise ErrorAPI(400, "La fecha debe tener formato AAAA-MM-DD.")
    return valor


def _color(valor):
    valor = str(valor or "")
    return valor if re.fullmatch(r"#[0-9a-fA-F]{6}", valor) else "#4fb3bf"


# ----------------------------------------------------------------------
# Transporte HTTP
# ----------------------------------------------------------------------

RUTAS = [
    ("POST", r"/api/login", "login"),
    ("POST", r"/api/logout", "logout"),
    ("GET", r"/api/miembros-publico", "miembros_publico"),
    ("GET", r"/api/estado", "estado"),
    ("POST", r"/api/miembros", "crear_miembro"),
    ("POST", r"/api/agentes", "crear_agente"),
    ("GET", r"/api/agentes/(\d+)", "detalle_agente"),
    ("PATCH", r"/api/agentes/(\d+)", "actualizar_agente"),
    ("DELETE", r"/api/agentes/(\d+)", "borrar_agente"),
    ("POST", r"/api/agentes/(\d+)/mensajes", "enviar_mensaje"),
    ("POST", r"/api/agentes/(\d+)/ia", "consultar_ia"),
    ("POST", r"/api/conocimiento", "crear_ficha"),
    ("DELETE", r"/api/conocimiento/(\d+)", "borrar_ficha"),
    ("GET", r"/api/tareas", "tareas"),
    ("POST", r"/api/tareas", "crear_tarea"),
    ("PATCH", r"/api/tareas/(\d+)", "actualizar_tarea"),
    ("DELETE", r"/api/tareas/(\d+)", "borrar_tarea"),
]


def crear_manejador(centro):

    class Manejador(BaseHTTPRequestHandler):

        server_version = "YaelcoreCentro/1.0"

        def log_message(self, formato, *args):
            if os.getenv("CENTRO_LOG"):
                super().log_message(formato, *args)

        # -------------------- respuestas --------------------

        def _json(self, codigo, datos, extra_headers=None):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra_headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(cuerpo)

        def _archivo(self, ruta):
            nombre = "index.html" if ruta in ("", "/") else ruta.lstrip("/")
            if nombre.startswith("static/"):
                nombre = nombre[len("static/"):]
            completo = os.path.realpath(os.path.join(CARPETA_STATIC, nombre))
            if not completo.startswith(os.path.realpath(CARPETA_STATIC) + os.sep) \
                    or not os.path.isfile(completo):
                completo = os.path.join(CARPETA_STATIC, "index.html")
            with open(completo, "rb") as f:
                cuerpo = f.read()
            tipo = mimetypes.guess_type(completo)[0] or "application/octet-stream"
            if tipo.startswith("text/") or tipo.endswith("javascript"):
                tipo += "; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(cuerpo)

        def _token(self):
            galleta = cookies.SimpleCookie(self.headers.get("Cookie", ""))
            return galleta["centro"].value if "centro" in galleta else None

        def _cuerpo(self):
            largo = int(self.headers.get("Content-Length") or 0)
            if largo > MAX_CUERPO:
                raise ErrorAPI(413, "La información es demasiado grande.")
            if not largo:
                return {}
            try:
                datos = json.loads(self.rfile.read(largo).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise ErrorAPI(400, "JSON no válido.")
            if not isinstance(datos, dict):
                raise ErrorAPI(400, "Se esperaba un objeto JSON.")
            return datos

        # -------------------- enrutamiento --------------------

        def _despachar(self, metodo):
            ruta = urlparse(self.path).path
            if not ruta.startswith("/api/"):
                if metodo == "GET":
                    return self._archivo(ruta)
                return self._json(405, {"error": "Método no permitido."})

            for m, patron, accion in RUTAS:
                encontrado = re.fullmatch(patron, ruta)
                if m == metodo and encontrado:
                    break
            else:
                return self._json(404, {"error": "Ruta no encontrada."})

            args = [int(g) for g in encontrado.groups()]
            try:
                datos = self._cuerpo() if metodo in ("POST", "PATCH") else {}

                if accion == "login":
                    token, miembro = centro.login(datos)
                    return self._json(200, miembro, {
                        "Set-Cookie": f"centro={token}; Path=/; HttpOnly; SameSite=Strict",
                    })
                if accion == "miembros_publico":
                    return self._json(200, [
                        {"nombre": m["nombre"], "color": m["color"], "puesto": m["puesto"],
                         "requiere_pin": bool(_pin_de(m["nombre"]))}
                        for m in centro.db.miembros()
                    ])

                yo = centro.usuario(self._token())
                if not yo:
                    raise ErrorAPI(401, "Inicia sesión.")

                if accion == "logout":
                    centro.sesiones.pop(self._token(), None)
                    return self._json(200, {"ok": True}, {
                        "Set-Cookie": "centro=; Path=/; Max-Age=0",
                    })
                if accion == "tareas":
                    return self._json(200, centro.tareas(yo))

                funcion = getattr(centro, accion)
                if metodo in ("POST", "PATCH"):
                    resultado = funcion(yo, *args, datos)
                else:
                    resultado = funcion(yo, *args)
                return self._json(200, resultado)
            except ErrorAPI as error:
                return self._json(error.codigo, {"error": error.mensaje})
            except Exception as error:  # pragma: no cover - red de seguridad
                print(f"ERROR - Centro de Mando: {error!r}")
                return self._json(500, {"error": "Error interno del Centro de Mando."})

        def do_GET(self):
            self._despachar("GET")

        def do_POST(self):
            self._despachar("POST")

        def do_PATCH(self):
            self._despachar("PATCH")

        def do_DELETE(self):
            self._despachar("DELETE")

    return Manejador


def ip_local():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def iniciar(host=None, puerto=None, abrir_navegador=False):
    host = host or os.getenv("CENTRO_HOST", "0.0.0.0")
    puerto = int(puerto or os.getenv("CENTRO_PUERTO", "8765"))

    centro = CentroDeMando()
    servidor = ThreadingHTTPServer((host, puerto), crear_manejador(centro))

    url_local = f"http://localhost:{puerto}"
    print("=" * 56)
    print(" YAELCORE-OS · CENTRO DE MANDO")
    print("=" * 56)
    print(f" En esta PC:        {url_local}")
    if host == "0.0.0.0":
        print(f" Para tu equipo:    http://{ip_local()}:{puerto}")
    sin_pin = [m["nombre"] for m in centro.db.miembros() if not _pin_de(m["nombre"])]
    if sin_pin:
        print(" AVISO: sin PIN ->", ", ".join(sin_pin),
              "(define CENTRO_PIN_<NOMBRE> en .env)")
    ias = centro.ia.disponibles()
    print(" IA conectada:     ", " y ".join(ias) if ias else "ninguna (revisa .env)")
    print("=" * 56)

    if abrir_navegador:
        import webbrowser
        webbrowser.open(url_local)

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nCentro de Mando detenido.")
    finally:
        servidor.server_close()
