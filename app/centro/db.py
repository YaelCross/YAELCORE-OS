"""
Almacén del Centro de Mando (SQLite, sin dependencias externas).

Modelo:
  miembros     -> personas reales (jefe Yael, Frida, Efren, Nova...)
  agentes      -> agentes de IA; cada uno lo controla un miembro (operador)
  conocimiento -> información que se le pasa a un agente (o a todos)
  tareas       -> trabajo asignado a un agente, con estado y recurrencia
  mensajes     -> canal de comunicación de cada agente
  actividad    -> bitácora de lo que pasa en el sistema
"""

import os
import sqlite3
import threading
from datetime import datetime, timedelta


RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUTA_DB = os.getenv(
    "CENTRO_DB",
    os.path.join(RAIZ, "data", "centro_mando.db"),
)

ESTADOS_TAREA = ("pendiente", "en_curso", "revision", "hecho")
PRIORIDADES = ("baja", "media", "alta")
RECURRENCIAS = ("ninguna", "diaria", "semanal", "mensual")
TIPOS_CONOCIMIENTO = ("contexto", "instruccion", "dato", "recurso", "proceso")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS miembros (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT NOT NULL UNIQUE,
    rol     TEXT NOT NULL DEFAULT 'integrante',
    puesto  TEXT NOT NULL DEFAULT '',
    color   TEXT NOT NULL DEFAULT '#4fb3bf'
);

CREATE TABLE IF NOT EXISTS agentes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    area        TEXT NOT NULL DEFAULT 'nucleo',
    operador_id INTEGER REFERENCES miembros(id),
    mision      TEXT NOT NULL DEFAULT '',
    estado      TEXT NOT NULL DEFAULT 'activo',
    creado      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conocimiento (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    agente_id INTEGER REFERENCES agentes(id) ON DELETE CASCADE,
    autor_id  INTEGER REFERENCES miembros(id),
    tipo      TEXT NOT NULL DEFAULT 'contexto',
    titulo    TEXT NOT NULL,
    contenido TEXT NOT NULL DEFAULT '',
    creado    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tareas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    agente_id    INTEGER NOT NULL REFERENCES agentes(id) ON DELETE CASCADE,
    creador_id   INTEGER REFERENCES miembros(id),
    titulo       TEXT NOT NULL,
    detalle      TEXT NOT NULL DEFAULT '',
    estado       TEXT NOT NULL DEFAULT 'pendiente',
    prioridad    TEXT NOT NULL DEFAULT 'media',
    fecha_limite TEXT,
    automatizable INTEGER NOT NULL DEFAULT 0,
    recurrencia  TEXT NOT NULL DEFAULT 'ninguna',
    resultado    TEXT NOT NULL DEFAULT '',
    creado       TEXT NOT NULL,
    actualizado  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mensajes (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    agente_id INTEGER NOT NULL REFERENCES agentes(id) ON DELETE CASCADE,
    autor_id  INTEGER REFERENCES miembros(id),
    es_ia     INTEGER NOT NULL DEFAULT 0,
    texto     TEXT NOT NULL,
    creado    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actividad (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    autor_id INTEGER REFERENCES miembros(id),
    texto    TEXT NOT NULL,
    creado   TEXT NOT NULL
);
"""

# Equipo inicial, tal como aparece en el diagrama.
EQUIPO_INICIAL = [
    ("Yael", "jefe", "Jefe / Dirección", "#e05252"),
    ("Frida", "integrante", "Integrante MKT", "#d9913b"),
    ("Efren", "integrante", "Integrante MKT", "#b65fd6"),
    ("Nova", "integrante", "Integrante MKT", "#c9c35a"),
]

AGENTES_INICIALES = [
    ("Agente Frida", "front", "Frida",
     "Apoyar a Frida en su área: recibir información, organizar "
     "pendientes y proponer tareas que se puedan automatizar."),
    ("Agente Efren", "nucleo", "Efren",
     "Apoyar a Efren en su área: recibir información, organizar "
     "pendientes y proponer tareas que se puedan automatizar."),
    ("Agente Nova", "back", "Nova",
     "Apoyar a Nova en su área: recibir información, organizar "
     "pendientes y proponer tareas que se puedan automatizar."),
]


def ahora():
    return datetime.now().isoformat(timespec="seconds")


class Almacen:

    def __init__(self, ruta=RUTA_DB):
        self.ruta = ruta
        if ruta != ":memory:":
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
        self._lock = threading.Lock()
        self._con = sqlite3.connect(ruta, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.executescript(ESQUEMA)
        self._sembrar()

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _q(self, sql, params=()):
        with self._lock:
            cur = self._con.execute(sql, params)
            self._con.commit()
            return cur

    def _todos(self, sql, params=()):
        with self._lock:
            return [dict(r) for r in self._con.execute(sql, params).fetchall()]

    def _uno(self, sql, params=()):
        with self._lock:
            fila = self._con.execute(sql, params).fetchone()
            return dict(fila) if fila else None

    def _sembrar(self):
        if self._uno("SELECT id FROM miembros LIMIT 1"):
            return
        for nombre, rol, puesto, color in EQUIPO_INICIAL:
            self._q(
                "INSERT INTO miembros (nombre, rol, puesto, color) VALUES (?,?,?,?)",
                (nombre, rol, puesto, color),
            )
        for nombre, area, operador, mision in AGENTES_INICIALES:
            op = self.miembro_por_nombre(operador)
            self._q(
                "INSERT INTO agentes (nombre, area, operador_id, mision, creado) "
                "VALUES (?,?,?,?,?)",
                (nombre, area, op["id"], mision, ahora()),
            )
        self.registrar(None, "Centro de Mando inicializado con el equipo base.")

    # ------------------------------------------------------------------
    # Miembros
    # ------------------------------------------------------------------

    def miembros(self):
        return self._todos("SELECT * FROM miembros ORDER BY rol='jefe' DESC, nombre")

    def miembro(self, miembro_id):
        return self._uno("SELECT * FROM miembros WHERE id=?", (miembro_id,))

    def miembro_por_nombre(self, nombre):
        return self._uno(
            "SELECT * FROM miembros WHERE lower(nombre)=lower(?)", (nombre,)
        )

    def crear_miembro(self, nombre, puesto="", color="#4fb3bf", rol="integrante"):
        cur = self._q(
            "INSERT INTO miembros (nombre, rol, puesto, color) VALUES (?,?,?,?)",
            (nombre, rol, puesto, color),
        )
        return self.miembro(cur.lastrowid)

    # ------------------------------------------------------------------
    # Agentes
    # ------------------------------------------------------------------

    _SQL_AGENTE = """
        SELECT a.*, m.nombre AS operador, m.color AS color,
          (SELECT COUNT(*) FROM tareas t WHERE t.agente_id=a.id AND t.estado!='hecho') AS abiertas,
          (SELECT COUNT(*) FROM tareas t WHERE t.agente_id=a.id AND t.estado='hecho') AS hechas,
          (SELECT COUNT(*) FROM conocimiento c WHERE c.agente_id=a.id) AS fichas
        FROM agentes a LEFT JOIN miembros m ON m.id=a.operador_id
    """

    def agentes(self):
        return self._todos(self._SQL_AGENTE + " ORDER BY a.id")

    def agente(self, agente_id):
        return self._uno(self._SQL_AGENTE + " WHERE a.id=?", (agente_id,))

    def crear_agente(self, nombre, area, operador_id, mision):
        cur = self._q(
            "INSERT INTO agentes (nombre, area, operador_id, mision, creado) "
            "VALUES (?,?,?,?,?)",
            (nombre, area, operador_id, mision, ahora()),
        )
        return self.agente(cur.lastrowid)

    def actualizar_agente(self, agente_id, **campos):
        permitidos = {"nombre", "area", "operador_id", "mision", "estado"}
        cambios = {k: v for k, v in campos.items() if k in permitidos}
        if cambios:
            sets = ", ".join(f"{k}=?" for k in cambios)
            self._q(
                f"UPDATE agentes SET {sets} WHERE id=?",
                (*cambios.values(), agente_id),
            )
        return self.agente(agente_id)

    def borrar_agente(self, agente_id):
        self._q("DELETE FROM agentes WHERE id=?", (agente_id,))

    # ------------------------------------------------------------------
    # Conocimiento
    # ------------------------------------------------------------------

    def conocimiento(self, agente_id=None, incluir_global=True):
        sql = (
            "SELECT c.*, m.nombre AS autor FROM conocimiento c "
            "LEFT JOIN miembros m ON m.id=c.autor_id "
        )
        if agente_id is None:
            return self._todos(sql + "ORDER BY c.id DESC")
        if incluir_global:
            return self._todos(
                sql + "WHERE c.agente_id=? OR c.agente_id IS NULL ORDER BY c.id DESC",
                (agente_id,),
            )
        return self._todos(sql + "WHERE c.agente_id=? ORDER BY c.id DESC", (agente_id,))

    def ficha(self, ficha_id):
        return self._uno("SELECT * FROM conocimiento WHERE id=?", (ficha_id,))

    def crear_ficha(self, agente_id, autor_id, tipo, titulo, contenido):
        cur = self._q(
            "INSERT INTO conocimiento (agente_id, autor_id, tipo, titulo, contenido, creado) "
            "VALUES (?,?,?,?,?,?)",
            (agente_id, autor_id, tipo, titulo, contenido, ahora()),
        )
        return self.ficha(cur.lastrowid)

    def borrar_ficha(self, ficha_id):
        self._q("DELETE FROM conocimiento WHERE id=?", (ficha_id,))

    # ------------------------------------------------------------------
    # Tareas
    # ------------------------------------------------------------------

    _SQL_TAREA = """
        SELECT t.*, a.nombre AS agente, a.operador_id AS operador_id,
               m.nombre AS creador
        FROM tareas t
        JOIN agentes a ON a.id=t.agente_id
        LEFT JOIN miembros m ON m.id=t.creador_id
    """

    def tareas(self, agente_id=None):
        orden = (
            " ORDER BY CASE t.prioridad WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END,"
            " COALESCE(t.fecha_limite, '9999'), t.id DESC"
        )
        if agente_id is None:
            return self._todos(self._SQL_TAREA + orden)
        return self._todos(self._SQL_TAREA + " WHERE t.agente_id=?" + orden, (agente_id,))

    def tarea(self, tarea_id):
        return self._uno(self._SQL_TAREA + " WHERE t.id=?", (tarea_id,))

    def crear_tarea(self, agente_id, creador_id, titulo, detalle="",
                    prioridad="media", fecha_limite=None,
                    automatizable=False, recurrencia="ninguna"):
        cur = self._q(
            "INSERT INTO tareas (agente_id, creador_id, titulo, detalle, prioridad, "
            "fecha_limite, automatizable, recurrencia, creado, actualizado) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (agente_id, creador_id, titulo, detalle, prioridad,
             fecha_limite or None, int(bool(automatizable)), recurrencia,
             ahora(), ahora()),
        )
        return self.tarea(cur.lastrowid)

    def actualizar_tarea(self, tarea_id, **campos):
        """Actualiza una tarea. Si una tarea recurrente pasa a 'hecho',
        se programa automáticamente la siguiente. Devuelve (tarea, nueva)."""

        antes = self.tarea(tarea_id)
        if not antes:
            return None, None

        permitidos = {"titulo", "detalle", "estado", "prioridad", "fecha_limite",
                      "automatizable", "recurrencia", "resultado", "agente_id"}
        cambios = {k: v for k, v in campos.items() if k in permitidos}
        if "automatizable" in cambios:
            cambios["automatizable"] = int(bool(cambios["automatizable"]))
        if cambios:
            cambios["actualizado"] = ahora()
            sets = ", ".join(f"{k}=?" for k in cambios)
            self._q(f"UPDATE tareas SET {sets} WHERE id=?", (*cambios.values(), tarea_id))

        despues = self.tarea(tarea_id)
        nueva = None
        if (antes["estado"] != "hecho" and despues["estado"] == "hecho"
                and despues["recurrencia"] != "ninguna"):
            nueva = self._programar_siguiente(despues)
        return despues, nueva

    def _programar_siguiente(self, tarea):
        base = tarea["fecha_limite"]
        try:
            fecha = datetime.fromisoformat(base) if base else datetime.now()
        except ValueError:
            fecha = datetime.now()
        salto = {"diaria": timedelta(days=1), "semanal": timedelta(weeks=1),
                 "mensual": timedelta(days=30)}[tarea["recurrencia"]]
        siguiente = max(fecha, datetime.now().replace(hour=0, minute=0, second=0)) + salto
        return self.crear_tarea(
            tarea["agente_id"], tarea["creador_id"], tarea["titulo"],
            tarea["detalle"], tarea["prioridad"], siguiente.date().isoformat(),
            tarea["automatizable"], tarea["recurrencia"],
        )

    def borrar_tarea(self, tarea_id):
        self._q("DELETE FROM tareas WHERE id=?", (tarea_id,))

    # ------------------------------------------------------------------
    # Mensajes
    # ------------------------------------------------------------------

    def mensajes(self, agente_id, limite=200):
        filas = self._todos(
            "SELECT x.*, m.nombre AS autor, m.color AS color FROM mensajes x "
            "LEFT JOIN miembros m ON m.id=x.autor_id "
            "WHERE x.agente_id=? ORDER BY x.id DESC LIMIT ?",
            (agente_id, limite),
        )
        return list(reversed(filas))

    def crear_mensaje(self, agente_id, autor_id, texto, es_ia=False):
        cur = self._q(
            "INSERT INTO mensajes (agente_id, autor_id, es_ia, texto, creado) "
            "VALUES (?,?,?,?,?)",
            (agente_id, autor_id, int(es_ia), texto, ahora()),
        )
        return self._uno("SELECT * FROM mensajes WHERE id=?", (cur.lastrowid,))

    # ------------------------------------------------------------------
    # Actividad
    # ------------------------------------------------------------------

    def registrar(self, autor_id, texto):
        self._q(
            "INSERT INTO actividad (autor_id, texto, creado) VALUES (?,?,?)",
            (autor_id, texto, ahora()),
        )

    def actividad(self, limite=40):
        return self._todos(
            "SELECT x.*, m.nombre AS autor, m.color AS color FROM actividad x "
            "LEFT JOIN miembros m ON m.id=x.autor_id ORDER BY x.id DESC LIMIT ?",
            (limite,),
        )

    # ------------------------------------------------------------------
    # Resumen para el tablero
    # ------------------------------------------------------------------

    def resumen(self):
        hoy = datetime.now().date().isoformat()
        uno = lambda sql, p=(): self._uno(sql, p)["n"]
        return {
            "agentes": uno("SELECT COUNT(*) n FROM agentes"),
            "abiertas": uno("SELECT COUNT(*) n FROM tareas WHERE estado!='hecho'"),
            "hechas": uno("SELECT COUNT(*) n FROM tareas WHERE estado='hecho'"),
            "vencidas": uno(
                "SELECT COUNT(*) n FROM tareas WHERE estado!='hecho' "
                "AND fecha_limite IS NOT NULL AND fecha_limite < ?", (hoy,)),
            "automatizables": uno(
                "SELECT COUNT(*) n FROM tareas WHERE automatizable=1 AND estado!='hecho'"),
            "recurrentes": uno(
                "SELECT COUNT(*) n FROM tareas WHERE recurrencia!='ninguna' AND estado!='hecho'"),
            "fichas": uno("SELECT COUNT(*) n FROM conocimiento"),
            "revision": uno("SELECT COUNT(*) n FROM tareas WHERE estado='revision'"),
        }
