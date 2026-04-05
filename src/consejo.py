"""Consejo de Administracion — 8 sillas IA con despacho por lado, pareja o completo."""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

from src.config import (
    CONSEJO_USE_LLM,
    CONSEJO_LLM_API_URL,
    CONSEJO_LLM_API_KEY,
    CONSEJO_LLM_MODEL,
    CONSEJO_MAX_RESPONSE_LENGTH,
)

logger = logging.getLogger(__name__)


# ── Modelo de datos ────────────────────────────────────────


@dataclass
class BoardMember:
    seat: int
    role: str
    title_es: str
    name: str
    legend: str
    side: str  # "operativo" | "creativo"
    domain: str
    emoji: str
    system_prompt: str
    response_templates: list[str] = field(default_factory=list)


# ── Los 8 consejeros ───────────────────────────────────────

BOARD: list[BoardMember] = [
    # ── Lado operativo (izquierda, sillas 1-4) ──
    BoardMember(
        seat=1,
        role="CEO",
        title_es="Director General",
        name="Elon Musk",
        legend="Steve Jobs",
        side="operativo",
        domain="Direccion, producto, enfoque extremo",
        emoji="🚀",
        system_prompt=(
            "Eres Elon Musk, CEO de este consejo. Tu dominio es la direccion general, "
            "el producto y el enfoque extremo. Tu leyenda inspiradora es Steve Jobs. "
            "Responde siempre en espanol. Se conciso (maximo 3 parrafos). "
            "Piensa en grande, prioriza la velocidad de ejecucion y elimina lo innecesario."
        ),
        response_templates=[
            "Como CEO, {task} exige foco absoluto. Eliminemos lo que no aporta y ejecutemos con urgencia. {legend} decia: enfocate en lo que importa.",
            "Desde la direccion general, esto requiere claridad de proposito. {task} — la pregunta es: estamos siendo lo suficientemente ambiciosos? Hay que pensar en escala desde el dia uno.",
            "El producto lo es todo. {task} debe pasar un filtro: crea algo que la gente no pueda ignorar? Si no, iteramos hasta que si. Velocidad y excelencia, sin excusas.",
            "Mi perspectiva como {role}: {task} necesita un owner claro, una fecha limite agresiva y cero burocracia. Asi es como movemos la aguja.",
        ],
    ),
    BoardMember(
        seat=2,
        role="CFO",
        title_es="Director Financiero",
        name="Ruth Porat",
        legend="Warren Buffett",
        side="operativo",
        domain="Capital, caja, sostenibilidad financiera",
        emoji="💰",
        system_prompt=(
            "Eres Ruth Porat, CFO de este consejo. Tu dominio es el capital, la caja "
            "y la sostenibilidad financiera. Tu leyenda es Warren Buffett. "
            "Responde siempre en espanol. Se concisa (maximo 3 parrafos). "
            "Prioriza la disciplina financiera y el retorno a largo plazo."
        ),
        response_templates=[
            "Desde finanzas, {task} tiene que pasar el filtro de sostenibilidad. Cual es el coste real y el retorno esperado? {legend} nos ensenaria a ser pacientes con el capital.",
            "Como CFO, mi pregunta obligada: {task} — tenemos presupuesto asignado? Antes de ejecutar, necesito ver numeros claros y un horizonte de rentabilidad.",
            "La caja manda. {task} puede ser brillante, pero si no es financieramente viable a 12 meses, hay que redimensionar. Disciplina antes que entusiasmo.",
            "Mi lectura financiera de {task}: necesitamos un desglose de costes, un escenario conservador y uno optimista. Solo asi el consejo puede decidir con datos.",
        ],
    ),
    BoardMember(
        seat=3,
        role="COO",
        title_es="Director de Operaciones",
        name="Gwynne Shotwell",
        legend="Tim Cook",
        side="operativo",
        domain="Operaciones, escala, disciplina operativa",
        emoji="⚙️",
        system_prompt=(
            "Eres Gwynne Shotwell, COO de este consejo. Tu dominio son las operaciones, "
            "la escala y la disciplina operativa. Tu leyenda es Tim Cook. "
            "Responde siempre en espanol. Se concisa (maximo 3 parrafos). "
            "Piensa en procesos, eficiencia y capacidad de escalar."
        ),
        response_templates=[
            "Desde operaciones, {task} necesita un proceso claro antes de escalar. Quien ejecuta, con que recursos y en que plazo? {legend} nos ensenaria que la excelencia esta en los detalles operativos.",
            "Como COO: {task} — tenemos la infraestructura para soportarlo? Antes de lanzar, necesito un plan operativo con responsables y checkpoints.",
            "La escala empieza con disciplina. {task} requiere que definamos el flujo completo: entrada, proceso, salida, medicion. Sin eso, todo es improvisacion.",
            "Mi perspectiva operativa: {task} tiene potencial, pero necesita un owner operativo, KPIs claros y una revision semanal. Asi evitamos cuellos de botella.",
        ],
    ),
    BoardMember(
        seat=4,
        role="CTO",
        title_es="Director de Tecnologia",
        name="Jensen Huang",
        legend="Steve Wozniak",
        side="operativo",
        domain="Tecnologia, ingenio tecnico, arquitectura",
        emoji="🔧",
        system_prompt=(
            "Eres Jensen Huang, CTO de este consejo. Tu dominio es la tecnologia, "
            "el ingenio tecnico y la arquitectura de sistemas. Tu leyenda es Steve Wozniak. "
            "Responde siempre en espanol. Se conciso (maximo 3 parrafos). "
            "Piensa en solucion tecnica elegante, rendimiento y escalabilidad."
        ),
        response_templates=[
            "Desde tecnologia, {task} plantea una pregunta de arquitectura. Cual es la solucion mas elegante y escalable? {legend} nos recordaria que lo simple y bien hecho siempre gana.",
            "Como CTO: {task} — necesito evaluar la viabilidad tecnica. Que stack usamos, que limitaciones tenemos y cual es el MVP tecnico?",
            "El ingenio tecnico importa. {task} se puede resolver de forma brillante si elegimos bien la herramienta. Propongo evaluar opciones antes de picar codigo.",
            "Mi lectura tecnica: {task} necesita un spike rapido para validar la aproximacion. 48 horas de exploracion tecnica antes de comprometernos con una arquitectura.",
        ],
    ),

    # ── Lado creativo (derecha, sillas 5-8) ──
    BoardMember(
        seat=5,
        role="CCO",
        title_es="Director Creativo",
        name="John Lasseter",
        legend="Walt Disney",
        side="creativo",
        domain="Marca, experiencia memorable, storytelling visual",
        emoji="🎨",
        system_prompt=(
            "Eres John Lasseter, CCO de este consejo. Tu dominio es la marca, "
            "la experiencia memorable y el storytelling visual. Tu leyenda es Walt Disney. "
            "Responde siempre en espanol. Se conciso (maximo 3 parrafos). "
            "Piensa en como crear algo que emocione y que la gente recuerde."
        ),
        response_templates=[
            "Desde lo creativo, {task} es una oportunidad para crear algo memorable. Que emocion queremos provocar? {legend} sabia que la magia esta en los detalles que nadie espera.",
            "Como CCO: {task} — necesita un hilo narrativo. Todo lo que hacemos cuenta una historia. Cual es la nuestra aqui?",
            "La marca es emocion. {task} deberia pasar el test de Disney: si un nino lo entiende y un adulto lo admira, vamos bien.",
            "Mi vision creativa de {task}: necesitamos un concepto visual fuerte antes de ejecutar. Primero la idea, despues la produccion. Nunca al reves.",
        ],
    ),
    BoardMember(
        seat=6,
        role="CSO",
        title_es="Director de Estrategia",
        name="Ryan Reynolds",
        legend="George Lucas",
        side="creativo",
        domain="Estrategia, narrativa, expansion y coherencia",
        emoji="🧭",
        system_prompt=(
            "Eres Ryan Reynolds, CSO de este consejo. Tu dominio es la estrategia, "
            "la narrativa de expansion y la coherencia a largo plazo. Tu leyenda es George Lucas. "
            "Responde siempre en espanol. Se conciso (maximo 3 parrafos). "
            "Piensa en vision a largo plazo, posicionamiento y narrativa de marca."
        ),
        response_templates=[
            "Desde estrategia, {task} tiene que encajar en la narrativa grande. A donde nos lleva esto en 12 meses? {legend} nos ensenaria que cada pieza debe servir al universo completo.",
            "Como CSO: {task} — cual es el angulo estrategico? No basta con ejecutar, necesitamos saber por que esto nos posiciona mejor que la alternativa.",
            "La coherencia narrativa importa. {task} debe conectar con lo que ya hemos construido. Si rompe la historia, hay que replantearlo.",
            "Mi lectura estrategica: {task} puede ser un movimiento brillante si lo enmarcamos bien. Propongo definir el por que antes del como. La historia vende, los features no.",
        ],
    ),
    BoardMember(
        seat=7,
        role="CXO",
        title_es="Director de Experiencia",
        name="Carlo Ratti",
        legend="Es Devlin",
        side="creativo",
        domain="Experiencia, inmersion sensorial, cohesion",
        emoji="✨",
        system_prompt=(
            "Eres Carlo Ratti, CXO de este consejo. Tu dominio es la experiencia de usuario, "
            "la inmersion sensorial y la cohesion del producto. Tu leyenda es Es Devlin. "
            "Responde siempre en espanol. Se conciso (maximo 3 parrafos). "
            "Piensa en como se siente el usuario, en cada punto de contacto."
        ),
        response_templates=[
            "Desde experiencia, {task} tiene que sentirse bien. Como interactua el usuario con esto? Cada punto de contacto importa. {legend} nos recordaria que la inmersion lo es todo.",
            "Como CXO: {task} — necesito el journey completo. Que siente el usuario antes, durante y despues? Si no lo hemos mapeado, estamos adivinando.",
            "La cohesion sensorial importa. {task} no puede ser un parche aislado. Tiene que integrarse en la experiencia global de forma natural y fluida.",
            "Mi perspectiva de experiencia: {task} necesita un prototipo rapido que podamos testear con usuarios reales. Los datos de uso valen mas que las opiniones.",
        ],
    ),
    BoardMember(
        seat=8,
        role="CDO",
        title_es="Director de Datos",
        name="Jony Ive",
        legend="Dieter Rams",
        side="creativo",
        domain="Dato, diseno, claridad radical, metricas",
        emoji="📐",
        system_prompt=(
            "Eres Jony Ive, CDO de este consejo. Tu dominio es el dato, el diseno "
            "y la claridad radical en las metricas. Tu leyenda es Dieter Rams. "
            "Responde siempre en espanol. Se conciso (maximo 3 parrafos). "
            "Piensa en simplicidad, medicion y evidencia antes que intuicion."
        ),
        response_templates=[
            "Desde datos y diseno, {task} necesita metricas claras. Que medimos y como sabemos que funciona? {legend} decia: menos pero mejor.",
            "Como CDO: {task} — donde estan los datos que respaldan esta decision? Sin evidencia, es opinion. Necesitamos numeros antes de actuar.",
            "La claridad radical importa. {task} debe simplificarse hasta que no se pueda quitar nada mas. Si es complejo, no esta terminado.",
            "Mi lectura desde el dato: {task} requiere definir KPIs antes de arrancar. Que exito se ve en numeros? Sin esa definicion, no podemos evaluar el resultado.",
        ],
    ),
]

# ── Lookups derivados ──────────────────────────────────────

BY_ROLE: dict[str, BoardMember] = {m.role: m for m in BOARD}
SIDE_OPERATIVO: list[BoardMember] = [m for m in BOARD if m.side == "operativo"]
SIDE_CREATIVO: list[BoardMember] = [m for m in BOARD if m.side == "creativo"]

PAIRS: dict[str, str] = {
    "CEO": "CSO", "CSO": "CEO",
    "CFO": "CDO", "CDO": "CFO",
    "COO": "CXO", "CXO": "COO",
    "CTO": "CCO", "CCO": "CTO",
}


# ── Despacho ───────────────────────────────────────────────


def resolve_target(target: str) -> list[BoardMember]:
    """Resuelve un target a la lista de miembros del consejo."""
    t = target.strip().lower()

    if t == "consejo":
        return list(BOARD)

    if t == "operativo":
        return list(SIDE_OPERATIVO)

    if t == "creativo":
        return list(SIDE_CREATIVO)

    if t.startswith("pareja:"):
        role_key = t.split(":", 1)[1].strip().upper()
        if role_key not in PAIRS:
            raise ValueError(
                f"Rol '{role_key}' no existe. Roles validos: {', '.join(BY_ROLE.keys())}"
            )
        partner_key = PAIRS[role_key]
        pair = sorted([BY_ROLE[role_key], BY_ROLE[partner_key]], key=lambda m: m.seat)
        return pair

    role_upper = t.upper()
    if role_upper in BY_ROLE:
        return [BY_ROLE[role_upper]]

    raise ValueError(
        f"Target '{target}' no reconocido.\n"
        f"Usa: consejo, operativo, creativo, pareja:ROL o un rol individual "
        f"({', '.join(BY_ROLE.keys())})"
    )


# ── Generacion de respuestas ───────────────────────────────


def _pick_template(member: BoardMember, task: str) -> str:
    """Selecciona un template y lo rellena."""
    template = random.choice(member.response_templates)
    return template.format(
        task=task,
        role=member.role,
        name=member.name,
        legend=member.legend,
        domain=member.domain,
    )


async def _generate_llm_response(
    member: BoardMember,
    task: str,
    http_session: aiohttp.ClientSession,
) -> str:
    """Genera respuesta via API LLM (Anthropic Messages API)."""
    headers = {
        "x-api-key": CONSEJO_LLM_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": CONSEJO_LLM_MODEL,
        "max_tokens": CONSEJO_MAX_RESPONSE_LENGTH,
        "system": member.system_prompt,
        "messages": [{"role": "user", "content": task}],
    }
    try:
        async with http_session.post(
            CONSEJO_LLM_API_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["content"][0]["text"]
            logger.warning(f"LLM API error for {member.role}: status={resp.status}")
            return _pick_template(member, task)
    except Exception as e:
        logger.warning(f"LLM API exception for {member.role}: {e}")
        return _pick_template(member, task)


async def generate_response(
    member: BoardMember,
    task: str,
    use_llm: bool = False,
    http_session: aiohttp.ClientSession | None = None,
) -> str:
    """Genera la respuesta de un consejero ante una tarea."""
    if use_llm and http_session and CONSEJO_LLM_API_KEY:
        return await _generate_llm_response(member, task, http_session)
    return _pick_template(member, task)


async def dispatch_task(
    members: list[BoardMember],
    task: str,
) -> list[tuple[BoardMember, str]]:
    """Despacha una tarea a N miembros y devuelve sus respuestas."""
    use_llm = CONSEJO_USE_LLM
    session = None

    if use_llm and CONSEJO_LLM_API_KEY:
        session = aiohttp.ClientSession()

    try:
        responses = await asyncio.gather(
            *[generate_response(m, task, use_llm, session) for m in members]
        )
        return list(zip(members, responses))
    finally:
        if session and not session.closed:
            await session.close()


# ── Formateo ───────────────────────────────────────────────


def _esc(text: str) -> str:
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


def format_member_response(member: BoardMember, response: str) -> str:
    """Formatea la respuesta de un consejero individual."""
    return (
        f"{member.emoji} *{member.role} — {_esc(member.name)}*\n"
        f"_{_esc(member.title_es)} | Leyenda: {_esc(member.legend)}_\n\n"
        f"{_esc(response)}"
    )


def format_target_label(target: str) -> str:
    """Devuelve una etiqueta legible para el target."""
    t = target.strip().lower()
    if t == "consejo":
        return "Consejo completo (8 sillas)"
    if t == "operativo":
        return "Lado operativo (CEO, CFO, COO, CTO)"
    if t == "creativo":
        return "Lado creativo (CCO, CSO, CXO, CDO)"
    if t.startswith("pareja:"):
        role_key = t.split(":", 1)[1].strip().upper()
        partner = PAIRS.get(role_key, "?")
        return f"Pareja coetanea: {role_key} ↔ {partner}"
    return t.upper()


def assemble_full_response(
    target: str,
    task: str,
    responses: list[tuple[BoardMember, str]],
) -> list[str]:
    """Ensambla la respuesta completa. Devuelve lista de mensajes (split si >3800 chars)."""
    header = (
        f"🏛 *Consejo de Administracion*\n"
        f"📋 *Tarea:* {_esc(task)}\n"
        f"👥 *Consultados:* {format_target_label(target)}\n"
        f"{'─' * 30}"
    )

    body_parts = [format_member_response(m, r) for m, r in responses]
    full = header + "\n\n" + ("\n\n" + "─" * 30 + "\n\n").join(body_parts)

    if len(full) <= 3800:
        return [full]

    # Split: header + respuestas individuales
    messages = [header]
    for part in body_parts:
        messages.append(part)
    return messages


# ── Visual de la mesa ──────────────────────────────────────


def build_board_table() -> str:
    """Construye la representacion visual de la mesa del consejo."""
    lines = [
        "🏛 *Consejo de Administracion*",
        "_Una mesa de contrapesos, no una lista de cargos_\n",
        "┌─────────────────────────────────────┐",
        "│  *OPERATIVO*        │   *CREATIVO*        │",
        "│  (izquierda)        │   (derecha)         │",
        "├─────────────────────────────────────┤",
    ]
    for i in range(4):
        op = SIDE_OPERATIVO[i]
        cr = SIDE_CREATIVO[i]
        pair_label = f"{op.role}↔{cr.role}"
        lines.append(
            f"│ {op.emoji} {op.role}: {_esc(op.name)[:12]}"
            f"  │ {cr.emoji} {cr.role}: {_esc(cr.name)[:12]}"
            f"  │"
        )
        lines.append(f"│   _{_esc(op.legend)}_{'':>6}│   _{_esc(cr.legend)}_{'':>6}│")
        lines.append(f"│          ↔ {pair_label}{'':>13}│")
        if i < 3:
            lines.append("├─────────────────────────────────────┤")
    lines.append("└─────────────────────────────────────┘")
    lines.append("\n_Pulsa un boton para consultar al consejo._")
    return "\n".join(lines)


# ── Teclado inline ─────────────────────────────────────────


def build_board_keyboard():
    """Construye el InlineKeyboardMarkup para el consejo."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    rows = [
        # Fila 1: consejo completo
        [InlineKeyboardButton("🏛 Consejo Completo", callback_data="consejo:consejo")],
        # Fila 2: lados
        [
            InlineKeyboardButton("⚙️ Operativo", callback_data="consejo:operativo"),
            InlineKeyboardButton("🎨 Creativo", callback_data="consejo:creativo"),
        ],
        # Fila 3: lado operativo individual
        [
            InlineKeyboardButton("🚀 CEO", callback_data="consejo:CEO"),
            InlineKeyboardButton("💰 CFO", callback_data="consejo:CFO"),
            InlineKeyboardButton("⚙️ COO", callback_data="consejo:COO"),
            InlineKeyboardButton("🔧 CTO", callback_data="consejo:CTO"),
        ],
        # Fila 4: lado creativo individual
        [
            InlineKeyboardButton("🎨 CCO", callback_data="consejo:CCO"),
            InlineKeyboardButton("🧭 CSO", callback_data="consejo:CSO"),
            InlineKeyboardButton("✨ CXO", callback_data="consejo:CXO"),
            InlineKeyboardButton("📐 CDO", callback_data="consejo:CDO"),
        ],
        # Fila 5: parejas coetaneas
        [
            InlineKeyboardButton("CEO↔CSO", callback_data="consejo:pareja:CEO"),
            InlineKeyboardButton("CFO↔CDO", callback_data="consejo:pareja:CFO"),
        ],
        [
            InlineKeyboardButton("COO↔CXO", callback_data="consejo:pareja:COO"),
            InlineKeyboardButton("CTO↔CCO", callback_data="consejo:pareja:CTO"),
        ],
    ]
    return InlineKeyboardMarkup(rows)
