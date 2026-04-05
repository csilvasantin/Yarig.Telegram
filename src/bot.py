"""Yarig.Telegram — Control completo de Yarig.ai desde Telegram."""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from src.config import TELEGRAM_BOT_TOKEN
from src.yarig import YarigClient
from src.consejo import (
    build_board_table,
    build_board_keyboard,
    resolve_target,
    dispatch_task,
    assemble_full_response,
    format_target_label,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

yarig = YarigClient()

# Conversation state for interactive consejo flow
CONSEJO_AWAITING_TASK = 0


# ── Inline task panel ───────────────────────────────────────


def _build_task_keyboard(tasks: list[dict]) -> InlineKeyboardMarkup:
    """Build inline keyboard with task controls."""
    rows = []
    for i, task in enumerate(tasks, 1):
        desc = task.get("description", "").strip()[:25]
        finished = task.get("finished", "0")
        started = task.get("start_time") is not None
        active = started and not task.get("end_time") and finished == "0"

        if finished == "1":
            rows.append([InlineKeyboardButton(f"✅ {i}. {desc}", callback_data="noop")])
        elif active:
            rows.append([
                InlineKeyboardButton(f"▶️ {i}. {desc}", callback_data="noop"),
                InlineKeyboardButton("⏸", callback_data="yt_pause"),
                InlineKeyboardButton("✅", callback_data=f"yt_finish_{i}"),
            ])
        elif started:
            rows.append([
                InlineKeyboardButton(f"⏸ {i}. {desc}", callback_data="noop"),
                InlineKeyboardButton("▶️", callback_data=f"yt_start_{i}"),
                InlineKeyboardButton("✅", callback_data=f"yt_finish_{i}"),
            ])
        else:
            rows.append([
                InlineKeyboardButton(f"⏳ {i}. {desc}", callback_data="noop"),
                InlineKeyboardButton("▶️", callback_data=f"yt_start_{i}"),
            ])

    rows.append([InlineKeyboardButton("🔄 Actualizar", callback_data="yt_refresh")])
    return InlineKeyboardMarkup(rows)


async def _send_yarig_panel(message, edit: bool = False):
    """Send or edit the Yarig task panel with inline controls."""
    data = await yarig.get_today_data()
    if not data:
        text = "No se pudo conectar con Yarig.ai"
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


async def handle_yarig_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Yarig task control buttons."""
    query = update.callback_query
    action = query.data

    if action == "yt_refresh":
        await query.answer("Actualizando...")
        await _send_yarig_panel(query.message, edit=True)
        return

    if action == "yt_pause":
        await query.answer("Pausando tarea...")
        await yarig.pausar_tarea()
        await _send_yarig_panel(query.message, edit=True)
        return

    if action.startswith("yt_start_"):
        idx = int(action.split("_")[-1])
        await query.answer("Iniciando tarea...")
        await yarig.iniciar_tarea(idx)
        await _send_yarig_panel(query.message, edit=True)
        return

    if action.startswith("yt_finish_"):
        idx = int(action.split("_")[-1])
        await query.answer("Finalizando tarea...")
        await yarig.finalizar_tarea(idx)
        await _send_yarig_panel(query.message, edit=True)
        return

    await query.answer()


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


async def cmd_tarea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new task."""
    if not context.args:
        await update.message.reply_text("Uso: /tarea <descripción>\nEjemplo: /tarea Revisar diseño del dashboard")
        return
    desc = " ".join(context.args)
    result = await yarig.add_task(desc)
    await update.message.reply_text(result)


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


async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show task history."""
    result = await yarig.get_history()
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
    """Show team members."""
    result = await yarig.get_team()
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
        await update.message.reply_text(f"No encontré a '{name}' en el equipo")
        return

    result = await yarig.send_request(mate["user_id"], text)
    await update.message.reply_text(f"{result}\n→ Enviada a *{mate['name']}*", parse_mode="Markdown")


async def cmd_proyectos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List projects."""
    result = await yarig.list_projects()
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help."""
    text = (
        "📋 *Yarig.Telegram*\n"
        "Control de Yarig.ai desde Telegram\n\n"
        "*Tareas*\n"
        "/yarig — Panel de tareas con controles\n"
        "/tarea <desc> — Añadir tarea\n"
        "/iniciar [n] — Iniciar o reanudar tarea\n"
        "/pausar — Pausar tarea (dejar para luego)\n"
        "/finalizar [n] — Completar tarea\n\n"
        "*Jornada*\n"
        "/fichar — Fichar entrada\n"
        "/fichar salida — Fichar salida\n"
        "/extras — Iniciar horas extras\n"
        "/extras fin — Finalizar horas extras\n\n"
        "*Equipo*\n"
        "/score — Tu puntuación\n"
        "/equipo — Miembros del equipo\n"
        "/pedir <nombre> <tarea> — Pedir tarea\n"
        "/proyectos — Lista de proyectos\n"
        "/historial — Historial de tareas\n\n"
        "*Consejo de Administracion*\n"
        "/consejo — Mesa del consejo con controles\n"
        "/consulta <target> <tarea> — Consultar al consejo\n"
        "  Targets: consejo, operativo, creativo, pareja:ROL, ROL\n\n"
        "/help — Esta ayuda"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── Consejo de Administracion ──────────────────────────────


async def cmd_consejo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the board table with inline controls."""
    table = build_board_table()
    keyboard = build_board_keyboard()
    await update.message.reply_text(table, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct dispatch: /consulta <target> <tarea>"""
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

    await update.message.reply_text(
        f"🏛 Consultando al consejo... ({len(members)} miembros)"
    )

    results = await dispatch_task(members, task)
    messages = assemble_full_response(target, task, results)
    for msg in messages:
        await update.message.reply_text(msg, parse_mode="Markdown")


async def consejo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle inline button press from /consejo — select target, then ask for task."""
    query = update.callback_query
    await query.answer()

    target = query.data.replace("consejo:", "", 1)
    context.user_data["consejo_target"] = target

    label = format_target_label(target)
    await query.message.reply_text(
        f"Has seleccionado: *{label}*\n\n"
        f"Escribe la tarea o pregunta para el consejo:\n"
        f"(o /cancelar para anular)",
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

    await update.message.reply_text(
        f"🏛 Consultando al consejo... ({len(members)} miembros)"
    )

    results = await dispatch_task(members, task)
    messages = assemble_full_response(target, task, results)
    for msg in messages:
        await update.message.reply_text(msg, parse_mode="Markdown")

    context.user_data.pop("consejo_target", None)
    return ConversationHandler.END


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel an in-progress consejo consultation."""
    context.user_data.pop("consejo_target", None)
    await update.message.reply_text("Consulta cancelada.")
    return ConversationHandler.END


# ── Main ────────────────────────────────────────────────────


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set. Check your .env file.")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("yarig", cmd_yarig))
    app.add_handler(CommandHandler("fichar", cmd_fichar))
    app.add_handler(CommandHandler("tarea", cmd_tarea))
    app.add_handler(CommandHandler("iniciar", cmd_iniciar))
    app.add_handler(CommandHandler("pausar", cmd_pausar))
    app.add_handler(CommandHandler("finalizar", cmd_finalizar))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CommandHandler("historial", cmd_historial))
    app.add_handler(CommandHandler("extras", cmd_extras))
    app.add_handler(CommandHandler("equipo", cmd_equipo))
    app.add_handler(CommandHandler("pedir", cmd_pedir))
    app.add_handler(CommandHandler("proyectos", cmd_proyectos))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))

    # Consejo de Administracion
    app.add_handler(CommandHandler("consejo", cmd_consejo))
    app.add_handler(CommandHandler("consulta", cmd_consulta))
    consejo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(consejo_callback, pattern=r"^consejo:")],
        states={
            CONSEJO_AWAITING_TASK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_consejo_task),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cmd_cancelar)],
        per_user=True,
        per_chat=True,
        name="consejo_conversation",
    )
    app.add_handler(consejo_conv)

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_yarig_control, pattern="^yt_"))
    app.add_handler(CallbackQueryHandler(handle_noop, pattern="^noop$"))

    logger.info("Yarig.Telegram bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
