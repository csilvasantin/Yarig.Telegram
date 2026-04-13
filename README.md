# Yarig.Telegram

Control completo de [Yarig.ai](https://yarig.ai) desde Telegram con panel interactivo de tareas, resumenes automaticos y arranque diario de mision.

## Que hace

Replica la operativa diaria de Yarig.ai dentro de Telegram para que el equipo pueda trabajar sin entrar en la web:

- panel inline para iniciar, pausar y completar misiones
- accesos rapidos inline a peticiones, avisos, estado, resumen, onboarding y offboarding
- creacion directa de tareas desde Telegram
- estado de jornada, score, equipo, historial y notificaciones
- bandeja de peticiones recibidas
- resumen diario automatico en Telegram
- mision de arranque automatica a las 08:00
- cierre de jornada automatizado con Inbox 0 a las 20:00 y salida a las 20:30

## Comandos

### Tareas
| Comando | Descripcion |
|---------|-------------|
| `/yarig` | Panel de tareas con controles inline |
| `/tarea <desc>` | Añadir tarea directa al proyecto por defecto |
| `/iniciar [n]` | Iniciar o reanudar tarea |
| `/pausar` | Pausar tarea activa |
| `/finalizar [n]` | Completar tarea |
| `/random [proyecto]` | Crear una mision sugerida por el bot |
| `/mision_dia` | Crear manualmente la mision de arranque del dia |
| `/onboarding` | Ejecutar manualmente la rutina de arranque del dia |
| `/offboarding` | Ejecutar manualmente la rutina de cierre del dia |

Formato con proyecto: `/tarea Proyecto :: Descripcion`

### Jornada
| Comando | Descripcion |
|---------|-------------|
| `/fichar` | Fichar entrada |
| `/fichar salida` | Fichar salida |
| `/extras` | Iniciar horas extras |
| `/extras fin` | Finalizar horas extras |
| `/estado` | Estado actual: jornada, tarea activa y puntuacion |
| `/score` | Tu puntuacion |

### Equipo y contexto
| Comando | Descripcion |
|---------|-------------|
| `/equipo` | Miembros del equipo |
| `/pedir <nombre> <tarea>` | Enviar peticion a compañero |
| `/peticiones` | Ver y gestionar peticiones recibidas |
| `/clientes [texto]` | Lista o busca clientes |
| `/cliente <texto>` | Ficha movil de cliente con proyectos y actividad de hoy |
| `/proyectos [texto]` | Lista o busca proyectos |
| `/proyecto <texto>` | Ficha movil de proyecto con actividad de hoy y acciones rapidas |
| `/historial` | Historial de tareas |
| `/notificaciones` | Avisos recientes de Yarig |
| `/resumen_diario` | Forzar el resumen diario en el chat |
| `/chatid` | Mostrar el id del chat actual |
| `/help` | Ayuda del bot |

## Automatizaciones diarias

El bot queda preparado para manana con dos rutinas fijas en horario de Madrid:

- `08:00` crea o verifica la primera mision del dia con este formato: `Hoy es domingo 5 de abril de 2026`
- `09:00` envia al grupo el resumen diario de Yarig con sesion, mision activa, XP, peticiones y notificaciones
- `20:00` crea o verifica `Inbox 0` y la pone en marcha para cerrar el dia
- `20:30` completa `Inbox 0` y ejecuta la salida de jornada

La mision de las 08:00 evita duplicados: si ya existe para ese dia, no la vuelve a crear. `Inbox 0` tambien evita duplicados y, si ya existe, reutiliza la tarea del dia.

## Servicio persistente en macOS

```bash
/Users/Carlos/Documents/Codex/Yarig.Telegram/manage_launchd.sh status
/Users/Carlos/Documents/Codex/Yarig.Telegram/manage_launchd.sh restart
/Users/Carlos/Documents/Codex/Yarig.Telegram/manage_launchd.sh logs
```

Servicio usado: `com.csilvasantin.yarigtelegram`

## Setup local

```bash
cp .env.example .env
# Edita .env con tus credenciales

pip install -r requirements.txt
python -m src.bot
```

## API de Yarig.ai

Documentacion completa de los 25 endpoints JSON en [docs/yarig_api_map.md](docs/yarig_api_map.md).

## Blueprint de producto

La vision funcional de Yarig.Telegram como capa movil de Yarig.ai y base para una futura Yarig.ai IA-first esta documentada en [docs/yarig_product_blueprint.md](docs/yarig_product_blueprint.md).

## Tech Stack

- Python 3.13+
- python-telegram-bot
- aiohttp (sesion con Yarig.ai)
- Yarig.ai API (session-based PHP auth)

## Incidencia conocida

- Ahora mismo `Memorizer` y `Yarig.Telegram` comparten el token de `Memorizer2Bot`.
- Eso provoca `409 Conflict` si ambos escuchan Telegram a la vez.
- La logica de las automatizaciones ya queda guardada; la separacion definitiva de bots se hara manana cuando BotFather permita crear el nuevo bot.
