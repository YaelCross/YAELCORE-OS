"""Pruebas del motor de automatización del Centro de Mando.
Uso:  .venv\\Scripts\\python.exe -m unittest test_centro_automatizacion -v"""
import os
import tempfile
import unittest
from datetime import datetime, timedelta

from app.centro.automatizacion import Automatizador, hora_de
from app.centro.db import Almacen
from app.centro.ia import CopilotoIA
from app.centro.server import CentroDeMando


class IAFalsa:
    """Proveedor de prueba: responde o falla según se le indique."""
    def __init__(self, nombre, falla=False):
        self.nombre, self.falla, self.llamadas = nombre, falla, 0

    def ask(self, pregunta, instrucciones, historial=None):
        self.llamadas += 1
        self.ultima = pregunta
        if self.falla:
            raise RuntimeError(f"{self.nombre} sin servicio")
        return f"Checklist preparado por {self.nombre}"


def copiloto(*ias):
    c = CopilotoIA()
    c._ias = list(ias)
    return c


class AutomatizacionTest(unittest.TestCase):
    def setUp(self):
        os.environ["CENTRO_AUTOMATIZAR"] = "si"
        os.environ["CENTRO_RESUMEN_HORA"] = "18:30"
        self.claude, self.gpt = IAFalsa("Claude"), IAFalsa("ChatGPT")
        db = Almacen(os.path.join(tempfile.mkdtemp(), "t.db"))
        self.c = CentroDeMando(almacen=db, copiloto=copiloto(self.claude, self.gpt))
        self.auto = Automatizador(self.c)
        self.db = db
        self.yael = db.miembro_por_nombre("Yael")
        self.ag = db.agentes()[0]
        self.hoy = datetime(2026, 11, 9)

    def tarea(self, titulo, auto=True, **kw):
        return self.c.crear_tarea(self.yael, {"agente_id": self.ag["id"], "titulo": titulo, "automatizable": auto, **kw})

    def test_hora_en_titulo(self):
        self.assertEqual(hora_de("09:00 · Revisión"), (9, 0))
        self.assertIsNone(hora_de("Sin hora"))

    def test_ejecuta_a_su_hora_y_deja_en_revision(self):
        t = self.tarea("10:00 · Programación de contenido")
        self.auto.ciclo(self.hoy.replace(hour=9, minute=59))
        self.assertEqual(self.db.tarea(t["id"])["estado"], "pendiente")
        self.auto.ciclo(self.hoy.replace(hour=10, minute=0))
        r = self.db.tarea(t["id"])
        self.assertEqual(r["estado"], "revision")  # nunca "hecho" sin una persona
        self.assertIn("[Automático · Claude", r["resultado"])
        self.auto.ciclo(self.hoy.replace(hour=10, minute=5))
        self.assertEqual(self.claude.llamadas, 1)  # una vez por día

    def test_respaldo_chatgpt_si_claude_falla(self):
        self.claude.falla = True
        t = self.tarea("Reporte del día")
        self.auto.ciclo(self.hoy.replace(hour=12))
        r = self.db.tarea(t["id"])
        self.assertEqual(r["estado"], "revision")
        self.assertIn("ChatGPT", r["resultado"])

    def test_si_ambas_fallan_reintenta(self):
        self.claude.falla = self.gpt.falla = True
        t = self.tarea("Reporte del día")
        base = self.hoy.replace(hour=12)
        self.auto.ciclo(base)
        self.assertEqual(self.db.tarea(t["id"])["estado"], "pendiente")
        self.auto.ciclo(base + timedelta(minutes=5))       # aún no reintenta
        self.assertEqual(self.claude.llamadas, 1)
        self.claude.falla = False
        self.auto.ciclo(base + timedelta(minutes=16))      # reintento
        self.assertEqual(self.db.tarea(t["id"])["estado"], "revision")

    def test_no_toca_tareas_no_automatizables_ni_futuras(self):
        a = self.tarea("Supervisar local", auto=False)
        b = self.tarea("Comisiones día 20", fecha_limite="2026-11-20")
        self.auto.ciclo(self.hoy.replace(hour=12))
        self.assertEqual(self.db.tarea(a["id"])["estado"], "pendiente")
        self.assertEqual(self.db.tarea(b["id"])["estado"], "pendiente")
        self.assertEqual(self.claude.llamadas, 0)

    def test_renueva_diarias_y_resumen(self):
        t = self.tarea("Seguimiento", auto=False, recurrencia="diaria", fecha_limite="2026-11-08")
        self.auto.ciclo(self.hoy.replace(hour=8))
        self.assertEqual(self.db.tarea(t["id"])["fecha_limite"], "2026-11-09")
        self.auto.ciclo(self.hoy.replace(hour=18, minute=31))
        self.assertEqual(len(self.auto._registros("resumen", "2026-11-09")), 1)
        self.auto.ciclo(self.hoy.replace(hour=18, minute=40))
        self.assertEqual(len(self.auto._registros("resumen", "2026-11-09")), 1)

    def test_tarea_de_campanas_recibe_datos_de_meta(self):
        from unittest import mock
        with mock.patch("app.centro.meta_ads.reporte", return_value="DATOS REALES DE META ADS · prueba"):
            self.tarea("09:00 · Revisión y seguimiento de campañas publicitarias")
            self.auto.ciclo(self.hoy.replace(hour=9, minute=1))
        self.assertIn("DATOS REALES DE META ADS · prueba", self.claude.ultima)


if __name__ == "__main__":
    unittest.main()
