"""
YAELCORE-OS · Conector de Meta Ads (solo lectura)

Lee el rendimiento real de las campañas con la API de Marketing de Meta y lo
entrega a los agentes del Centro de Mando. NO modifica nada: no pausa, no
cambia presupuestos, no crea anuncios.

Configuración en .env:
    META_ACCESS_TOKEN=...            token de un usuario del sistema con permiso ads_read
    META_AD_ACCOUNTS=Movilera:289256139,PhoneDepot:123456789   (nombre:id, separados por coma)
    META_API_VERSION=v23.0           opcional
    META_CTR_MINIMO=0.8              opcional, en %
    META_FRECUENCIA_MAX=3.5          opcional
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.facebook.com"

# Qué cuenta como "resultado" (se usa el primero que tenga datos)
ACCIONES_RESULTADO = [
    ("purchase", "compras"),
    ("omni_purchase", "compras"),
    ("lead", "leads"),
    ("onsite_conversion.lead_grouped", "leads"),
    ("onsite_conversion.messaging_conversation_started_7d", "conversaciones"),
    ("landing_page_view", "visitas a la página"),
    ("link_click", "clics al enlace"),
]


class MetaAdsError(Exception):
    pass


def configurado():
    return bool(os.getenv("META_ACCESS_TOKEN")) and bool(cuentas())


def cuentas():
    """[('Movilera', '289256139'), ...] desde META_AD_ACCOUNTS."""
    salida = []
    for parte in os.getenv("META_AD_ACCOUNTS", "").split(","):
        parte = parte.strip()
        if not parte:
            continue
        nombre, _, ident = parte.rpartition(":")
        ident = ident.strip().removeprefix("act_")
        if ident.isdigit():
            salida.append((nombre.strip() or ident, ident))
    return salida


def _get(ruta, params, abrir=urllib.request.urlopen):
    version = os.getenv("META_API_VERSION", "v23.0")
    token = os.getenv("META_ACCESS_TOKEN", "")
    consulta = urllib.parse.urlencode({**params, "access_token": token})
    url = f"{API}/{version}/{ruta}?{consulta}"
    try:
        with abrir(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        # Nunca se incluye la URL (lleva el token)
        raise MetaAdsError(f"Meta respondió {e.code}: {msg[:200]}") from None
    except Exception as e:
        raise MetaAdsError(f"Sin conexión con Meta: {type(e).__name__}") from None


def _resultado(fila):
    acciones = {a["action_type"]: float(a["value"]) for a in fila.get("actions", []) or []}
    for clave, etiqueta in ACCIONES_RESULTADO:
        if acciones.get(clave):
            return acciones[clave], etiqueta
    return 0.0, "resultados"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def campanas(cuenta_id, periodo="yesterday", abrir=urllib.request.urlopen):
    datos = _get(f"act_{cuenta_id}/insights", {
        "level": "campaign",
        "date_preset": periodo,
        "fields": "campaign_id,campaign_name,spend,impressions,reach,frequency,clicks,ctr,cpc,cpm,actions",
        "limit": 100,
    }, abrir)
    filas = []
    for f in datos.get("data", []):
        res, etiqueta = _resultado(f)
        gasto = _f(f.get("spend"))
        filas.append({
            "id": f.get("campaign_id"), "nombre": f.get("campaign_name", "(sin nombre)"),
            "gasto": gasto, "impresiones": int(_f(f.get("impressions"))), "alcance": int(_f(f.get("reach"))),
            "frecuencia": _f(f.get("frequency")), "clics": int(_f(f.get("clicks"))),
            "ctr": _f(f.get("ctr")), "cpc": _f(f.get("cpc")), "cpm": _f(f.get("cpm")),
            "resultados": res, "tipo_resultado": etiqueta,
            "costo_resultado": gasto / res if res else None,
        })
    return sorted(filas, key=lambda x: -x["gasto"])


def alertas(hoy, semana):
    """Reglas simples sobre datos reales. hoy=ayer, semana=últimos 7 días."""
    ctr_min = _f(os.getenv("META_CTR_MINIMO", "0.8"))
    frec_max = _f(os.getenv("META_FRECUENCIA_MAX", "3.5"))
    prom = {c["id"]: c for c in semana}
    salida = []
    for c in hoy:
        if c["gasto"] > 0 and not c["resultados"]:
            salida.append(f"«{c['nombre']}» gastó ${c['gasto']:,.2f} sin {c['tipo_resultado']}.")
        if c["impresiones"] >= 1000 and c["ctr"] < ctr_min:
            salida.append(f"«{c['nombre']}» tiene CTR bajo: {c['ctr']:.2f}% (mínimo {ctr_min}%).")
        if c["frecuencia"] > frec_max:
            salida.append(f"«{c['nombre']}» frecuencia {c['frecuencia']:.1f}: posible fatiga del anuncio.")
        base = prom.get(c["id"])
        if base and c["costo_resultado"] and base["costo_resultado"]:
            cambio = c["costo_resultado"] / base["costo_resultado"] - 1
            if cambio > 0.3:
                salida.append(f"«{c['nombre']}» costo por {c['tipo_resultado']} subió {cambio:.0%} vs. su promedio de 7 días.")
    return salida


def _tabla(filas):
    if not filas:
        return "  (sin gasto en el periodo)"
    lineas = []
    for c in filas[:15]:
        cpr = f"${c['costo_resultado']:,.2f}" if c["costo_resultado"] else "—"
        lineas.append(
            f"  • {c['nombre']}: gasto ${c['gasto']:,.2f} · {c['resultados']:.0f} {c['tipo_resultado']} "
            f"(costo {cpr}) · CTR {c['ctr']:.2f}% · CPC ${c['cpc']:,.2f} · frec. {c['frecuencia']:.1f}")
    return "\n".join(lineas)


def reporte(abrir=urllib.request.urlopen):
    """Texto con datos REALES de Meta Ads para dárselo a la IA (o al equipo)."""
    if not configurado():
        return ("META ADS: no conectado. Falta META_ACCESS_TOKEN o META_AD_ACCOUNTS en .env. "
                "No hay datos de campañas disponibles.")
    bloques = []
    for nombre, ident in cuentas():
        try:
            ayer = campanas(ident, "yesterday", abrir)
            semana = campanas(ident, "last_7d", abrir)
        except MetaAdsError as e:
            bloques.append(f"CUENTA {nombre} (act_{ident}): ERROR al leer datos — {e}")
            continue
        total_ayer = sum(c["gasto"] for c in ayer)
        total_sem = sum(c["gasto"] for c in semana)
        al = alertas(ayer, semana)
        bloques.append(
            f"CUENTA {nombre} (act_{ident})\n"
            f"Ayer — gasto total ${total_ayer:,.2f}:\n{_tabla(ayer)}\n"
            f"Últimos 7 días — gasto total ${total_sem:,.2f}:\n{_tabla(semana)}\n"
            f"Alertas automáticas:\n" + ("\n".join(f"  ⚠ {a}" for a in al) if al else "  Sin alertas.")
        )
    return "DATOS REALES DE META ADS (solo lectura, montos en la moneda de la cuenta)\n\n" + "\n\n".join(bloques)


def es_tarea_de_campanas(titulo):
    t = (titulo or "").lower()
    return any(p in t for p in ("campaña", "campana", "meta ads", "publicidad", "pauta", "anuncio"))
