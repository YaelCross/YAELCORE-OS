"""Pruebas del conector de Meta Ads con respuestas simuladas de la API (sin red).
Uso:  .venv\\Scripts\\python.exe -m unittest test_meta_ads -v"""
import io
import json
import os
import unittest
import urllib.error

from app.centro import meta_ads


def respuesta(datos):
    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False
    return R(json.dumps(datos).encode())


AYER = {"data": [
    {"campaign_id": "1", "campaign_name": "Fundas InCase", "spend": "500", "impressions": "20000", "reach": "9000",
     "frequency": "2.2", "clicks": "100", "ctr": "0.5", "cpc": "5", "cpm": "25",
     "actions": [{"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "10"}]},
    {"campaign_id": "2", "campaign_name": "Micas Movilera", "spend": "300", "impressions": "8000", "reach": "1500",
     "frequency": "5.3", "clicks": "160", "ctr": "2.0", "cpc": "1.9", "cpm": "37", "actions": []},
]}
SEMANA = {"data": [
    {"campaign_id": "1", "campaign_name": "Fundas InCase", "spend": "2100", "impressions": "90000", "reach": "30000",
     "frequency": "3", "clicks": "900", "ctr": "1", "cpc": "2.3", "cpm": "23",
     "actions": [{"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "70"}]},
]}


class MetaAdsTest(unittest.TestCase):
    def setUp(self):
        os.environ["META_ACCESS_TOKEN"] = "TOKEN-SECRETO-123"
        os.environ["META_AD_ACCOUNTS"] = "Movilera:289256139"
        self.urls = []

    def abrir(self, url, timeout=30):
        self.urls.append(url)
        return respuesta(AYER if "yesterday" in url else SEMANA)

    def test_cuentas(self):
        os.environ["META_AD_ACCOUNTS"] = "Movilera:289256139, PhoneDepot:act_555, malo:x"
        self.assertEqual(meta_ads.cuentas(), [("Movilera", "289256139"), ("PhoneDepot", "555")])

    def test_reporte_con_datos_reales_y_alertas(self):
        r = meta_ads.reporte(self.abrir)
        self.assertIn("Fundas InCase", r)
        self.assertIn("10 conversaciones", r)
        self.assertIn("«Micas Movilera» gastó $300.00 sin", r)       # gasto sin resultados
        self.assertIn("CTR bajo: 0.50%", r)                         # CTR bajo
        self.assertIn("frecuencia 5.3", r)                           # fatiga
        self.assertIn("subió 67%", r)                                # costo por resultado 50 vs 30
        self.assertTrue(all("act_289256139/insights" in u for u in self.urls))

    def test_error_no_expone_token(self):
        def falla(url, timeout=30):
            raise urllib.error.HTTPError(url, 400, "x", {}, io.BytesIO(b'{"error":{"message":"Invalid OAuth access token"}}'))
        r = meta_ads.reporte(falla)
        self.assertIn("ERROR al leer datos", r)
        self.assertIn("Invalid OAuth", r)
        self.assertNotIn("TOKEN-SECRETO", r)

    def test_sin_configurar(self):
        os.environ["META_ACCESS_TOKEN"] = ""
        self.assertIn("no conectado", meta_ads.reporte(self.abrir))
        self.assertEqual(self.urls, [])

    def test_detecta_tareas_de_campanas(self):
        self.assertTrue(meta_ads.es_tarea_de_campanas("09:00 · Revisión y seguimiento de campañas publicitarias"))
        self.assertFalse(meta_ads.es_tarea_de_campanas("Supervisión del local Movilera"))


if __name__ == "__main__":
    unittest.main()
