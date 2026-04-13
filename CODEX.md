# Proyecto 09 — Yarig.Telegram

Repositorio oficial: **https://github.com/csilvasantin/02.-YarigTelegram**
Version desplegada: **v.2026.13.04.5**

## Estado (2026-04-08): BOT PROPIO @YarimTelegramBot OPERATIVO EN MAC MINI

Control de Yarig.ai desde Telegram + Consejo de Administracion con 8 sillas IA.
Bot propio: **@YarimTelegramBot** (token independiente, sin conflicto 409 con Memorizer).

## Que queda vivo en el repo
- panel Yarig con botones inline por `task id`
- accesos rapidos inline desde `/yarig` a peticiones, avisos, estado, resumen, onboarding y offboarding
- Consejo de Administracion con dispatch a las 8 sillas
- actas locales del consejo
- arranque persistente por `launchd` (macOS) o manual (Windows)
- resumen diario y mision diaria automatica
- **ranking de productividad** del equipo (`/ranking`)
- **dedicacion del equipo** en tiempo real (`/dedicacion`)
- auto-refresh del panel tras crear tarea
- zona horaria Europe/Madrid en todas las horas mostradas
- blueprint de producto para convertir Yarig.ai completo a Telegram y disenar la futura Yarig.ai IA-first (`docs/yarig_product_blueprint.md`)

## Comandos Yarig
- `/login`, `/logout`, `/cuenta` — conectar cada usuario de Telegram con sus credenciales de Yarig.ai
- `/yarig`, `/tarea`, `/iniciar`, `/pausar`, `/finalizar`
- `/fichar`, `/fichar salida`, `/extras`, `/extras fin`
- `/estado`, `/personal`, `/score`, `/equipo`, `/equipo_lista`, `/finanzas`, `/marca`, `/pedir`, `/peticiones`, `/clientes`, `/cliente`, `/proyectos`, `/proyecto`, `/historial`, `/notificaciones`
- `/consejoweb`, `/consejo_web`, `/admiranext` — enviar misiones al Consejo AdmiraNext web via API local `http://127.0.0.1:3030`
- `/ranking` — ranking de productividad del equipo (XP, tareas, estado, medallas)
- `/dedicacion` — dedicacion del equipo hoy (fichajes, misiones activas/completadas por persona)
- `/stats` — estadísticas anuales (días trabajados, estados, desglose por mes)
- `/puntos` — puntos del mes actual (desglose diario, acumulado, rango)
- `/random` — crea una mision sugerida y la documenta en Yarig.ai
- `/mision_dia` — fuerza la creacion de la mision de arranque del dia
- `/onboarding` — ejecuta manualmente la rutina de arranque del dia
- `/offboarding` — ejecuta manualmente la rutina de cierre del dia
- `/resumen_diario` — fuerza el resumen diario en el chat
- `/chatid` — muestra el id del chat actual

## Comandos consejo
- `/consejo` — mesa del consejo con botones inline
- `/consulta <target> <tarea>` — consulta directa
- `/actas` — historial de consultas
- `/acta <n>` — detalle de un acta
- `/cancelar` — cancela una consulta interactiva

## Automatizaciones diarias
- `08:00` Europe/Madrid: crea o verifica la primera mision del dia en Yarig.ai
  - formato: `Hoy es domingo 5 de abril de 2026`
  - evita duplicados si la mision ya existe
- `09:00` Europe/Madrid: envia resumen diario al grupo configurado
  - sesion abierta
  - mision activa
  - tiempo dedicado
  - XP y rango
  - peticiones pendientes
  - notificaciones recientes
- `20:00` Europe/Madrid: crea o verifica `Inbox 0` y la pone en marcha
- `20:30` Europe/Madrid: completa `Inbox 0` y cierra la jornada con fichar salida

## Servicio persistente
- macOS: LaunchAgent `~/Library/LaunchAgents/com.csilvasantin.yarigtelegram.plist`
- Windows: `python -m src.bot` (requiere `WindowsSelectorEventLoopPolicy` — ya incluido)

## Config relevante
- `.env`: `TELEGRAM_BOT_TOKEN`, `YARIG_EMAIL`, `YARIG_PASSWORD`
- `src/config.py`: `TELEGRAM_DAILY_CHAT_ID` y variables del consejo
- Bot Telegram: **@YarimTelegramBot** (token propio)

## API endpoints descubiertos (2026-04-07)
- `productivity/json_get_team_by_order_or_rank` — ranking del equipo (params: column, order, rank, range)
- `tasks/json_get_newer_company_tasks` — tareas y fichajes de toda la empresa hoy (param: id=0)
- `personal/json_get_user_days` — calendario anual de días trabajados (state, day, month, year)
- `personal/json_get_scoring` — puntos diarios del mes (year, month, day, total, aux)

## Cambios sesion 2026-04-07 (tarde)
7. **`/stats`**: nuevo comando — estadísticas anuales con calendario de días, estados (trabajando/ausente/remoto) y desglose mensual
8. **`/puntos`**: nuevo comando — puntos del mes con desglose diario, acumulado, días positivos/negativos y rango actual
9. **Consejeros 7/8**: CCO y CXO ahora arrancan (antes fallaban); solo CTO falla por red transitoria

## Cambios sesion 2026-04-07
1. **Bot propio creado**: @YarimTelegramBot (antes @YarigAiBot) con token independiente — resuelve conflicto 409 con Memorizer
2. **Fix Windows**: `asyncio.WindowsSelectorEventLoopPolicy()` para evitar `ConnectError` en `start_tls`
3. **`/ranking`**: nuevo comando — ranking de productividad del equipo con XP, tareas, medallas y estado
4. **`/dedicacion`**: nuevo comando — dedicacion del equipo hoy con fichajes, misiones activas y completadas
5. **Auto-refresh panel**: tras crear tarea (por cualquier via) se envia automaticamente el panel `/yarig`
6. **Zona horaria Madrid**: todas las horas se convierten de UTC a Europe/Madrid antes de mostrar
   - `_parse_dt` ahora marca timestamps como UTC
   - `_format_dt_madrid` convierte a hora local Barcelona
   - `_format_elapsed_compact` usa `datetime.now(UTC)` para calculos correctos

## Incidencias resueltas
- ~~Conflicto 409 Memorizer/Yarig.Telegram~~ → bot propio @YarimTelegramBot
- ~~Horas 2h atrasadas~~ → conversion UTC a Europe/Madrid
- ~~ConnectError en Windows~~ → WindowsSelectorEventLoopPolicy

## Nota multi IA
Antes de cerrar una sesion, dejar siempre documentado:
- que se ha cambiado
- que queda pendiente
- si el servicio sigue corriendo
- si se ha subido a GitHub

## Direccion producto
- Yarig.Telegram debe mapear toda la plataforma Yarig.ai y convertirla en operativa movil.
- Cada modulo debe indicar cobertura actual en Telegram, endpoints usados, gaps y comandos propuestos.
- La nueva Yarig.ai se disenara desde los workflows reales descubiertos en Telegram, con look and feel moderno e IA nativa.
