# CODEX — Yarig.Telegram

## Estado (2026-04-05): CONSEJO + YARIG OPERATIVO Y PROGRAMADO PARA MANANA

Control de Yarig.ai desde Telegram + Consejo de Administracion con 8 sillas IA.
Integrado en Memorizer bot (csilvasantin/Memorizer).

## Que queda vivo en el repo
- panel Yarig con botones inline por `task id`
- Consejo de Administracion con dispatch a las 8 sillas
- actas locales del consejo
- arranque persistente por `launchd`
- resumen diario y mision diaria automatica

## Comandos Yarig
- `/yarig`, `/tarea`, `/iniciar`, `/pausar`, `/finalizar`
- `/fichar`, `/fichar salida`, `/extras`, `/extras fin`
- `/estado`, `/score`, `/equipo`, `/pedir`, `/peticiones`, `/proyectos`, `/historial`, `/notificaciones`
- `/random` — crea una mision sugerida y la documenta en Yarig.ai
- `/mision_dia` — fuerza la creacion de la mision de arranque del dia
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
- LaunchAgent: `~/Library/LaunchAgents/com.csilvasantin.yarigtelegram.plist`
- Script de gestion: `/Users/Carlos/Documents/Codex/Yarig.Telegram/manage_launchd.sh`
- Estado esperado: una sola instancia estable del bot, sin dobles `getUpdates`

## Config relevante
- `.env`: `TELEGRAM_BOT_TOKEN`, `YARIG_EMAIL`, `YARIG_PASSWORD`
- `src/config.py`: `TELEGRAM_DAILY_CHAT_ID` y variables del consejo

## Incidencia abierta
- `Memorizer` y `Yarig.Telegram` siguen compartiendo el token de `Memorizer2Bot`.
- Las automatizaciones horarias ya estan cableadas y el scheduler ya esta instalado.
- El conflicto `409 Conflict` queda aplazado hasta manana, cuando se cree un bot propio para `Yarig.Telegram` o se reasigne `Memorizer` a otro token.

## Nota multi IA
Antes de cerrar una sesion, dejar siempre documentado:
- que se ha cambiado
- que queda pendiente
- si el servicio sigue corriendo
- si se ha subido a GitHub
