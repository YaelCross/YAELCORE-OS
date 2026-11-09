"""Prueba la conexión REAL con Meta Ads sin mostrar el token.
Uso:  .venv\\Scripts\\python.exe probar_meta.py"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.centro import meta_ads

token = os.getenv("META_ACCESS_TOKEN", "")
print("== Meta Ads ==")
print(f"[{'OK ' if token else 'FALLA'}] META_ACCESS_TOKEN presente (longitud: {len(token)})")
print(f"[{'OK ' if meta_ads.cuentas() else 'FALLA'}] META_AD_ACCOUNTS: {', '.join(f'{n} (act_{i})' for n, i in meta_ads.cuentas()) or 'vacío'}")
if not meta_ads.configurado():
    raise SystemExit("\nCompleta las dos líneas en .env y vuelve a ejecutar.")
for nombre, ident in meta_ads.cuentas():
    try:
        filas = meta_ads.campanas(ident, "last_7d")
        print(f"[OK ] {nombre}: {len(filas)} campañas con gasto en 7 días · total ${sum(c['gasto'] for c in filas):,.2f}")
    except meta_ads.MetaAdsError as e:
        print(f"[FALLA] {nombre}: {e}")
print("\n" + meta_ads.reporte())
