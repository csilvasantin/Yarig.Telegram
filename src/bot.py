"""Yarig.Telegram — Control completo de Yarig.ai desde Telegram."""

import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import contextvars
import logging
import random
import secrets
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    Defaults,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode
from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_DAILY_CHAT_ID
from src.yarig import YarigClient
from src.consejo import (
    build_board_table,
    build_board_keyboard,
    resolve_target,
    dispatch_task,
    assemble_full_response,
    format_target_label,
)
from src.actas import (
    get_acta,
    get_recent_actas,
    format_acta_detail,
    format_actas_list,
)
from src.dispatch_telegram import notify_consejero_bots

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

CURRENT_USER_ID: contextvars.ContextVar[int | None] = contextvars.ContextVar("current_user_id", default=None)
DEFAULT_YARIG = YarigClient()
USER_YARIG_CLIENTS: dict[int, YarigClient] = {}
PENDING_REQUESTS: dict[str, dict] = {}
PENDING_TASKS: dict[str, dict] = {}
PENDING_LOGIN_EMAIL: dict[int, str] = {}

MADRID_TZ = ZoneInfo("Europe/Madrid")
LOGIN_EMAIL, LOGIN_PASSWORD = range(2)
APP_VERSION = "v.2026.13.04.4"


class YarigSessionRouter:
    """Delegate Yarig calls to the logged-in Telegram user's client."""

    def _client(self) -> YarigClient:
        user_id = CURRENT_USER_ID.get()
        if user_id is not None and user_id in USER_YARIG_CLIENTS:
            return USER_YARIG_CLIENTS[user_id]
        return DEFAULT_YARIG

    def __getattr__(self, name: str):
        return getattr(self._client(), name)

    async def close(self) -> None:
        await DEFAULT_YARIG.close()
        for client in list(USER_YARIG_CLIENTS.values()):
            await client.close()


yarig = YarigSessionRouter()


RANDOM_TASK_TEMPLATES = [
    "Revisar mensajes pendientes y convertirlos en siguientes acciones claras",
    "Ordenar ideas sueltas del proyecto y dejar tres decisiones propuestas",
    "Documentar el siguiente paso del flujo actual para no perder contexto",
    "Detectar un cuello de botella del dia y proponer una mejora pequena",
    "Limpiar tareas abiertas y dejar una lista corta de prioridades reales",
    "Revisar avances recientes y anotar un resumen util para el equipo",
    "Preparar una micro mejora de UX en el frente mas activo del proyecto",
    "Convertir una idea difusa en una tarea concreta con criterio de cierre",
    "Revisar el panel actual y anotar una mejora visible de producto",
    "Buscar una pequena automatizacion que ahorre pasos repetitivos hoy",
]


HELP_TEXT = (
    "✦ Yarig.Telegram\n"
    f"{APP_VERSION}\n"
    "Control de Yarig.ai desde Telegram\n\n"
    "Cuenta\n"
    "/login — Conectar tu usuario de Yarig.ai\n"
    "/logout — Cerrar tu sesion en este bot\n"
    "/cuenta — Ver que usuario esta conectado\n\n"
    "Personal\n"
    "/personal — Panel personal: jornada, foco, XP y acciones\n"
    "/estado — Estado actual de jornada y tarea\n"
    "/fichar — Fichar entrada\n"
    "/fichar salida — Fichar salida\n"
    "/extras — Iniciar horas extras\n"
    "/extras fin — Finalizar horas extras\n"
    "/score — Tu puntuacion\n"
    "/puntos — Puntos del mes\n"
    "/stats — Estadisticas anuales\n"
    "/historial — Historial de tareas\n\n"
    "Tareas\n"
    "/yarig — Panel de tareas con controles\n"
    "/tarea texto — Añadir tarea directa\n"
    "/tarea Proyecto :: texto — Añadir tarea a proyecto\n"
    "/iniciar — Iniciar o reanudar tarea\n"
    "/pausar — Pausar tarea\n"
    "/finalizar — Completar tarea\n"
    "/random — Mision sugerida por el bot\n"
    "/onboarding — Arranque del dia\n"
    "/offboarding — Cierre del dia\n\n"
    "Equipo\n"
    "/equipo — Panel equipo: actividad, ranking y accesos\n"
    "/equipo_lista — Listado de companeros\n"
    "/ranking — Ranking de productividad\n"
    "/dedicacion — Dedicacion del equipo hoy\n"
    "/pedir nombre texto — Pedir tarea a un companero\n"
    "/peticiones — Bandeja de peticiones\n\n"
    "Finanzas\n"
    "/finanzas — Panel finanzas: facturas, clientes y acciones\n"
    "/clientes — Lista o busca clientes\n"
    "/cliente — Ficha movil de cliente\n"
    "/proyectos Cliente :: — Proyectos de un cliente\n"
    "/tarea Finanzas :: texto — Crear mision financiera\n\n"
    "Marca\n"
    "/marca — Panel marca/RRSS\n"
    "/proyectos Marca :: — Proyectos de marca\n"
    "/tarea Marca :: texto — Crear mision de marca\n"
    "/consulta CCO texto — Consulta creativa al consejo\n\n"
    "Contexto\n"
    "/proyectos — Lista o busca proyectos\n"
    "/proyecto — Ficha movil de proyecto\n"
    "/notificaciones — Avisos recientes\n"
    "/chatid — Id del chat actual\n\n"
    "/help — Esta ayuda"
)


def _current_user_id(update: Update) -> int | None:
    return update.effective_user.id if update.effective_user else None


def _with_user_session(handler):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        token = CURRENT_USER_ID.set(_current_user_id(update))
        try:
            return await handler(update, context)
        finally:
            CURRENT_USER_ID.reset(token)

    return wrapped


def _has_yarig_account(user_id: int | None) -> bool:
    if user_id is not None and user_id in USER_YARIG_CLIENTS:
        return True
    return bool(DEFAULT_YARIG.email and DEFAULT_YARIG.password)


async def _reply_yarig_login_required(update: Update) -> None:
    text = (
        "No hay una cuenta de Yarig.ai conectada en este bot.\n\n"
        "Usa /login y envia tu email y password de Yarig.ai. "
        "Despues podras usar /yarig, /tarea, /personal, /equipo, /finanzas y /marca."
    )
    if update.callback_query:
        await update.callback_query.answer("Conecta Yarig.ai con /login", show_alert=True)
        if update.callback_query.message:
            await update.callback_query.message.reply_text(text, parse_mode=None)
        return
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode=None)


def _with_yarig_account(handler):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = _current_user_id(update)
        token = CURRENT_USER_ID.set(user_id)
        try:
            if not _has_yarig_account(user_id):
                await _reply_yarig_login_required(update)
                return None
            return await handler(update, context)
        finally:
            CURRENT_USER_ID.reset(token)

    return wrapped


def _mask_email(email: str) -> str:
    if "@" not in email:
        return email[:2] + "***" if len(email) > 2 else "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        local_masked = local[:1] + "***"
    else:
        local_masked = local[:2] + "***" + local[-1:]
    return f"{local_masked}@{domain}"

# Conversation state for interactive consejo flow
CONSEJO_AWAITING_TASK = 0


# ── Inline task panel ───────────────────────────────────────


def _task_sort_key(task: dict) -> tuple[int, str]:
    finished = task.get("finished", "0") == "1"
    started = bool(task.get("start_time"))
    ended = bool(task.get("end_time"))
    if started and not ended and not finished:
        rank = 0
    elif not started and not finished:
        rank = 1
    elif started and ended and not finished:
        rank = 2
    else:
        rank = 3
    return rank, str(task.get("description", "")).lower()


def _format_clock_label(start_time: str | None) -> str:
    if not start_time:
        return ""
    raw = str(start_time).strip()
    started_at = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            started_at = datetime.strptime(raw, fmt)
            break
        except ValueError:
            continue
    if started_at is None:
        return ""
    return started_at.strftime("%H:%M")


def _format_elapsed_label(start_time: str | None, end_time: str | None = None) -> str:
    """Return compact elapsed time for a task period."""
    if not start_time:
        return ""
    raw = str(start_time).strip()
    started_at = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            started_at = datetime.strptime(raw, fmt)
            break
        except ValueError:
            continue
    if started_at is None:
        return ""

    if end_time:
        ended_at = None
        raw_end = str(end_time).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                ended_at = datetime.strptime(raw_end, fmt)
                break
            except ValueError:
                continue
    else:
        ended_at = datetime.now()

    if ended_at is None:
        ended_at = datetime.now()

    total_seconds = max(int((ended_at - started_at).total_seconds()), 0)
    total_minutes = max(1, round(total_seconds / 60)) if total_seconds else 0
    hours, minutes = divmod(total_minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m"
    return "<1m"


def _build_task_keyboard(tasks: list[dict]) -> InlineKeyboardMarkup:
    """Build inline keyboard with task controls."""
    rows = []
    indexed_tasks = list(enumerate(tasks, 1))
    indexed_tasks.sort(key=lambda item: _task_sort_key(item[1]))
    for i, task in indexed_tasks:
        desc = task.get("description", "").strip()[:25]
        task_id = str(task.get("id", "")).strip()
        finished = task.get("finished", "0")
        start_time = task.get("start_time")
        started = start_time is not None
        end_time = task.get("end_time")
        active = started and not end_time and finished == "0"
        elapsed = _format_elapsed_label(start_time, end_time)

        if finished == "1":
            duration_label = f" · {elapsed}" if elapsed else ""
            points_label = yarig.get_task_completion_badge(task_id)
            rows.append([InlineKeyboardButton(f"☑ {i}. {desc}{duration_label}{points_label}", callback_data="noop")])
        elif active:
            start_label = _format_clock_label(start_time) or "--:--"
            compact_elapsed = elapsed.replace(" ", "") if elapsed else ""
            pause_label = f"{start_label}⏸{compact_elapsed}" if compact_elapsed else f"{start_label}⏸"
            rows.append([
                InlineKeyboardButton(f"● {i}. {desc}", callback_data="noop"),
                InlineKeyboardButton(pause_label, callback_data=f"yt_pause_{task_id}"),
                InlineKeyboardButton("✓", callback_data=f"yt_finish_{task_id}"),
            ])
        elif started:
            paused_label = f"⏸ {elapsed} · {i}. {desc}" if elapsed else f"⏸ {i}. {desc}"
            rows.append([
                InlineKeyboardButton(paused_label, callback_data="noop"),
                InlineKeyboardButton("☑", callback_data=f"yt_finish_{task_id}"),
                InlineKeyboardButton("▶", callback_data=f"yt_start_{task_id}"),
            ])
        else:
            rows.append([
                InlineKeyboardButton(f"◌ {i}. {desc}", callback_data="noop"),
                InlineKeyboardButton("▶", callback_data=f"yt_start_{task_id}"),
            ])

    rows.append([
        InlineKeyboardButton("↻ Actualizar", callback_data="yt_refresh"),
        InlineKeyboardButton("⌘ Ayuda", callback_data="yt_help"),
    ])
    rows.append([
        InlineKeyboardButton("📥 Peticiones", callback_data="yt_requests"),
        InlineKeyboardButton("🔔 Avisos", callback_data="yt_notifications"),
    ])
    rows.append([
        InlineKeyboardButton("◔ Estado", callback_data="yt_status"),
        InlineKeyboardButton("✦ Resumen", callback_data="yt_digest"),
    ])
    rows.append([
        InlineKeyboardButton("☀️ Onboarding", callback_data="yt_onboarding"),
        InlineKeyboardButton("🌙 Offboarding", callback_data="yt_offboarding"),
    ])
    return InlineKeyboardMarkup(rows)


def _build_project_keyboard(projects: list[dict], token: str) -> InlineKeyboardMarkup:
    """Build inline keyboard to choose a project before creating a task."""
    rows = []
    for project in projects[:6]:
        label = (project.get("label") or project.get("value") or "?").strip()[:32]
        project_id = str(project.get("id", "")).strip()
        rows.append([InlineKeyboardButton(f"▣ {label}", callback_data=f"ytask_pick_{token}_{project_id}")])
    rows.append([InlineKeyboardButton("✕ Cancelar", callback_data=f"ytask_cancel_{token}")])
    return InlineKeyboardMarkup(rows)


def _build_requests_keyboard(requests: list[dict]) -> InlineKeyboardMarkup:
    """Build inline keyboard for unread Yarig requests."""
    rows = []
    for request in requests[:6]:
        request_id = str(request.get("id", "")).strip()
        sender = (request.get("sender") or "Mate").strip()[:18]
        rows.append([
            InlineKeyboardButton(f"✓ {sender}", callback_data=f"yrq_accept_{request_id}"),
            InlineKeyboardButton("◌ Leida", callback_data=f"yrq_read_{request_id}"),
        ])
    rows.append([InlineKeyboardButton("↻ Actualizar", callback_data="yrq_refresh")])
    return InlineKeyboardMarkup(rows)


async def _send_requests_panel(message, edit: bool = False):
    """Send or edit the unread requests panel with inline controls."""
    requests = await yarig.get_unread_requests_data()
    summary = await yarig.get_unread_requests_summary()
    keyboard = _build_requests_keyboard(requests) if requests else InlineKeyboardMarkup(
        [[InlineKeyboardButton("↻ Actualizar", callback_data="yrq_refresh")]]
    )

    if edit:
        await message.edit_text(summary, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await message.reply_text(summary, parse_mode="Markdown", reply_markup=keyboard)


async def _send_yarig_panel(message, edit: bool = False):
    """Send or edit the Yarig task panel with inline controls."""
    data = await yarig.get_today_data()
    if not data:
        text = "No he podido conectar con Yarig.ai ahora mismo."
        if edit:
            await message.edit_text(text)
        else:
            await message.reply_text(text)
        return

    summary = await yarig.get_today_summary()
    tasks = data.get("tasks", [])
    keyboard = _build_task_keyboard(tasks) if tasks else None

    if edit:
        await message.edit_text(summary, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await message.reply_text(summary, parse_mode="Markdown", reply_markup=keyboard)


# ── Callback handlers ───────────────────────────────────────


async def handle_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


async def _send_action_feedback(message, title: str, result: str) -> None:
    await message.reply_text(
        f"✦ *{title}*\n{yarig._esc(result)}",
        parse_mode="Markdown",
    )


async def _build_daily_digest() -> str:
    try:
        status = await yarig.get_status_summary()
        requests = await yarig.get_unread_requests_summary()
        notifications = await yarig.get_notifications()
        return (
            "✦ *Resumen diario Yarig*\n\n"
            f"{status}\n\n"
            f"{requests}\n\n"
            f"{notifications}"
        )
    finally:
        await yarig.close()


async def _post_daily_opening_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not TELEGRAM_DAILY_CHAT_ID:
        return
    try:
        created, task_text = await yarig.ensure_daily_opening_task()
        if created:
            message = (
                "✦ *Mision de arranque creada*\n"
                f"→ _{yarig._esc(task_text)}_"
            )
        else:
            message = (
                "✦ *Mision de arranque ya preparada*\n"
                f"→ _{yarig._esc(task_text)}_"
            )
        await context.bot.send_message(
            chat_id=int(TELEGRAM_DAILY_CHAT_ID),
            text=message,
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info("daily opening task processed", extra={"chat_id": TELEGRAM_DAILY_CHAT_ID, "created": created})
    except Exception as exc:
        logger.warning(f"Daily opening task failed: {exc}")
    finally:
        await yarig.close()


async def _post_daily_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not TELEGRAM_DAILY_CHAT_ID:
        return
    try:
        digest = await _build_daily_digest()
        await context.bot.send_message(
            chat_id=int(TELEGRAM_DAILY_CHAT_ID),
            text=digest,
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info("daily digest sent", extra={"chat_id": TELEGRAM_DAILY_CHAT_ID})
    except Exception as exc:
        logger.warning(f"Daily digest failed: {exc}")


async def _post_evening_inbox_zero(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not TELEGRAM_DAILY_CHAT_ID:
        return
    try:
        created, task = await yarig.ensure_task_for_today("Inbox 0")
        if task and task.get("id"):
            start_result = await yarig.start_task_if_needed(str(task.get("id")))
        else:
            start_result = "⚠️ No he podido arrancar Inbox 0 porque no he encontrado la tarea tras crearla."
        headline = "✦ *Cierre del dia iniciado*"
        task_line = "→ _Inbox 0_"
        created_line = "Nueva mision preparada." if created else "Inbox 0 ya existia para hoy."
        await context.bot.send_message(
            chat_id=int(TELEGRAM_DAILY_CHAT_ID),
            text=(
                f"{headline}\n"
                f"{task_line}\n"
                f"{created_line}\n"
                f"{yarig._esc(start_result)}"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info("daily evening inbox processed", extra={"chat_id": TELEGRAM_DAILY_CHAT_ID, "created": created})
    except Exception as exc:
        logger.warning(f"Daily evening inbox failed: {exc}")
    finally:
        await yarig.close()


async def _post_evening_close_day(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not TELEGRAM_DAILY_CHAT_ID:
        return
    try:
        finish_result = await yarig.close_task_by_description("Inbox 0")
        close_result = await yarig.fichar_salida("Inbox 0")
        await context.bot.send_message(
            chat_id=int(TELEGRAM_DAILY_CHAT_ID),
            text=(
                "✦ *Cierre del dia completado*\n"
                f"→ {yarig._esc(finish_result)}\n"
                f"→ {yarig._esc(close_result)}"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info("daily evening close processed", extra={"chat_id": TELEGRAM_DAILY_CHAT_ID})
    except Exception as exc:
        logger.warning(f"Daily evening close failed: {exc}")
    finally:
        await yarig.close()


async def handle_yarig_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Yarig task control buttons."""
    query = update.callback_query
    action = query.data

    if action == "yt_refresh":
        await query.answer("Actualizando...")
        await _send_yarig_panel(query.message, edit=True)
        return

    if action == "yt_help":
        await query.answer("Mostrando ayuda...")
        await query.message.reply_text(HELP_TEXT, parse_mode=None)
        return

    if action == "yt_requests":
        await query.answer("Abriendo peticiones...")
        await _send_requests_panel(query.message)
        return

    if action == "yt_notifications":
        await query.answer("Cargando avisos...")
        notifications = await yarig.get_notifications()
        await query.message.reply_text(notifications, parse_mode="Markdown")
        return

    if action == "yt_status":
        await query.answer("Cargando estado...")
        status = await yarig.get_status_summary()
        await query.message.reply_text(status, parse_mode="Markdown")
        return

    if action == "yt_digest":
        await query.answer("Preparando resumen...")
        digest = await _build_daily_digest()
        await query.message.reply_text(digest, parse_mode="Markdown")
        return

    if action == "yt_onboarding":
        await query.answer("Ejecutando onboarding...")
        created, task_text = await yarig.ensure_daily_opening_task()
        await yarig.close()
        headline = "✦ *Onboarding ejecutado*"
        if created:
            body = f"→ _{yarig._esc(task_text)}_\nNueva mision de arranque creada."
        else:
            body = f"→ _{yarig._esc(task_text)}_\nLa mision de arranque ya estaba preparada para hoy."
        await query.message.reply_text(f"{headline}\n{body}", parse_mode="Markdown")
        return

    if action == "yt_offboarding":
        await query.answer("Ejecutando offboarding...")
        created, task = await yarig.ensure_task_for_today("Inbox 0")
        if task and task.get("id"):
            start_result = await yarig.start_task_if_needed(str(task.get("id")))
        else:
            start_result = "⚠️ No he podido arrancar Inbox 0 porque no he encontrado la tarea tras crearla."
        finish_result = await yarig.close_task_by_description("Inbox 0")
        close_result = await yarig.fichar_salida("Inbox 0")
        await yarig.close()
        created_line = "Nueva mision preparada." if created else "Inbox 0 ya existia para hoy."
        text = (
            "✦ *Offboarding ejecutado*\n"
            "→ _Inbox 0_\n"
            f"{created_line}\n"
            f"→ {yarig._esc(start_result)}\n"
            f"→ {yarig._esc(finish_result)}\n"
            f"→ {yarig._esc(close_result)}"
        )
        await query.message.reply_text(text, parse_mode="Markdown")
        return

    if action.startswith("yt_pause_"):
        task_id = action.split("_", 2)[-1]
        await query.answer("Mision en pausa")
        result = await yarig.pausar_tarea_por_id(task_id)
        await _send_yarig_panel(query.message, edit=True)
        await _send_action_feedback(query.message, "Mision actualizada", result)
        return

    if action.startswith("yt_start_"):
        task_id = action.split("_", 2)[-1]
        await query.answer("Mision en marcha")
        result = await yarig.iniciar_tarea_por_id(task_id)
        await _send_yarig_panel(query.message, edit=True)
        await _send_action_feedback(query.message, "Movimiento confirmado", result)
        return

    if action.startswith("yt_finish_"):
        task_id = action.split("_", 2)[-1]
        await query.answer("Mision completada")
        result = await yarig.finalizar_tarea_por_id(task_id)
        await _send_yarig_panel(query.message, edit=True)
        await _send_action_feedback(query.message, "Cierre confirmado", result)
        return

    await query.answer()


async def handle_task_project_picker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline project selection for /tarea."""
    query = update.callback_query
    action = query.data

    if action.startswith("ytask_cancel_"):
        token = action.removeprefix("ytask_cancel_")
        PENDING_TASKS.pop(token, None)
        await query.answer("Creación cancelada")
        await query.edit_message_text("Operacion cancelada.")
        return

    if not action.startswith("ytask_pick_"):
        await query.answer()
        return

    payload_token, project_id = action.removeprefix("ytask_pick_").rsplit("_", 1)
    payload = PENDING_TASKS.pop(payload_token, None)
    if not payload:
        await query.answer("Esta tarea ya no está disponible", show_alert=True)
        await query.edit_message_text("La creación de tarea ya no está disponible. Vuelve a usar /tarea.")
        return

    actor_id = update.effective_user.id if update.effective_user else None
    if payload.get("from_user_id") and actor_id != payload["from_user_id"]:
        PENDING_TASKS[payload_token] = payload
        await query.answer("Solo quien lanzó /tarea puede confirmar esta tarea", show_alert=True)
        return

    project = next((p for p in payload.get("projects", []) if str(p.get("id")) == project_id), None)
    project_name = yarig._esc((project or {}).get("label") or (project or {}).get("value") or "Proyecto")

    await query.answer("Creando tarea...")
    result = await yarig.add_task(payload["description"], int(project_id))
    await query.edit_message_text(
        f"{result}\n"
        f"→ Proyecto: *{project_name}*\n"
        f"→ Tarea: _{yarig._esc(payload['description'])}_",
        parse_mode="Markdown",
    )
    await _send_yarig_panel(query.message)


async def handle_requests_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inbox actions for received Yarig requests."""
    query = update.callback_query
    action = query.data

    if action == "yrq_refresh":
        await query.answer("Actualizando bandeja...")
        await _send_requests_panel(query.message, edit=True)
        return

    if action.startswith("yrq_read_"):
        request_id = action.removeprefix("yrq_read_")
        await query.answer("Marcando como leida...")
        result = await yarig.mark_request_state(request_id, 1)
        await query.answer(result)
        await _send_requests_panel(query.message, edit=True)
        return

    if action.startswith("yrq_accept_"):
        request_id = action.removeprefix("yrq_accept_")
        await query.answer("Aceptando peticion...")
        result = await yarig.accept_request(request_id)
        await query.answer(result)
        await _send_requests_panel(query.message, edit=True)
        return

    await query.answer()


async def handle_request_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline priority selection for teammate requests."""
    query = update.callback_query
    action = query.data

    if action.startswith("yreq_cancel_"):
        token = action.removeprefix("yreq_cancel_")
        PENDING_REQUESTS.pop(token, None)
        await query.answer("Peticion cancelada")
        await query.edit_message_text("Operacion cancelada.")
        return

    if not action.startswith("yreq_"):
        await query.answer()
        return

    _, priority_raw, token = action.split("_", 2)
    payload = PENDING_REQUESTS.pop(token, None)
    if not payload:
        await query.answer("Esta petición ya no está disponible", show_alert=True)
        await query.edit_message_text("Esta solicitud ya no esta disponible. Lanza /pedir otra vez.")
        return

    actor_id = update.effective_user.id if update.effective_user else None
    if payload.get("from_user_id") and actor_id != payload["from_user_id"]:
        PENDING_REQUESTS[token] = payload
        await query.answer("Solo quien lanzo /pedir puede confirmar esta peticion", show_alert=True)
        return

    priority = int(priority_raw)
    await query.answer("Enviando peticion...")
    result = await yarig.send_request(payload["user_id"], payload["text"], priority)
    labels = {1: "Sugerencia", 2: "Peticion", 3: "Urgencia"}
    await query.edit_message_text(
        f"{result}\n"
        f"→ Destinatario: *{yarig._esc(payload['name'])}*\n"
        f"→ Tipo: *{labels.get(priority, 'Petición')}*\n"
        f"→ Texto: _{yarig._esc(payload['text'])}_",
        parse_mode="Markdown",
    )


# ── Commands ────────────────────────────────────────────────


async def cmd_yarig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's tasks with inline controls."""
    await _send_yarig_panel(update.message)


async def cmd_fichar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clock in or out."""
    arg = " ".join(context.args).strip().lower() if context.args else ""
    if arg in ("salida", "out", "fin"):
        result = await yarig.fichar_salida()
    else:
        result = await yarig.fichar_entrada()
    await update.message.reply_text(result)


async def cmd_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a plausible random task directly in Yarig.ai."""
    project_term = " ".join(context.args).strip() if context.args else ""
    project = await yarig.find_project(project_term) if project_term else None

    if project_term and not project:
        await update.message.reply_text(f"No encuentro el proyecto '{project_term}'.")
        return

    task_text = random.choice(RANDOM_TASK_TEMPLATES)
    if project:
        result = await yarig.add_task(task_text, int(project["id"]))
        project_name = yarig._esc(project.get("label", project.get("value", "Proyecto")))
    else:
        result = await yarig.add_task(task_text)
        project_name = "Admira"

    await update.message.reply_text(
        f"{result}\n"
        f"→ Proyecto: *{project_name}*\n"
        f"→ Mision sugerida: _{yarig._esc(task_text)}_",
        parse_mode="Markdown",
    )
    await _send_yarig_panel(update.message)


async def cmd_tarea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new task directly, with optional project prefix."""
    if not context.args:
        await update.message.reply_text(
            "Uso: /tarea <descripción>\n"
            "O bien: /tarea <proyecto> :: <descripción>\n"
            "Ejemplo: /tarea Revisar diseño del dashboard\n"
            "Ejemplo: /tarea Memorizer :: Revisar diseño del dashboard"
        )
        return

    raw = " ".join(context.args).strip()
    if "::" in raw:
        project_term, desc = [part.strip() for part in raw.split("::", 1)]
        if not project_term or not desc:
            await update.message.reply_text("Usa el formato /tarea <proyecto> :: <descripcion>.")
            return
        project = await yarig.find_project(project_term)
        if not project:
            await update.message.reply_text(f"No encuentro el proyecto '{project_term}'.")
            return
        result = await yarig.add_task(desc, int(project["id"]))
        project_name = yarig._esc(project.get("label", project.get("value", "Proyecto")))
        await update.message.reply_text(
            f"{result}\n→ Proyecto: *{project_name}*",
            parse_mode="Markdown",
        )
        await _send_yarig_panel(update.message)
        return

    result = await yarig.add_task(raw)
    await update.message.reply_text(result)
    await _send_yarig_panel(update.message)


async def cmd_iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start or resume a task by index."""
    idx = 1
    if context.args:
        try:
            idx = int(context.args[0])
        except ValueError:
            pass
    result = await yarig.iniciar_tarea(idx)
    await update.message.reply_text(result)


async def cmd_pausar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pause the active task."""
    result = await yarig.pausar_tarea()
    await update.message.reply_text(result)


async def cmd_finalizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark task as completed."""
    idx = None
    if context.args:
        try:
            idx = int(context.args[0])
        except ValueError:
            pass
    result = await yarig.finalizar_tarea(idx)
    await update.message.reply_text(result)


async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Yarig score."""
    result = await yarig.get_score()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show compact current status: workday, active task and score."""
    result = await yarig.get_status_summary()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show task history."""
    result = await yarig.get_history()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_notificaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent Yarig notifications."""
    result = await yarig.get_notifications()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_extras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start or stop overtime."""
    arg = " ".join(context.args).strip().lower() if context.args else ""
    if arg in ("fin", "stop", "parar"):
        result = await yarig.extras_fin()
    else:
        result = await yarig.extras_inicio()
    await update.message.reply_text(result)


async def cmd_equipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show team block."""
    result = await yarig.get_team_block()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_equipo_lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show team members."""
    result = await yarig.get_team()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_personal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show personal block."""
    result = await yarig.get_personal_block()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_finanzas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show finance block."""
    result = await yarig.get_finance_block()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_marca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show brand block."""
    result = await yarig.get_brand_block()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show team productivity ranking."""
    result = await yarig.get_ranking()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_dedicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show team dedication for today."""
    result = await yarig.get_dedication()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show annual statistics."""
    result = await yarig.get_stats()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_puntos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show monthly points breakdown."""
    result = await yarig.get_puntos()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_pedir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send task request to a teammate."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /pedir <nombre> <descripción>\n"
            "Ejemplo: /pedir David Revisar el presupuesto Q2"
        )
        return

    name = context.args[0]
    text = " ".join(context.args[1:])

    mate = await yarig.find_mate(name)
    if not mate:
        await update.message.reply_text(f"No encuentro a '{name}' en el equipo.")
        return

    token = secrets.token_urlsafe(6)
    PENDING_REQUESTS[token] = {
        "user_id": str(mate["user_id"]),
        "name": mate["name"],
        "text": text,
        "from_user_id": update.effective_user.id if update.effective_user else None,
    }
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("◌ Sugerencia", callback_data=f"yreq_1_{token}"),
                InlineKeyboardButton("▣ Peticion", callback_data=f"yreq_2_{token}"),
            ],
            [
                InlineKeyboardButton("⚠ Urgencia", callback_data=f"yreq_3_{token}"),
                InlineKeyboardButton("✕ Cancelar", callback_data=f"yreq_cancel_{token}"),
            ],
        ]
    )
    await update.message.reply_text(
        "Selecciona la prioridad antes de enviar la petición:\n"
        f"→ Destinatario: *{yarig._esc(mate['name'])}*\n"
        f"→ Texto: _{yarig._esc(text)}_",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def cmd_peticiones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show unread Yarig requests with inline actions."""
    await _send_requests_panel(update.message)


async def cmd_clientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List customers, optionally filtered."""
    term = " ".join(context.args).strip() if context.args else ""
    result = await yarig.list_customers(term=term)
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show a compact mobile customer profile."""
    term = " ".join(context.args).strip() if context.args else ""
    result = await yarig.get_customer_profile(term)
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_proyectos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List projects, optionally filtered."""
    term = " ".join(context.args).strip() if context.args else ""
    result = await yarig.list_projects(term=term)
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_proyecto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show a compact mobile project profile."""
    term = " ".join(context.args).strip() if context.args else ""
    result = await yarig.get_project_profile(term)
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current chat id for setup/debug."""
    chat = update.effective_chat
    user = update.effective_user
    title = getattr(chat, "title", None) or getattr(chat, "full_name", None) or getattr(chat, "username", None) or "chat"
    who = getattr(user, "full_name", None) or getattr(user, "username", None) or "usuario"
    logger.info(f"chatid command: title={title} chat_id={chat.id} user={who}")
    await update.message.reply_text(
        f"Chat: {title}\\n"
        f"chat_id: {chat.id}\\n"
        f"usuario: {who}"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help."""
    await update.message.reply_text(HELP_TEXT, parse_mode=None)


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start Yarig.ai login flow for this Telegram user."""
    user_id = _current_user_id(update)
    if user_id is None:
        await update.message.reply_text("No puedo identificar tu usuario de Telegram en este chat.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Vamos a conectar tu usuario de Yarig.ai.\n\n"
        "Enviame tu email de Yarig.ai. Puedes cancelar con /cancelar.",
        parse_mode=None,
    )
    return LOGIN_EMAIL


async def process_login_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the email temporarily and ask for password."""
    user_id = _current_user_id(update)
    email = (update.message.text or "").strip() if update.message else ""
    if user_id is None or not email or "@" not in email:
        await update.message.reply_text("Ese email no parece valido. Enviame el email de Yarig.ai o /cancelar.")
        return LOGIN_EMAIL
    PENDING_LOGIN_EMAIL[user_id] = email
    await update.message.reply_text(
        f"Email recibido: {_mask_email(email)}\n\n"
        "Ahora enviame la password de Yarig.ai. La pruebo contra Yarig.ai y no la escribo en disco.",
        parse_mode=None,
    )
    return LOGIN_PASSWORD


async def process_login_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate credentials against Yarig.ai and keep an in-memory client."""
    user_id = _current_user_id(update)
    password = (update.message.text or "").strip() if update.message else ""
    email = PENDING_LOGIN_EMAIL.pop(user_id, "") if user_id is not None else ""
    if user_id is None or not email or not password:
        await update.message.reply_text("No he podido completar el login. Usa /login otra vez.")
        return ConversationHandler.END

    try:
        await update.message.delete()
    except Exception:
        pass

    await update.effective_chat.send_message("Probando credenciales con Yarig.ai...", parse_mode=None)
    client = YarigClient(email=email, password=password)
    if not await client.login():
        await client.close()
        await update.effective_chat.send_message(
            "No he podido entrar en Yarig.ai con esas credenciales. Usa /login para intentarlo de nuevo.",
            parse_mode=None,
        )
        return ConversationHandler.END

    old_client = USER_YARIG_CLIENTS.pop(user_id, None)
    if old_client:
        await old_client.close()
    USER_YARIG_CLIENTS[user_id] = client
    await update.effective_chat.send_message(
        f"Sesion conectada para {_mask_email(email)}.\n"
        "Ya puedes usar /tarea, /yarig, /fichar y el resto de comandos con tu usuario.",
        parse_mode=None,
    )
    return ConversationHandler.END


async def cmd_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close this Telegram user's Yarig session."""
    user_id = _current_user_id(update)
    client = USER_YARIG_CLIENTS.pop(user_id, None) if user_id is not None else None
    PENDING_LOGIN_EMAIL.pop(user_id, None) if user_id is not None else None
    if client:
        await client.close()
        await update.message.reply_text("Sesion de Yarig.ai cerrada en este bot.", parse_mode=None)
        return
    await update.message.reply_text("No habia una sesion personalizada abierta. Usa /login para conectar.", parse_mode=None)


async def cmd_cuenta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the current Telegram user's Yarig session status."""
    user_id = _current_user_id(update)
    client = USER_YARIG_CLIENTS.get(user_id) if user_id is not None else None
    if client:
        await update.message.reply_text(f"Conectado como {_mask_email(client.email)}.", parse_mode=None)
        return
    if DEFAULT_YARIG.email:
        await update.message.reply_text(
            f"Usando la cuenta por defecto del bot: {_mask_email(DEFAULT_YARIG.email)}.\n"
            "Usa /login para conectar tu propio usuario.",
            parse_mode=None,
        )
        return
    await update.message.reply_text("No hay cuenta Yarig.ai conectada. Usa /login.", parse_mode=None)


async def cmd_mision_dia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create the opening mission for today on demand."""
    created, task_text = await yarig.ensure_daily_opening_task()
    await yarig.close()
    if created:
        text = f"✦ *Mision de arranque creada*\n→ _{yarig._esc(task_text)}_"
    else:
        text = f"✦ *Mision de arranque ya preparada*\n→ _{yarig._esc(task_text)}_"
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run the morning onboarding flow manually."""
    created, task_text = await yarig.ensure_daily_opening_task()
    await yarig.close()
    headline = "✦ *Onboarding ejecutado*"
    if created:
        body = f"→ _{yarig._esc(task_text)}_\nNueva mision de arranque creada."
    else:
        body = f"→ _{yarig._esc(task_text)}_\nLa mision de arranque ya estaba preparada para hoy."
    await update.message.reply_text(f"{headline}\n{body}", parse_mode="Markdown")


async def cmd_offboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run the evening offboarding flow manually."""
    created, task = await yarig.ensure_task_for_today("Inbox 0")
    if task and task.get("id"):
        start_result = await yarig.start_task_if_needed(str(task.get("id")))
    else:
        start_result = "⚠️ No he podido arrancar Inbox 0 porque no he encontrado la tarea tras crearla."
    finish_result = await yarig.close_task_by_description("Inbox 0")
    close_result = await yarig.fichar_salida("Inbox 0")
    await yarig.close()
    created_line = "Nueva mision preparada." if created else "Inbox 0 ya existia para hoy."
    text = (
        "✦ *Offboarding ejecutado*\n"
        "→ _Inbox 0_\n"
        f"{created_line}\n"
        f"→ {yarig._esc(start_result)}\n"
        f"→ {yarig._esc(finish_result)}\n"
        f"→ {yarig._esc(close_result)}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_resumen_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the daily digest on demand."""
    digest = await _build_daily_digest()
    await update.message.reply_text(digest, parse_mode="Markdown")


# ── Consejo de Administracion ──────────────────────────────


async def cmd_consejo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the board table with inline controls."""
    table = build_board_table()
    keyboard = build_board_keyboard()
    await update.message.reply_text(table, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct dispatch: /consulta <target> <tarea>."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /consulta <target> <tarea>\n\n"
            "Targets validos:\n"
            "• `consejo` — los 8 consejeros\n"
            "• `operativo` — CEO, CFO, COO, CTO\n"
            "• `creativo` — CCO, CSO, CXO, CDO\n"
            "• `pareja:CEO` — pareja coetanea\n"
            "• `CEO`, `CTO`, etc. — silla individual\n\n"
            "Ejemplo: /consulta operativo Revisar el presupuesto Q2",
            parse_mode="Markdown",
        )
        return

    target = context.args[0]
    task = " ".join(context.args[1:])

    try:
        members = resolve_target(target)
    except ValueError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return

    await update.message.reply_text(f"🏛 Consultando al consejo... ({len(members)} miembros)")

    results, acta_num = await dispatch_task(members, task, target)
    messages = assemble_full_response(target, task, results)
    for msg in messages:
        await update.message.reply_text(msg, parse_mode="Markdown")

    chat_id = update.message.chat_id
    roles = [m.role for m in members]
    resp_map = {m.role: r for m, r in results}
    notified = await notify_consejero_bots(roles, task, chat_id, resp_map)
    if notified:
        await update.message.reply_text(
            f"📜 Acta *#{acta_num}* | Notificados: {', '.join(notified)}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(f"📜 Guardado como acta *#{acta_num}*", parse_mode="Markdown")


async def consejo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle inline button press from /consejo — select target, then ask for task."""
    query = update.callback_query
    await query.answer()

    target = query.data.replace("consejo:", "", 1)
    context.user_data["consejo_target"] = target

    label = format_target_label(target)
    await query.message.reply_text(
        f"Has seleccionado: *{label}*\n\n"
        "Escribe la tarea o pregunta para el consejo:\n"
        "(o /cancelar para anular)",
        parse_mode="Markdown",
    )
    return CONSEJO_AWAITING_TASK


async def process_consejo_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the task text after target selection."""
    target = context.user_data.get("consejo_target")
    if not target:
        await update.message.reply_text("⚠️ No hay target seleccionado. Usa /consejo para empezar.")
        return ConversationHandler.END

    task = update.message.text.strip()
    if not task:
        await update.message.reply_text("⚠️ Escribe una tarea o pregunta.")
        return CONSEJO_AWAITING_TASK

    try:
        members = resolve_target(target)
    except ValueError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return ConversationHandler.END

    await update.message.reply_text(f"🏛 Consultando al consejo... ({len(members)} miembros)")

    results, acta_num = await dispatch_task(members, task, target)
    messages = assemble_full_response(target, task, results)
    for msg in messages:
        await update.message.reply_text(msg, parse_mode="Markdown")

    chat_id = update.message.chat_id
    roles = [m.role for m in members]
    resp_map = {m.role: r for m, r in results}
    notified = await notify_consejero_bots(roles, task, chat_id, resp_map)
    if notified:
        await update.message.reply_text(
            f"📜 Acta *#{acta_num}* | Notificados: {', '.join(notified)}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(f"📜 Guardado como acta *#{acta_num}*", parse_mode="Markdown")

    context.user_data.pop("consejo_target", None)
    return ConversationHandler.END


async def cmd_actas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent board consultations."""
    actas = get_recent_actas(limit=10)
    text = format_actas_list(actas)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_acta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detail of a specific acta."""
    if not context.args:
        await update.message.reply_text("Uso: /acta <numero>\nEjemplo: /acta 3")
        return
    try:
        num = int(context.args[0])
    except ValueError:
        await update.message.reply_text("El numero de acta debe ser un entero.")
        return

    acta = get_acta(num)
    if not acta:
        await update.message.reply_text(f"No existe el acta #{num}.")
        return

    text = format_acta_detail(acta)
    if len(text) <= 3800:
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        parts = text.split("\n" + "─" * 30)
        for part in parts:
            if part.strip():
                await update.message.reply_text(part.strip(), parse_mode="Markdown")


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel an in-progress conversation."""
    context.user_data.pop("consejo_target", None)
    user_id = _current_user_id(update)
    if user_id is not None:
        PENDING_LOGIN_EMAIL.pop(user_id, None)
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


# ── Main ────────────────────────────────────────────────────


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set. Check your .env file.")

    defaults = Defaults(tzinfo=MADRID_TZ)
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).defaults(defaults).build()

    login_conv = ConversationHandler(
        entry_points=[CommandHandler("login", _with_user_session(cmd_login))],
        states={
            LOGIN_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _with_user_session(process_login_email)),
            ],
            LOGIN_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _with_user_session(process_login_password)),
            ],
        },
        fallbacks=[CommandHandler("cancelar", _with_user_session(cmd_cancelar))],
        per_user=True,
        per_chat=True,
        name="yarig_login_conversation",
    )
    app.add_handler(login_conv)

    # Commands
    app.add_handler(CommandHandler("yarig", _with_yarig_account(cmd_yarig)))
    app.add_handler(CommandHandler("fichar", _with_yarig_account(cmd_fichar)))
    app.add_handler(CommandHandler("tarea", _with_yarig_account(cmd_tarea)))
    app.add_handler(CommandHandler("random", _with_yarig_account(cmd_random)))
    app.add_handler(CommandHandler("iniciar", _with_yarig_account(cmd_iniciar)))
    app.add_handler(CommandHandler("pausar", _with_yarig_account(cmd_pausar)))
    app.add_handler(CommandHandler("finalizar", _with_yarig_account(cmd_finalizar)))
    app.add_handler(CommandHandler("estado", _with_yarig_account(cmd_estado)))
    app.add_handler(CommandHandler("personal", _with_yarig_account(cmd_personal)))
    app.add_handler(CommandHandler("score", _with_yarig_account(cmd_score)))
    app.add_handler(CommandHandler("historial", _with_yarig_account(cmd_historial)))
    app.add_handler(CommandHandler("notificaciones", _with_yarig_account(cmd_notificaciones)))
    app.add_handler(CommandHandler("extras", _with_yarig_account(cmd_extras)))
    app.add_handler(CommandHandler("equipo", _with_yarig_account(cmd_equipo)))
    app.add_handler(CommandHandler("equipo_lista", _with_yarig_account(cmd_equipo_lista)))
    app.add_handler(CommandHandler("finanzas", _with_yarig_account(cmd_finanzas)))
    app.add_handler(CommandHandler("marca", _with_yarig_account(cmd_marca)))
    app.add_handler(CommandHandler("ranking", _with_yarig_account(cmd_ranking)))
    app.add_handler(CommandHandler("dedicacion", _with_yarig_account(cmd_dedicacion)))
    app.add_handler(CommandHandler("stats", _with_yarig_account(cmd_stats)))
    app.add_handler(CommandHandler("puntos", _with_yarig_account(cmd_puntos)))
    app.add_handler(CommandHandler("pedir", _with_yarig_account(cmd_pedir)))
    app.add_handler(CommandHandler("peticiones", _with_yarig_account(cmd_peticiones)))
    app.add_handler(CommandHandler("clientes", _with_yarig_account(cmd_clientes)))
    app.add_handler(CommandHandler("cliente", _with_yarig_account(cmd_cliente)))
    app.add_handler(CommandHandler("proyectos", _with_yarig_account(cmd_proyectos)))
    app.add_handler(CommandHandler("proyecto", _with_yarig_account(cmd_proyecto)))
    app.add_handler(CommandHandler("chatid", _with_user_session(cmd_chatid)))
    app.add_handler(CommandHandler("logout", _with_user_session(cmd_logout)))
    app.add_handler(CommandHandler("cuenta", _with_user_session(cmd_cuenta)))
    app.add_handler(CommandHandler("help", _with_user_session(cmd_help)))
    app.add_handler(CommandHandler("start", _with_user_session(cmd_help)))
    app.add_handler(CommandHandler("resumen_diario", _with_yarig_account(cmd_resumen_diario)))
    app.add_handler(CommandHandler("mision_dia", _with_yarig_account(cmd_mision_dia)))
    app.add_handler(CommandHandler("onboarding", _with_yarig_account(cmd_onboarding)))
    app.add_handler(CommandHandler("offboarding", _with_yarig_account(cmd_offboarding)))

    # Consejo de Administracion
    app.add_handler(CommandHandler("consejo", _with_user_session(cmd_consejo)))
    app.add_handler(CommandHandler("consulta", _with_user_session(cmd_consulta)))
    app.add_handler(CommandHandler("actas", _with_user_session(cmd_actas)))
    app.add_handler(CommandHandler("acta", _with_user_session(cmd_acta)))
    consejo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(_with_user_session(consejo_callback), pattern=r"^consejo:")],
        states={
            CONSEJO_AWAITING_TASK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _with_user_session(process_consejo_task)),
            ],
        },
        fallbacks=[CommandHandler("cancelar", _with_user_session(cmd_cancelar))],
        per_user=True,
        per_chat=True,
        name="consejo_conversation",
    )
    app.add_handler(consejo_conv)

    # Callbacks
    app.add_handler(CallbackQueryHandler(_with_yarig_account(handle_yarig_control), pattern="^yt_"))
    app.add_handler(CallbackQueryHandler(_with_yarig_account(handle_request_priority), pattern="^yreq_"))
    app.add_handler(CallbackQueryHandler(_with_yarig_account(handle_requests_inbox), pattern="^yrq_"))
    app.add_handler(CallbackQueryHandler(_with_yarig_account(handle_task_project_picker), pattern="^ytask_"))
    app.add_handler(CallbackQueryHandler(_with_user_session(handle_noop), pattern="^noop$"))

    async def _shutdown(_: Application) -> None:
        await yarig.close()

    app.post_shutdown = _shutdown

    job_queue = app.job_queue
    if job_queue is not None and TELEGRAM_DAILY_CHAT_ID:
        job_queue.run_daily(
            _post_daily_opening_task,
            time=dtime(hour=8, minute=0, tzinfo=MADRID_TZ),
            name="yarig_daily_opening_task",
        )
        job_queue.run_daily(
            _post_daily_digest,
            time=dtime(hour=9, minute=0, tzinfo=MADRID_TZ),
            name="yarig_daily_digest",
        )
        job_queue.run_daily(
            _post_evening_inbox_zero,
            time=dtime(hour=20, minute=0, tzinfo=MADRID_TZ),
            name="yarig_evening_inbox_zero",
        )
        job_queue.run_daily(
            _post_evening_close_day,
            time=dtime(hour=20, minute=30, tzinfo=MADRID_TZ),
            name="yarig_evening_close_day",
        )

    logger.info("Yarig.Telegram bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
