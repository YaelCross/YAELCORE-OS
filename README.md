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
