# YAELCORE-OS

Asistente personal de escritorio para Windows.

## Iniciar manualmente

- `jarvis.bat` — abre YAELCORE-OS con ventana de consola (útil para ver errores).
- `iniciar_yaelcore.vbs` — abre YAELCORE-OS sin ventana de consola.

Ambos usan el entorno virtual `.venv` dentro de esta carpeta.

## Iniciar automáticamente al encender la computadora

1. Asegúrate de que `.venv` existe y tiene las dependencias instaladas
   (prueba primero con `jarvis.bat`).
2. Haz doble clic en **`instalar_inicio_automatico.bat`**.

Esto crea el acceso directo `YAELCORE-OS` en la carpeta **Inicio** de Windows
(`shell:startup`), así que el sistema arrancará cada vez que inicies sesión.

Para desactivarlo, haz doble clic en **`quitar_inicio_automatico.bat`**.

> Si mueves la carpeta del proyecto a otro lugar, vuelve a ejecutar
> `instalar_inicio_automatico.bat` para actualizar el acceso directo.

## Cerebro: Claude + ChatGPT trabajando juntos

JARVIS usa dos inteligencias. Por defecto trabajan **en equipo**:
ChatGPT prepara la respuesta y Claude la revisa, corrige y te la entrega.
Si una falla o no tiene clave, la otra responde sola.

### Configurar las claves

1. Copia `.env.example` y renómbralo a `.env`.
2. Pega tu clave de OpenAI en `OPENAI_API_KEY`
   (https://platform.openai.com/api-keys).
3. Pega tu clave de Anthropic en `ANTHROPIC_API_KEY`
   (https://console.anthropic.com/settings/keys).
4. Instala las dependencias nuevas:
   `.venv\Scripts\python.exe -m pip install -r requirements.txt`

### Comandos de voz

| Dices | Qué hace |
|-------|----------|
| "modo equipo" / "trabajen juntos" | ChatGPT redacta y Claude revisa (por defecto) |
| "usa Claude" | Solo responde Claude |
| "usa ChatGPT" | Solo responde ChatGPT |
| "pregúntale a Claude …" | Pregunta directa a Claude, sin cambiar de modo |
| "pregúntale a ChatGPT …" | Pregunta directa a ChatGPT, sin cambiar de modo |
| "¿qué modo?" | JARVIS te dice qué modo está activo |
| "olvida la conversación" | Borra la memoria de la charla actual |

Ambas IAs comparten la memoria de las últimas 6 preguntas, así que
puedes hacer preguntas de seguimiento ("¿y en inglés?").

El modo inicial se cambia en `.env` con `JARVIS_MODO=equipo|claude|chatgpt`,
y los modelos con `OPENAI_MODEL` y `CLAUDE_MODEL`.

## Centro de Mando: el equipo trabajando con sus agentes

Interfaz web donde cada persona real (Yael, Frida, Efren, Nova…) controla
a su agente, le pasa toda la información necesaria y automatiza tareas.
Replica el diagrama de la organización: Frente, front, back, interfaz,
núcleo, agentes, integrantes MKT, jefe Yael, Frida, Efren y Nova.

### Cómo abrirlo

- Doble clic en **`centro_mando.bat`**, o
- dile a JARVIS **"abre el centro de mando"**, o
- `python centro_mando.py`

En la consola aparecen dos direcciones:

- **En esta PC:** `http://localhost:8765`
- **Para tu equipo:** `http://<ip-de-tu-pc>:8765` — compártela con Frida,
  Efren y Nova; entran desde su navegador si están en la misma red (Wi-Fi).
  Si Windows pregunta por el firewall, permite el acceso en redes privadas.

### Qué puede hacer cada quien

| Sección | Para qué sirve |
|---------|----------------|
| **Mapa** | Tu diagrama en vivo. Toca a una persona para abrir su agente o un área para ver sus tareas. Muestra tareas abiertas y vencidas. |
| **Agente** | Misión del agente, sus tareas, **"Pasarle información"** (su memoria) y el **canal** con el equipo y el **copiloto IA**. |
| **Tareas** | Tablero Pendiente → En curso → Revisión → Hecho (arrastra las tarjetas). Filtra por agente, área o persona. |
| **Conocimiento** | Toda la información que el equipo le ha pasado a los agentes. Yael puede enviar información general a **todos** los agentes. |
| **Equipo** | (Solo Yael) Crear agentes, asignar quién los controla y agregar integrantes. |

**Copiloto IA:** cada agente usa Claude/ChatGPT con su misión, su
información y sus tareas. Botones rápidos: *¿Qué hago primero?*,
*¿Qué automatizo?*, *Resumen para Yael* y *¿Qué info me falta?*.

**Automatización:** marca una tarea como *se repite* (diaria, semanal,
mensual). Al terminarla, el sistema crea sola la siguiente. Marca también
las tareas *automatizables* para que el copiloto proponga cómo automatizarlas.

**Permisos:** Yael ve y controla todo. Cada integrante opera su propio
agente; cualquiera puede pasarle tareas o mensajes a otro agente para
coordinarse.

### PIN de acceso

Define un PIN por persona en `.env` (ver `.env.example`):

```
CENTRO_PIN_YAEL=1234
CENTRO_PIN_FRIDA=...
```

Si alguien no tiene PIN, puede entrar sin contraseña (útil solo para
pruebas). Los datos se guardan en `data/centro_mando.db` (no se sube a git).
