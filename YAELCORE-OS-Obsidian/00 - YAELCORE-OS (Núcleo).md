---
tipo: nucleo
actualizado: 2026-11-07
tags: [yaelcore, moc]
---
# YAELCORE-OS — Núcleo

Mapa de todas las unidades de negocio y proyectos creados con Claude.
Abre la **Vista de gráfico** (Ctrl/Cmd + G) para verlo como red neuronal.

## Unidades de negocio (por fecha de inicio)
### [[Unidad - Herramientas]] (2026-07-25 a 2026-07-25)
- [[claude-code fork]] (2026-07-25 a 2026-07-25)
### [[Unidad - Marca y Contenido]] (2026-08-03 a 2026-08-03)
- [[YAELCORE-MARCA]] (2026-08-03 a 2026-08-03)
### [[Unidad - Asistente de Escritorio]] (2026-08-06 a 2026-10-17)
- [[jarvis-os]] (2026-08-06 a 2026-10-17)
- [[YAELCORE-OS]] (2026-10-13 a 2026-10-17)
### [[Unidad - IA y Agentes]] (2026-10-13 a en curso)
- [[YAELCORE-AGENTS]] (2026-10-13 a en curso)
### [[Unidad - Automatización y Mensajería]] (2026-10-15 a en curso)
- [[WhatsApp Business Cloud node]] (2026-10-15 a en curso)
### [[Unidad - Trading]] (2026-10-16 a 2026-10-17)
- [[YAELCORE-TRADING]] (2026-10-16 a 2026-10-17)
### [[Unidad - Apps]] (2026-10-25 a en curso)
- [[Yaelcore-app]] (2026-10-25 a en curso)

### [[Chats claude.ai - Pendientes]]

## Línea de tiempo
| Inicio | Fin | Proyecto | Unidad |
|---|---|---|---|
| 2026-07-25 | 2026-07-25 | [[claude-code fork]] | Unidad - Herramientas |
| 2026-08-03 | 2026-08-03 | [[YAELCORE-MARCA]] | Unidad - Marca y Contenido |
| 2026-08-06 | 2026-10-17 | [[jarvis-os]] | Unidad - Asistente de Escritorio |
| 2026-10-13 | 2026-10-17 | [[YAELCORE-OS]] | Unidad - Asistente de Escritorio |
| 2026-10-13 | en curso | [[YAELCORE-AGENTS]] | Unidad - IA y Agentes |
| 2026-10-15 | en curso | [[WhatsApp Business Cloud node]] | Unidad - Automatización y Mensajería |
| 2026-10-16 | 2026-10-17 | [[YAELCORE-TRADING]] | Unidad - Trading |
| 2026-10-25 | en curso | [[Yaelcore-app]] | Unidad - Apps |

## Tecnologías
[[Python]], [[Claude API]], [[OpenAI API]], [[Windows]], [[WhatsApp Business API]], [[GitHub]]

## Tablero (requiere el plugin Dataview)
```dataview
TABLE unidad, estado, inicio, fin, ultima_actividad
FROM #proyecto
SORT inicio ASC
```

> Fechas: inicio = creación del repo o primera sesión; fin = última actividad.
> "en curso" = actividad desde el 2026-10-20.
