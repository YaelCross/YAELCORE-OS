"""
YAELCORE-OS · Motor de automatización del Centro de Mando

Corre en segundo plano mientras el Centro de Mando está encendido:

1. Tareas automatizables: a su hora (el "HH:MM" al inicio del título) el
   agente las trabaja con IA (Claude y, si falla, ChatGPT), deja el
   resultado en la tarea y la pasa a "Revisión" para que una persona la
   apruebe. Nunca la marca como "Hecho" por su cuenta.
2. Tareas recurrentes: cada día renueva las diarias que no se cerraron,
   para que el tablero amanezca con los pendientes del día.
3. Resumen diario: a la hora indicada deja en el chat del agente del
   jefe un resumen con números reales del tablero (sin IA, siempre funciona).

La IA no tiene acceso a sistemas externos (Meta Ads, Mercado Libre, redes):
prepara borradores, checklists y análisis con la información que el equipo
cargó en el Centro de Mando, y dice qué datos le faltan. No inventa cifras.
"""

import os
import re
import threading
import time
from datetime import date, datetime, timedelta

ESQUEMA = """
CREATE TABLE IF NOT EXISTS automatizaciones (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    tarea_id  INTEGER,
    tipo      TEXT NOT NULL,
    dia       TEXT NOT NULL,
    proveedor TEXT,
    ok        INTEGER NOT NULL,
    detalle   TEXT,
    creado    TEXT NOT NULL
);
"""

INSTRUCCION_AUTOMATICA = """Ejecuta ahora esta tarea programada: «{titulo}».
Detalle: {detalle}

Reglas:
- No tienes acceso directo a sistemas externos. Si abajo vienen "DATOS REALES",
  úsalos; si no vienen, NO inventes cifras, resultados ni datos.
- Trabaja solo con esos datos, tu conocimiento y las tareas.
- Entrega, en español y en máximo 20 líneas:
  1. Lo que ya dejas preparado (checklist, borrador, mensaje o análisis).
  2. Qué datos faltan para completarla y de dónde sacarlos.
  Con datos de campañas: resumen por cuenta, alertas priorizadas y 3 acciones
  recomendadas (sin ejecutarlas).
  3. El siguiente paso concreto para la persona responsable.
"""

HORA_TITULO = re.compile(r"^\s*(\d{1,2}):(\d{2})")
MAX_INTENTOS_DIA = 3
ESPERA_REINTENTO = timedelta(minutes=15)


def _activo():
    return os.getenv("CENTRO_AUTOMATIZAR", "si").strip().lower() not in ("no", "0", "false")


def hora_de(titulo):
    m = HORA_TITULO.match(titulo or "")
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return (h, mi) if h < 24 and mi < 60 else None


class Automatizador(threading.Thread):

    def __init__(self, centro, intervalo=60):
        super().__init__(name="automatizador", daemon=True)
        self.centro = centro
        self.db = centro.db
        self.intervalo = intervalo
        self._parar = threading.Event()
        self._candado = threading.Lock()
        self.ultimo_ciclo = None
        self.ultima_ejecucion = None
        self.db._q(ESQUEMA.strip().rstrip(";"))

    # -------------------------------------------------------------- ciclo
    def run(self):
        while not self._parar.is_set():
            try:
                self.ciclo()
            except Exception as error:  # el motor nunca debe tumbar el servidor
                print(f"ERROR - Automatización: {error}")
            self._parar.wait(self.intervalo)

    def detener(self):
        self._parar.set()

    def ciclo(self, ahora=None):
        if not _activo():
            return
        with self._candado:
            ahora = ahora or datetime.now()
            self.ultimo_ciclo = ahora
            self._renovar_recurrentes(ahora)
            for tarea in self.db.tareas():
                if self._toca(tarea, ahora):
                    self._ejecutar(tarea, ahora)
            self._resumen_diario(ahora)

    # -------------------------------------------------------------- reglas
    def _registros(self, tipo, dia, tarea_id=None):
        sql = "SELECT * FROM automatizaciones WHERE tipo=? AND dia=?"
        params = [tipo, dia]
        if tarea_id is not None:
            sql += " AND tarea_id=?"
            params.append(tarea_id)
        return self.db._todos(sql + " ORDER BY id", params)

    def _anotar(self, tipo, dia, ok, tarea_id=None, proveedor=None, detalle="", cuando=None):
        self.db._q(
            "INSERT INTO automatizaciones (tarea_id, tipo, dia, proveedor, ok, detalle, creado) "
            "VALUES (?,?,?,?,?,?,?)",
            (tarea_id, tipo, dia, proveedor, int(ok), detalle[:500], (cuando or datetime.now()).isoformat(timespec="seconds")),
        )

    def _toca(self, tarea, ahora):
        if not tarea["automatizable"] or tarea["estado"] != "pendiente":
            return False
        hoy = ahora.date().isoformat()
        if tarea["fecha_limite"] and tarea["fecha_limite"] > hoy:
            return False  # aún no le toca (p. ej. comisiones del día 20)
        hm = hora_de(tarea["titulo"])
        if hm and (ahora.hour, ahora.minute) < hm:
            return False
        previos = self._registros("tarea", hoy, tarea["id"])
        if any(r["ok"] for r in previos) or len(previos) >= MAX_INTENTOS_DIA:
            return False
        if previos:
            ultimo = datetime.fromisoformat(previos[-1]["creado"])
            if ahora - ultimo < ESPERA_REINTENTO:
                return False
        return True

    def _ejecutar(self, tarea, ahora):
        hoy = ahora.date().isoformat()
        agente = self.db.agente(tarea["agente_id"])
        if not agente:
            return
        self.db.actualizar_tarea(tarea["id"], estado="en_curso")
        datos = ""
        from app.centro import meta_ads
        if meta_ads.es_tarea_de_campanas(tarea["titulo"]):
            datos = "\n\n" + meta_ads.reporte() + (
                "\n\nUsa SOLO estos datos para las cifras. Prioriza las alertas y "
                "recomienda acciones; no ejecutes cambios: los decide una persona.")
        try:
            proveedor, texto = self.centro.ia.preguntar(
                agente,
                self.db.conocimiento(agente["id"]),
                self.db.tareas(agente["id"]),
                [],
                INSTRUCCION_AUTOMATICA.format(titulo=tarea["titulo"], detalle=tarea["detalle"] or "(sin detalle)") + datos,
            )
        except Exception as error:
            self.db.actualizar_tarea(tarea["id"], estado="pendiente")
            self._anotar("tarea", hoy, False, tarea["id"], None, str(error), ahora)
            self.db.registrar(agente.get("operador_id"),
                              f"Automatización falló en «{tarea['titulo']}»: {str(error)[:120]}. Reintento en 15 min.")
            return

        sello = ahora.strftime("%d/%m %H:%M")
        resultado = f"[Automático · {proveedor} · {sello}]\n{texto.strip()}"
        self.db.actualizar_tarea(tarea["id"], estado="revision", resultado=resultado)
        self.db.crear_mensaje(agente["id"], None,
                              f"⚙️ Preparé «{tarea['titulo']}» y la dejé en Revisión.\n\n{texto.strip()}",
                              es_ia=True)
        self.db.registrar(agente.get("operador_id"),
                          f"Automatización: {agente['nombre']} preparó «{tarea['titulo']}» con {proveedor}")
        self._anotar("tarea", hoy, True, tarea["id"], proveedor, cuando=ahora)
        self.ultima_ejecucion = {"tarea": tarea["titulo"], "proveedor": proveedor, "hora": sello}

    def _renovar_recurrentes(self, ahora):
        """Una vez al día: las tareas diarias que quedaron abiertas de días
        anteriores se ponen con fecha de hoy y vuelven a Pendiente."""
        hoy = ahora.date().isoformat()
        if self._registros("renovar", hoy):
            return
        n = 0
        for t in self.db.tareas():
            if (t["recurrencia"] == "diaria" and t["estado"] != "hecho"
                    and (t["fecha_limite"] is None or t["fecha_limite"] < hoy)):
                cambios = {"fecha_limite": hoy}
                if t["estado"] == "revision" and t["automatizable"] and (t["resultado"] or "").startswith("[Automático"):
                    cambios["estado"] = "pendiente"  # el borrador de ayer ya no sirve
                self.db.actualizar_tarea(t["id"], **cambios)
                n += 1
        self._anotar("renovar", hoy, True, detalle=f"{n} tareas diarias renovadas")

    def _resumen_diario(self, ahora):
        hora = os.getenv("CENTRO_RESUMEN_HORA", "18:30")
        hm = hora_de(hora) or (18, 30)
        hoy = ahora.date().isoformat()
        if (ahora.hour, ahora.minute) < hm or self._registros("resumen", hoy):
            return
        jefe = next((m for m in self.db.miembros() if m["rol"] == "jefe"), None)
        if not jefe:
            return
        agente = next((a for a in self.db.agentes() if a["operador_id"] == jefe["id"]), None)
        tareas = self.db.tareas()
        hechas = [t for t in tareas if t["estado"] == "hecho" and (t["actualizado"] or "").startswith(hoy)]
        abiertas = [t for t in tareas if t["estado"] != "hecho"]
        vencidas = [t for t in abiertas if t["fecha_limite"] and t["fecha_limite"] < hoy]
        revision = [t for t in abiertas if t["estado"] == "revision"]
        autos = self._registros("tarea", hoy)
        por_persona = {}
        for t in abiertas:
            por_persona[t["agente"]] = por_persona.get(t["agente"], 0) + 1
        texto = (
            f"📊 Resumen del día {ahora.strftime('%d/%m/%Y')}\n"
            f"• Cerradas hoy: {len(hechas)}\n"
            f"• Abiertas: {len(abiertas)} (vencidas: {len(vencidas)})\n"
            f"• Esperando tu revisión: {len(revision)}\n"
            f"• Automatizaciones: {sum(1 for a in autos if a['ok'])} listas, {sum(1 for a in autos if not a['ok'])} con fallo\n"
            f"• Abiertas por agente: " + ", ".join(f"{k} {v}" for k, v in sorted(por_persona.items())) +
            ("\n\nRevisa primero:\n" + "\n".join(f"  – {t['titulo']}" for t in revision[:8]) if revision else "")
        )
        if agente:
            self.db.crear_mensaje(agente["id"], None, texto, es_ia=True)
        self.db.registrar(jefe["id"], "Resumen diario generado")
        self._anotar("resumen", hoy, True, detalle=texto[:500])

    # -------------------------------------------------------------- estado
    def estado(self):
        hoy = date.today().isoformat()
        autos = self._registros("tarea", hoy)
        return {
            "activo": _activo() and self.is_alive(),
            "ultimo_ciclo": self.ultimo_ciclo.isoformat(timespec="seconds") if self.ultimo_ciclo else None,
            "ultima_ejecucion": self.ultima_ejecucion,
            "hoy_ok": sum(1 for a in autos if a["ok"]),
            "hoy_fallos": sum(1 for a in autos if not a["ok"]),
            "resumen_hora": os.getenv("CENTRO_RESUMEN_HORA", "18:30"),
        }
