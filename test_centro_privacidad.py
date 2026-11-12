"""Pruebas de privacidad del Centro de Mando: cada integrante ve solo lo suyo; el jefe ve todo.
Uso:  .venv\\Scripts\\python.exe -m unittest test_centro_privacidad -v"""
import os
import tempfile
import unittest

from app.centro.db import Almacen
from app.centro.server import CentroDeMando, ErrorAPI


class IAFalsa:
    def disponibles(self):
        return []


class PrivacidadTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for k in [k for k in os.environ if k.startswith("CENTRO_PIN_")]:
            os.environ.pop(k)
        os.environ["CENTRO_PIN_FRIDA"] = "frida123"
        self.c = CentroDeMando(almacen=Almacen(os.path.join(self.dir, "t.db")), copiloto=IAFalsa())
        db = self.c.db
        self.yael, self.frida, self.efren = (db.miembro_por_nombre(n) for n in ("Yael", "Frida", "Efren"))
        ag = {a["operador_id"]: a for a in db.agentes()}
        self.ag_frida, self.ag_efren = ag[self.frida["id"]], ag[self.efren["id"]]
        self.t_frida = self.c.crear_tarea(self.yael, {"agente_id": self.ag_frida["id"], "titulo": "Brief InCase"})
        self.t_efren = self.c.crear_tarea(self.yael, {"agente_id": self.ag_efren["id"], "titulo": "Reporte ventas"})

    def titulos(self, yo, agente_id=None):
        return {t["titulo"] for t in self.c.tareas(yo, agente_id)}

    def test_jefe_ve_todo(self):
        self.assertEqual(self.titulos(self.yael), {"Brief InCase", "Reporte ventas"})

    def test_integrante_ve_solo_lo_suyo(self):
        self.assertEqual(self.titulos(self.frida), {"Brief InCase"})
        self.assertEqual(self.titulos(self.efren), {"Reporte ventas"})

    def test_integrante_ve_lo_que_creo_para_otro(self):
        self.c.crear_tarea(self.frida, {"agente_id": self.ag_efren["id"], "titulo": "Pedido de Frida"})
        self.assertIn("Pedido de Frida", self.titulos(self.frida))
        self.assertNotIn("Reporte ventas", self.titulos(self.frida))

    def test_detalle_de_agente_ajeno(self):
        d = self.c.detalle_agente(self.frida, self.ag_efren["id"])
        self.assertEqual(d["tareas"], [])
        self.assertEqual(d["mensajes"], [])

    def test_no_puede_tocar_tarea_ajena(self):
        for f in (lambda: self.c.actualizar_tarea(self.frida, self.t_efren["id"], {"estado": "hecho"}),
                  lambda: self.c.borrar_tarea(self.frida, self.t_efren["id"]),
                  lambda: self.c.enviar_mensaje(self.frida, self.ag_efren["id"], {"texto": "hola"})):
            with self.assertRaises(ErrorAPI):
                f()

    def test_actividad_y_resumen_privados(self):
        e = self.c.estado(self.frida)
        self.assertTrue(all(x["autor_id"] == self.frida["id"] for x in e["actividad"]))
        self.assertEqual(e["resumen"]["abiertas"], 1)
        self.assertEqual(self.c.estado(self.yael)["resumen"]["abiertas"], 2)

    def test_bloqueo_por_intentos(self):
        for _ in range(5):
            with self.assertRaises(ErrorAPI):
                self.c.login({"nombre": "Frida", "pin": "mal"})
        with self.assertRaises(ErrorAPI) as e:
            self.c.login({"nombre": "Frida", "pin": "frida123"})
        self.assertEqual(e.exception.codigo, 429)


if __name__ == "__main__":
    unittest.main()
