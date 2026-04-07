"""Yarig.ai integration — full platform access via API."""

import json
import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import aiohttp

from src.config import YARIG_EMAIL, YARIG_PASSWORD

logger = logging.getLogger(__name__)

YARIG_BASE = "https://yarig.ai"
LOGIN_URL = f"{YARIG_BASE}/registration/login"
TASKS_URL = f"{YARIG_BASE}/tasks/json_get_current_day_tasks_and_journey_info"
ADD_TASKS_URL = f"{YARIG_BASE}/tasks/json_add_tasks"
UPDATE_TASK_URL = f"{YARIG_BASE}/tasks/json_update_task"
DELETE_TASK_URL = f"{YARIG_BASE}/tasks/json_delete_task"
OPEN_TASK_URL = f"{YARIG_BASE}/tasks/json_get_and_open_task"
CLOSE_TASK_URL = f"{YARIG_BASE}/tasks/json_close_task"
CLOCKING_URL = f"{YARIG_BASE}/clocking/json_add_clocking"
CLOCKING_EXTRA_URL = f"{YARIG_BASE}/clocking_extra/json_add_clocking_extra"
SCORE_URL = f"{YARIG_BASE}/score/json_user_score"
USERS_URL = f"{YARIG_BASE}/user/json_get_customers_and_mates_like"
PROJECTS_URL = f"{YARIG_BASE}/projects/json_get_projects_like_by_customer_and_order"
ADD_REQUEST_URL = f"{YARIG_BASE}/tasks/json_add_request"
UNREAD_REQUESTS_URL = f"{YARIG_BASE}/tasks/json_get_unread_requests_by_user"
REQUEST_DETAIL_URL = f"{YARIG_BASE}/tasks/json_get_task_request"
UPDATE_REQUEST_STATE_URL = f"{YARIG_BASE}/tasks/json_update_state_task_request"
OPEN_TASK_FROM_REQUEST_URL = f"{YARIG_BASE}/tasks/json_add_open_task_from_task_request"
NOTIFICATIONS_URL = f"{YARIG_BASE}/system_notification/json_get_user_notifications"
WORKING_STATE_URL = f"{YARIG_BASE}/working_state/json_change_state"
RANKING_URL = f"{YARIG_BASE}/productivity/json_get_team_by_order_or_rank"
COMPANY_TASKS_URL = f"{YARIG_BASE}/tasks/json_get_newer_company_tasks"
USER_DAYS_URL = f"{YARIG_BASE}/personal/json_get_user_days"
SCORING_URL = f"{YARIG_BASE}/personal/json_get_scoring"


COMPLETION_POINTS_FILE = Path(__file__).resolve().parent.parent / "state" / "completion_points.json"


SPANISH_WEEKDAYS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
SPANISH_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


MADRID_TZ = ZoneInfo("Europe/Madrid")
UTC = timezone.utc


def _parse_dt(value: str | None) -> datetime | None:
    """Parse a datetime string from Yarig API (UTC) and return aware datetime."""
    if not value:
        return None
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _to_madrid(dt: datetime) -> datetime:
    """Convert an aware datetime to Madrid timezone."""
    return dt.astimezone(MADRID_TZ)


def _format_dt_madrid(value: str | None) -> str:
    """Format a Yarig API datetime string in Madrid timezone (HH:MM)."""
    dt = _parse_dt(value)
    if dt is None:
        return ""
    return _to_madrid(dt).strftime("%H:%M")


def _load_completion_points() -> dict[str, dict]:
    try:
        if COMPLETION_POINTS_FILE.exists():
            data = json.loads(COMPLETION_POINTS_FILE.read_text())
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_completion_points(data: dict[str, dict]) -> None:
    COMPLETION_POINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    COMPLETION_POINTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


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


def build_daily_opening_task_text(target_date: date | None = None) -> str:
    target_date = target_date or datetime.now().date()
    weekday = SPANISH_WEEKDAYS[target_date.weekday()]
    month = SPANISH_MONTHS[target_date.month - 1]
    return f"Hoy es {weekday} {target_date.day} de {month} de {target_date.year}"


def _common_project_name(tasks: list[dict]) -> str:
    names = {str((task.get("project") or "")).strip() for task in tasks if str((task.get("project") or "")).strip()}
    if len(names) == 1:
        return next(iter(names))
    return ""


def _format_elapsed_compact(start_value: str | None, end_value: str | None = None) -> str:
    start_dt = _parse_dt(start_value)
    if start_dt is None:
        return ""
    end_dt = _parse_dt(end_value) if end_value else datetime.now(UTC)
    if end_dt is None:
        end_dt = datetime.now(UTC)
    total_seconds = max(int((end_dt - start_dt).total_seconds()), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m"
    return "<1m"


class YarigClient:
    """Async client for Yarig.ai with full platform access."""

    def __init__(self, email: str = YARIG_EMAIL, password: str = YARIG_PASSWORD):
        self.email = email
        self.password = password
        self._session: aiohttp.ClientSession | None = None
        self._logged_in = False
        self._cache_ttl_seconds = 300
        self._team_cache: dict | None = None
        self._projects_cache: dict[str, dict] = {}

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            jar = aiohttp.CookieJar(unsafe=True)
            self._session = aiohttp.ClientSession(connector=connector, cookie_jar=jar)
            self._logged_in = False

    async def login(self) -> bool:
        if not self.email or not self.password:
            logger.warning("Yarig credentials not configured")
            return False
        await self._ensure_session()
        try:
            await self._session.get(LOGIN_URL)
            async with self._session.post(
                LOGIN_URL,
                data={"email": self.email, "password": self.password, "submit": "Entrar"},
                allow_redirects=True,
            ) as resp:
                if resp.status == 200 and "/tasks" in str(resp.url):
                    self._logged_in = True
                    logger.info("Yarig login successful")
                    return True
                logger.warning(f"Yarig login failed: url={resp.url}")
                return False
        except Exception as e:
            logger.warning(f"Yarig login error: {e}")
            return False

    async def _request(self, url: str, data: dict | None = None, method: str = "POST") -> dict | list | int | None:
        await self._ensure_session()
        if not self._logged_in:
            if not await self.login():
                return None
        try:
            kw = {"data": data} if data else {}
            async with self._session.request(method, url, **kw) as resp:
                if resp.status == 200:
                    result = await resp.json(content_type=None)
                    return result
                # Session expired
                self._logged_in = False
                if await self.login():
                    async with self._session.request(method, url, **kw) as retry:
                        if retry.status == 200:
                            return await retry.json(content_type=None)
                logger.warning(f"Yarig request failed: {url} status={resp.status}")
                return None
        except Exception as e:
            logger.warning(f"Yarig request error: {e}")
            return None

    def _cache_is_fresh(self, cached: dict | None) -> bool:
        if not cached:
            return False
        return (time.time() - cached.get("ts", 0)) < self._cache_ttl_seconds


    @staticmethod
    def _esc(text: str) -> str:
        for ch in ("_", "*", "`", "["):
            text = text.replace(ch, f"\\{ch}")
        return text

    @staticmethod
    def _score_rank(score: int) -> tuple[str, str]:
        if score >= 80:
            return "💎", "Leyenda"
        if score >= 40:
            return "🚀", "Heroe"
        if score >= 15:
            return "🧭", "Explorador"
        if score > 0:
            return "✨", "Rookie"
        if score < 0:
            return "🫧", "En recuperacion"
        return "◌", "Sin combo"

    async def _get_score_value(self) -> int:
        score_raw = await self._request(SCORE_URL)
        try:
            return int(score_raw) if isinstance(score_raw, (int, str)) else 0
        except (TypeError, ValueError):
            return 0

    def get_task_completion_points(self, task_id: str) -> int | None:
        data = _load_completion_points()
        entry = data.get(str(task_id))
        if isinstance(entry, dict):
            points = entry.get("points")
            if isinstance(points, int):
                return points
        return None

    def get_task_completion_badge(self, task_id: str) -> str:
        points = self.get_task_completion_points(task_id)
        if points is None:
            return ""
        sign = "+" if points >= 0 else ""
        return f" · XP {sign}{points}"

    def remember_task_completion_points(self, task_id: str, points: int) -> None:
        data = _load_completion_points()
        data[str(task_id)] = {
            "points": int(points),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        _save_completion_points(data)

    async def _get_score_summary_line(self) -> str:
        score = await self._get_score_value()
        icon, rank = self._score_rank(score)
        return f"{icon} XP Yarig: *{score}* puntos · Rango: *{self._esc(rank)}*"
    # ── Tareas del día ──────────────────────────────────────

    async def get_today_data(self) -> dict | None:
        return await self._request(TASKS_URL)

    async def get_today_summary(self) -> str:
        data = await self.get_today_data()
        if not data:
            return "No he podido conectar con Yarig.ai ahora mismo."

        tasks = data.get("tasks", [])
        clocking = data.get("clocking", [])

        if not tasks and not clocking:
            return "Todo en orden: no hay actividad registrada para hoy todavía."

        score_line = await self._get_score_summary_line()
        journey_elapsed = _format_elapsed_compact(clocking[0].get("datetime")) if clocking else ""
        active_count = sum(1 for task in tasks if task.get("start_time") and not task.get("end_time") and task.get("finished", "0") == "0")
        pending_count = sum(1 for task in tasks if not task.get("start_time") and task.get("finished", "0") == "0")
        paused_count = sum(1 for task in tasks if task.get("start_time") and task.get("end_time") and task.get("finished", "0") == "0")
        finished_count = sum(1 for task in tasks if task.get("finished", "0") == "1")
        common_project = _common_project_name(tasks)
        missions_header = "◌ *Misiones del dia*"
        if journey_elapsed:
            missions_header += f" · Tiempo transcurrido: *{journey_elapsed}*"
        lines = ["✦ *Yarig.ai | Panel*", score_line, "", missions_header, f"● {active_count} activas · ◌ {pending_count} pendientes · ⏸ {paused_count} en pausa · ☑ {finished_count} completadas"]
        if common_project:
            lines.append(f"▣ Proyecto principal: _{self._esc(common_project)}_")
        lines.append("")

        indexed_tasks = list(enumerate(tasks, 1))
        indexed_tasks.sort(key=lambda item: _task_sort_key(item[1]))

        for i, task in indexed_tasks:
            desc = self._esc(task.get("description", "").strip())
            project = self._esc(task.get("project", ""))
            finished = task.get("finished", "0")
            start_time = task.get("start_time")
            end_time = task.get("end_time")

            if finished == "1":
                status = "☑"
            elif start_time and not end_time:
                status = "●"
            else:
                status = "◌"

            line = f"{i}. {status} {desc}"
            if project and project != self._esc(common_project):
                line += f" — _{project}_"
            if finished == "1":
                task_elapsed = _format_elapsed_compact(start_time, end_time)
                if task_elapsed:
                    line += f" · ⏱ {task_elapsed}"
                points_badge = self.get_task_completion_badge(str(task.get("id", "")))
                if points_badge:
                    line += points_badge
            lines.append(line)

        if not tasks:
            lines.append("(sin tareas registradas)")

        if clocking:
            entry = clocking[0]
            name = self._esc(entry.get("name", ""))
            dt_raw = entry.get("datetime", "")
            dt_display = _format_dt_madrid(dt_raw) or dt_raw or "?"
            journey_elapsed = _format_elapsed_compact(dt_raw)
            if journey_elapsed:
                lines.append(f"\n◔ Jornada de *{name}* iniciada: {dt_display} · ⏱ {journey_elapsed}")
            else:
                lines.append(f"\n◔ Jornada de *{name}* iniciada: {dt_display}")

        return "\n".join(lines)
    async def get_status_summary(self) -> str:
        """Return compact status for current workday, active task and score."""
        data = await self.get_today_data()
        if not data:
            return "⚠️ No he podido conectar con Yarig.ai ahora mismo."

        tasks = data.get("tasks", [])
        clocking = data.get("clocking", [])
        active = self._find_active_task(tasks)
        score = await self._get_score_value()
        score_icon, rank = self._score_rank(score)
        lines = ["✦ *Yarig.ai | Estado*\n"]

        if clocking:
            entry = clocking[0]
            name = self._esc(entry.get("name", ""))
            dt_raw = entry.get("datetime", "")
            dt_display = _format_dt_madrid(dt_raw) or dt_raw or "?"
            journey_elapsed = _format_elapsed_compact(dt_raw)
            journey_line = f"◔ Sesion activa: *{name}* desde {dt_display}"
            if journey_elapsed:
                journey_line += f"\n⏱ Tiempo transcurrido: {journey_elapsed}"
            lines.append(journey_line)
        else:
            lines.append("◔ Sesion: sin fichaje activo")

        if active:
            desc = self._esc(active.get("description", "").strip())
            project = self._esc(active.get("project", ""))
            start_display = _format_dt_madrid(active.get("start_time")) or active.get("start_time", "?")
            task_elapsed = _format_elapsed_compact(active.get("start_time"), active.get("end_time"))
            line = f"● Tarea activa: *{desc}*"
            if project:
                line += f" — _{project}_"
            line += f"\n◔ Inicio: {start_display}"
            if task_elapsed:
                line += f"\n⏱ Dedicado a esta tarea: {task_elapsed}"
            lines.append(line)
        else:
            pending_count = sum(
                1
                for task in tasks
                if task.get("finished", "0") == "0" and not task.get("start_time")
            )
            paused_count = sum(
                1
                for task in tasks
                if task.get("finished", "0") == "0" and task.get("start_time") and task.get("end_time")
            )
            lines.append(
                "◌ Sin mision activa"
                f"\n⏳ Pendientes: {pending_count}"
                f"\n⏸ Pausadas: {paused_count}"
            )

        lines.append(f"{score_icon} XP actual: *{score}* puntos")
        lines.append(f"◆ Rango actual: *{self._esc(rank)}*")
        return "\n\n".join(lines)
    # ── Fichar ──────────────────────────────────────────────

    async def fichar_entrada(self) -> str:
        result = await self._request(CLOCKING_URL, {"type": 0, "todo": ""})
        if result:
            return "☑ Sesion iniciada"
        return "⚠️ No he podido abrir la sesion. Puede que ya estuviera iniciada."

    async def fichar_salida(self, todo: str = "") -> str:
        result = await self._request(CLOCKING_URL, {"type": 1, "todo": todo})
        if result:
            return "☑ Sesion cerrada"
        return "⚠️ No he podido cerrar la sesion."

    # ── Horas extras ────────────────────────────────────────

    async def extras_inicio(self) -> str:
        result = await self._request(CLOCKING_EXTRA_URL, {"type": 0})
        msgs = {
            0: "⚠️ Estás dentro de tu horario laboral, no puedes hacer extras ahora",
            1: "⚠️ Ya tienes una jornada extra abierta, ciérrala primero",
        }
        if isinstance(result, int) and result in msgs:
            return msgs[result]
        return "☑ Bloque extra iniciado"

    async def extras_fin(self) -> str:
        result = await self._request(CLOCKING_EXTRA_URL, {"type": 1})
        msgs = {
            2: "☑ Bloque extra finalizado",
            3: "⚠️ Ya finalizaste las horas extras hoy",
        }
        if isinstance(result, int) and result in msgs:
            return msgs[result]
        return "⚠️ Hoy no has iniciado horas extras"

    # ── Añadir tarea ────────────────────────────────────────

    async def ensure_daily_opening_task(self, project_id: int = 312) -> tuple[bool, str]:
        task_text = build_daily_opening_task_text()
        data = await self.get_today_data()
        tasks = (data or {}).get("tasks", [])
        for task in tasks:
            if str(task.get("description", "")).strip().lower() == task_text.lower():
                return False, task_text

        result = await self.add_task(task_text, project_id=project_id)
        return result.startswith("☑"), task_text

    async def ensure_task_for_today(self, description: str, project_id: int = 312) -> tuple[bool, dict | None]:
        data = await self.get_today_data()
        tasks = (data or {}).get("tasks", [])
        wanted = str(description).strip().lower()
        for task in tasks:
            if str(task.get("description", "")).strip().lower() == wanted:
                return False, task

        result = await self.add_task(description, project_id=project_id)
        if not result.startswith("☑"):
            return False, None

        data = await self.get_today_data()
        tasks = (data or {}).get("tasks", [])
        for task in tasks:
            if str(task.get("description", "")).strip().lower() == wanted:
                return True, task
        return True, None

    async def start_task_if_needed(self, task_id: str) -> str:
        data = await self.get_today_data()
        if not data or not data.get("tasks"):
            return "⚠️ No hay tareas para hoy"

        task = next((t for t in data["tasks"] if str(t.get("id")) == str(task_id)), None)
        if not task:
            return "⚠️ Esa mision ya no aparece en la lista actual."

        if task.get("finished") == "1":
            return f"☑ Ya estaba completada: {task.get('description', '').strip()}"

        if task.get("start_time") and not task.get("end_time"):
            return f"▶ Mision ya en marcha: {task.get('description', '').strip()}"

        return await self.iniciar_tarea_por_id(task_id)

    async def close_task_by_description(self, description: str) -> str:
        data = await self.get_today_data()
        if not data or not data.get("tasks"):
            return "⚠️ No hay tareas para hoy"

        wanted = str(description).strip().lower()
        task = next((t for t in data["tasks"] if str(t.get("description", "")).strip().lower() == wanted and t.get("finished") != "1"), None)
        if not task:
            done = next((t for t in data["tasks"] if str(t.get("description", "")).strip().lower() == wanted and t.get("finished") == "1"), None)
            if done:
                return f"☑ Mision ya completada: {done.get('description', '').strip()}"
            return f"⚠️ No he encontrado una mision abierta llamada: {description}"

        task_id = str(task.get("id"))
        if not (task.get("start_time") and not task.get("end_time")):
            await self.start_task_if_needed(task_id)
        return await self.finalizar_tarea_por_id(task_id)


    async def add_task(self, description: str, project_id: int = 312, estimation: int = 1) -> str:
        tmp_id = int(time.time() * 1000)
        task_str = f"{tmp_id}#$#{estimation}#$#{description}#$#{project_id}@$@"
        result = await self._request(ADD_TASKS_URL, {"tasks": task_str})
        if result:
            return f"☑ Nueva mision creada: {description}"
        return "⚠️ No he podido crear la mision."

    # ── Iniciar / Parar tarea ───────────────────────────────

    def _find_active_task(self, tasks: list[dict]) -> dict | None:
        """Find the currently active (started, not finished) task."""
        for t in tasks:
            if t.get("start_time") and not t.get("end_time") and t.get("finished") == "0":
                return t
        return None

    async def iniciar_tarea(self, task_index: int = 1) -> str:
        """Start or resume a task by index."""
        data = await self.get_today_data()
        if not data or not data.get("tasks"):
            return "⚠️ No hay tareas para hoy"

        tasks = data["tasks"]
        if task_index < 1 or task_index > len(tasks):
            return f"⚠️ La mision {task_index} no existe. Ahora mismo hay {len(tasks)} en la lista."

        task = tasks[task_index - 1]
        tid = task["id"]
        result = await self._request(OPEN_TASK_URL, {"id": tid})
        if result:
            desc = task.get("description", "").strip()
            was_started = task.get("start_time") is not None
            icon = "↺" if was_started else "▶"
            verb = "reanudada" if was_started else "en marcha"
            return f"{icon} Mision {verb}: {desc}"
        return "⚠️ No he podido poner en marcha esa mision."

    async def iniciar_tarea_por_id(self, task_id: str) -> str:
        data = await self.get_today_data()
        if not data or not data.get("tasks"):
            return "⚠️ No hay tareas para hoy"

        task = next((t for t in data["tasks"] if str(t.get("id")) == str(task_id)), None)
        if not task:
            return "⚠️ Esa mision ya no aparece en la lista actual."

        result = await self._request(OPEN_TASK_URL, {"id": task_id})
        if result:
            desc = task.get("description", "").strip()
            was_started = task.get("start_time") is not None
            icon = "↺" if was_started else "▶"
            verb = "reanudada" if was_started else "en marcha"
            return f"{icon} Mision {verb}: {desc}"
        return "⚠️ No he podido poner en marcha esa mision."

    async def pausar_tarea(self) -> str:
        """Pause the active task (leave for later, not finished)."""
        data = await self.get_today_data()
        if not data or not data.get("tasks"):
            return "⚠️ No hay tareas para hoy"

        active = self._find_active_task(data["tasks"])
        if not active:
            return "⚠️ No hay ninguna mision en curso ahora mismo."

        tid = active["id"]
        # finished=0 → pause (dejar para luego)
        result = await self._request(CLOSE_TASK_URL, {"tid": tid, "finished": 0})
        if result is not None:
            desc = active.get("description", "").strip()
            return f"⏸ Mision en pausa: {desc}\nLista para retomarla cuando quieras."
        return "⚠️ No he podido poner la mision en pausa."

    async def pausar_tarea_por_id(self, task_id: str) -> str:
        data = await self.get_today_data()
        if not data or not data.get("tasks"):
            return "⚠️ No hay tareas para hoy"

        task = next((t for t in data["tasks"] if str(t.get("id")) == str(task_id)), None)
        if not task:
            return "⚠️ Esa mision ya no aparece en la lista actual."

        result = await self._request(CLOSE_TASK_URL, {"tid": task_id, "finished": 0})
        if result is not None:
            desc = task.get("description", "").strip()
            return f"⏸ Mision en pausa: {desc}\nLista para retomarla cuando quieras."
        return "⚠️ No he podido poner la mision en pausa."

    async def finalizar_tarea(self, task_index: int | None = None) -> str:
        """Finish/complete a task (mark as done)."""
        data = await self.get_today_data()
        if not data or not data.get("tasks"):
            return "⚠️ No hay tareas para hoy"

        tasks = data["tasks"]

        if task_index is not None:
            if task_index < 1 or task_index > len(tasks):
                return f"⚠️ La mision {task_index} no existe. Ahora mismo hay {len(tasks)} en la lista."
            task = tasks[task_index - 1]
        else:
            task = self._find_active_task(tasks)
            if not task:
                return "⚠️ No hay ninguna mision activa. Usa /finalizar <n> si quieres cerrar una concreta."

        tid = task["id"]
        # finished=1 → completar
        pre_score = await self._get_score_value()
        result = await self._request(CLOSE_TASK_URL, {"tid": tid, "finished": 1})
        if result is not None:
            post_score = await self._get_score_value()
            gained_points = post_score - pre_score
            self.remember_task_completion_points(str(tid), gained_points)
            desc = task.get("description", "").strip()
            return f"☑ Mision completada: {desc} · XP {gained_points:+d}"
        return "⚠️ No he podido completar la mision."

    async def finalizar_tarea_por_id(self, task_id: str) -> str:
        data = await self.get_today_data()
        if not data or not data.get("tasks"):
            return "⚠️ No hay tareas para hoy"

        task = next((t for t in data["tasks"] if str(t.get("id")) == str(task_id)), None)
        if not task:
            return "⚠️ Esa mision ya no aparece en la lista actual."

        pre_score = await self._get_score_value()
        result = await self._request(CLOSE_TASK_URL, {"tid": task_id, "finished": 1})
        if result is not None:
            post_score = await self._get_score_value()
            gained_points = post_score - pre_score
            self.remember_task_completion_points(str(task_id), gained_points)
            desc = task.get("description", "").strip()
            return f"☑ Mision completada: {desc} · XP {gained_points:+d}"
        return "⚠️ No he podido completar la mision."

    # ── Puntuación ──────────────────────────────────────────

    async def get_score(self) -> str:
        score = await self._get_score_value()
        icon, rank = self._score_rank(score)
        return (
            "✦ *Yarig.ai | Puntuacion*\n\n"
            f"{icon} XP actual: *{score}* puntos\n"
            f"◆ Rango: *{self._esc(rank)}*"
        )
    # ── Equipo ──────────────────────────────────────────────

    async def get_team_data(self, refresh: bool = False) -> list[dict]:
        if not refresh and self._cache_is_fresh(self._team_cache):
            return self._team_cache.get("items", [])

        result = await self._request(USERS_URL, {"term": ""})
        mates = result.get("mates", []) if result and result.get("mates") else []
        if mates:
            self._team_cache = {"ts": time.time(), "items": mates}
        return mates

    async def get_team(self) -> str:
        mates = await self.get_team_data()
        if not mates:
            return "⚠️ No he podido cargar el equipo ahora mismo."

        lines = [f"👥 *Equipo Yarig.ai* ({len(mates)} miembros)\n"]
        for m in mates:
            name = self._esc(m.get("name", "?"))
            lines.append(f"• {name}")
        return "\n".join(lines)

    # ── Ranking ────────────────────────────────────────────

    async def get_ranking(self) -> str:
        result = await self._request(RANKING_URL, {
            "column": "points", "order": "desc", "rank": "points", "range": "",
        })
        if not result or not isinstance(result, list):
            return "⚠️ No he podido cargar el ranking ahora mismo."

        STATE_ICONS = {
            "Trabajando": "🟢", "Gestionando tareas": "🟡",
            "En casa": "🔴", "Reunión": "🔵",
        }

        active = [m for m in result if m.get("total_points") is not None]
        inactive = [m for m in result if m.get("total_points") is None]
        active.sort(key=lambda m: int(m.get("total_points") or 0), reverse=True)

        lines = [f"🏆 *Ranking Yarig.ai* — {len(result)} miembros\n"]

        for pos, m in enumerate(active, 1):
            name = self._esc(m.get("name", "?"))
            points = int(m.get("total_points") or 0)
            started = int(m.get("total_started_tasks") or 0)
            finished = int(m.get("total_finished_tasks") or 0)
            state = m.get("state") or ""
            state_icon = STATE_ICONS.get(state, "⚪")
            score_icon, _ = self._score_rank(points)

            medal = ""
            if pos == 1:
                medal = "🥇 "
            elif pos == 2:
                medal = "🥈 "
            elif pos == 3:
                medal = "🥉 "

            lines.append(
                f"{medal}{pos}. {state_icon} *{name}* — {score_icon} {points:+d} XP"
                f"\n     ▶ {started} iniciadas · ☑ {finished} completadas"
            )

        if inactive:
            names = ", ".join(self._esc(m.get("name", "?")) for m in inactive)
            lines.append(f"\n◌ Sin actividad: _{names}_")

        return "\n".join(lines)

    # ── Dedicacion del equipo ──────────────────────────────

    async def get_dedication(self) -> str:
        result = await self._request(COMPANY_TASKS_URL, {"id": 0})
        if not result or not isinstance(result, dict):
            return "⚠️ No he podido cargar la dedicacion del equipo."

        tasks = result.get("tasks", [])
        clockings = result.get("clockings", [])

        # Group clockings by user (entry time)
        user_clockin: dict[str, str] = {}
        for c in clockings:
            uid = c.get("id_user", "")
            if c.get("type") == "0" and uid not in user_clockin:
                user_clockin[uid] = c.get("datetime", "")

        # Group tasks by user
        user_tasks: dict[str, dict] = {}
        for t in tasks:
            uid = t.get("id_user", "")
            if uid not in user_tasks:
                user_tasks[uid] = {
                    "name": t.get("name", "?"),
                    "tasks": [],
                    "active": None,
                    "finished": 0,
                    "total": 0,
                }
            entry = user_tasks[uid]
            entry["total"] += 1
            entry["tasks"].append(t)
            if t.get("finished") == "1":
                entry["finished"] += 1
            elif t.get("start_time") and not t.get("end_time"):
                entry["active"] = t

        # Also add users with clockings but no tasks
        for c in clockings:
            uid = c.get("id_user", "")
            if uid not in user_tasks and c.get("type") == "0":
                user_tasks[uid] = {
                    "name": c.get("name", "?"),
                    "tasks": [],
                    "active": None,
                    "finished": 0,
                    "total": 0,
                }

        if not user_tasks:
            return "📊 *Dedicacion del equipo*\n\nAun no hay actividad registrada hoy."

        lines = [f"📊 *Dedicacion del equipo* — {len(user_tasks)} activos hoy\n"]

        for uid, data in sorted(user_tasks.items(), key=lambda x: x[1]["name"]):
            name = self._esc(data["name"])
            clockin_dt = user_clockin.get(uid)
            elapsed = _format_elapsed_compact(clockin_dt) if clockin_dt else ""
            clockin_display = _format_dt_madrid(clockin_dt) if clockin_dt else ""

            line = f"👤 *{name}*"
            if clockin_display:
                line += f" · 🕐 {clockin_display}"
            if elapsed:
                line += f" · ⏱ {elapsed}"
            line += f"\n     ☑ {data['finished']}/{data['total']} misiones"

            if data["active"]:
                desc = self._esc(data["active"].get("description", "").strip())
                project = self._esc(data["active"].get("project", ""))
                line += f"\n     ● _{desc}_"
                if project:
                    line += f" — {project}"

            lines.append(line)

        return "\n".join(lines)

    # ── Estadísticas anuales ──────────────────────────────────

    async def get_stats(self) -> str:
        """Return annual stats summary (days worked, states calendar)."""
        result = await self._request(USER_DAYS_URL)
        if not result or not isinstance(result, dict):
            return "⚠️ No he podido cargar las estadísticas anuales."

        now = datetime.now(MADRID_TZ)
        current_year = now.year
        current_month = now.month

        # Count days by state for the current year
        state_counts: dict[str, int] = {}
        monthly_counts: dict[int, int] = {}
        total_days = 0

        for _key, entry in result.items():
            if not isinstance(entry, dict):
                continue
            try:
                year = int(entry.get("year", 0))
                month = int(entry.get("month", 0))
                state = str(entry.get("state", "")).strip()
            except (ValueError, TypeError):
                continue

            if year != current_year:
                continue

            total_days += 1
            state_counts[state] = state_counts.get(state, 0) + 1
            monthly_counts[month] = monthly_counts.get(month, 0) + 1

        if total_days == 0:
            return f"📊 *Estadísticas {current_year}*\n\nAún no hay datos registrados este año."

        STATE_LABELS = {
            "in": ("🟢", "Trabajando"),
            "out": ("🔴", "Ausente"),
            "holiday": ("🏖", "Vacaciones"),
            "sick": ("🤒", "Baja"),
            "remote": ("🏠", "Remoto"),
        }

        lines = [f"📊 *Estadísticas {current_year}*\n"]
        lines.append(f"📅 Total días registrados: *{total_days}*\n")

        # State breakdown
        lines.append("*Por estado:*")
        for state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
            icon, label = STATE_LABELS.get(state, ("⚪", state.capitalize() or "Otro"))
            lines.append(f"  {icon} {self._esc(label)}: *{count}* días")

        # Monthly breakdown for current year
        lines.append("\n*Por mes:*")
        month_names = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        for m in range(1, current_month + 1):
            count = monthly_counts.get(m, 0)
            bar = "█" * min(count, 20) if count else "—"
            lines.append(f"  {month_names[m-1]}: {bar} *{count}*")

        return "\n".join(lines)

    # ── Puntos del mes ─────────────────────────────────────────

    async def get_puntos(self) -> str:
        """Return monthly scoring summary."""
        result = await self._request(SCORING_URL)
        if not result or not isinstance(result, list):
            return "⚠️ No he podido cargar los puntos del mes."

        now = datetime.now(MADRID_TZ)
        current_year = now.year
        current_month = now.month

        # Filter current month entries
        month_entries = []
        for entry in result:
            if not isinstance(entry, dict):
                continue
            try:
                year = int(entry.get("year", 0))
                month = int(entry.get("month", 0))
            except (ValueError, TypeError):
                continue
            if year == current_year and month == current_month:
                month_entries.append(entry)

        # Sort by day
        month_entries.sort(key=lambda e: int(e.get("day", 0)))

        month_names = SPANISH_MONTHS
        month_label = month_names[current_month - 1].capitalize()

        if not month_entries:
            return f"🏅 *Puntos de {month_label} {current_year}*\n\nAún no hay puntos registrados este mes."

        total_points = 0
        positive_days = 0
        negative_days = 0
        lines = [f"🏅 *Puntos de {month_label} {current_year}*\n"]

        for entry in month_entries:
            try:
                day = int(entry.get("day", 0))
                points = int(entry.get("total", 0))
                aux = entry.get("aux", "")
            except (ValueError, TypeError):
                continue

            total_points += points
            if points > 0:
                positive_days += 1
            elif points < 0:
                negative_days += 1

            sign = "+" if points >= 0 else ""
            icon = "🟢" if points > 0 else ("🔴" if points < 0 else "⚪")
            aux_text = f" _{self._esc(str(aux))}_" if aux else ""
            lines.append(f"  {icon} Día {day}: *{sign}{points}*{aux_text}")

        lines.insert(1, f"📈 Total acumulado: *{total_points:+d}* puntos")
        lines.insert(2, f"🟢 {positive_days} días positivos · 🔴 {negative_days} días negativos\n")

        # Current XP score
        score = await self._get_score_value()
        score_icon, rank = self._score_rank(score)
        lines.append(f"\n{score_icon} XP actual: *{score}* · Rango: *{self._esc(rank)}*")

        return "\n".join(lines)

    # ── Historial ───────────────────────────────────────────

    async def get_history(self) -> str:
        import re
        await self._ensure_session()
        if not self._logged_in:
            if not await self.login():
                return "⚠️ No he podido conectar con Yarig.ai ahora mismo."

        try:
            async with self._session.get(f"{YARIG_BASE}/tasks/history") as resp:
                if resp.status != 200:
                    return "⚠️ No he podido abrir el historial ahora mismo."
                html = await resp.text()

            # Parse table rows
            rows = re.findall(
                r'<tr[^>]*class="task-row[^"]*"[^>]*>(.*?)</tr>',
                html, re.DOTALL
            )
            if not rows:
                # Try simpler pattern
                rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)

            # Extract task descriptions from HTML
            tasks_found = []
            for row in rows[:20]:
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                if len(cells) >= 3:
                    # Clean HTML tags
                    clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                    clean = [c for c in clean if c]
                    if clean:
                        tasks_found.append(clean)

            if not tasks_found:
                return "📜 Aun no hay historial reciente para mostrar."

            lines = ["📜 *Historial de tareas*\n"]
            for t in tasks_found[:10]:
                desc = self._esc(" | ".join(t[:3]))
                lines.append(f"• {desc}")

            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"History error: {e}")
            return "⚠️ Ha fallado la carga del historial."

    # ── Pedir tarea a compañero ─────────────────────────────

    async def get_notifications(self) -> str:
        result = await self._request(NOTIFICATIONS_URL, method="GET")
        if not result:
            return "🔔 Sin notificaciones recientes"

        items = []
        if isinstance(result, dict):
            for key in ("notifications", "data", "items", "rows"):
                value = result.get(key)
                if isinstance(value, list):
                    items = value
                    break
            if not items and all(not isinstance(v, (dict, list)) for v in result.values()):
                items = [result]
        elif isinstance(result, list):
            items = result

        if not items:
            return "🔔 Sin notificaciones recientes"

        lines = ["🔔 *Notificaciones Yarig*\n"]
        for item in items[:10]:
            if isinstance(item, dict):
                title = self._esc(
                    str(
                        item.get("title")
                        or item.get("notification")
                        or item.get("text")
                        or item.get("message")
                        or item.get("description")
                        or "Notificación"
                    ).strip()
                )
                subtitle = self._esc(
                    str(
                        item.get("datetime")
                        or item.get("created")
                        or item.get("date")
                        or item.get("hour")
                        or ""
                    ).strip()
                )
                state = item.get("state") or item.get("read")
                unread = str(state) in ("0", "false", "False", "")
                prefix = "🆕" if unread else "•"
                line = f"{prefix} {title}"
                if subtitle:
                    line += f" — _{subtitle}_"
                lines.append(line)
            else:
                lines.append(f"• {self._esc(str(item))}")
        return "\n".join(lines)

    async def find_mate(self, name: str) -> dict | None:
        name_lower = name.lower()

        cached_mates = await self.get_team_data()
        for mate in cached_mates:
            if name_lower in mate.get("name", "").lower():
                return mate

        result = await self._request(USERS_URL, {"term": name})
        if not result or not result.get("mates"):
            return None
        mates = result["mates"]
        for mate in mates:
            if name_lower in mate.get("name", "").lower():
                return mate
        return mates[0] if mates else None

    def _normalize_request_item(self, item: dict) -> dict:
        request_id = str(
            item.get("id")
            or item.get("request_id")
            or item.get("id_task_request")
            or item.get("task_request_id")
            or ""
        ).strip()
        sender = (
            item.get("sender")
            or item.get("from")
            or item.get("name")
            or item.get("user")
            or item.get("requester")
            or item.get("mate")
            or "Compañero"
        )
        text_value = (
            item.get("text")
            or item.get("description")
            or item.get("task")
            or item.get("title")
            or item.get("message")
            or item.get("request")
            or "Petición sin texto"
        )
        priority_raw = str(item.get("type") or item.get("priority") or item.get("request_type") or "2")
        created = str(item.get("datetime") or item.get("created") or item.get("date") or item.get("hour") or "").strip()
        return {
            "id": request_id,
            "sender": str(sender).strip(),
            "text": str(text_value).strip(),
            "priority": priority_raw,
            "created": created,
            "raw": item,
        }

    async def get_unread_requests_data(self) -> list[dict]:
        result = await self._request(UNREAD_REQUESTS_URL)
        items = []
        if isinstance(result, list):
            items = result
        elif isinstance(result, dict):
            for key in ("requests", "data", "items", "rows"):
                value = result.get(key)
                if isinstance(value, list):
                    items = value
                    break
        normalized = []
        for item in items:
            if isinstance(item, dict):
                normalized.append(self._normalize_request_item(item))
        return [item for item in normalized if item.get("id")]

    async def get_unread_requests_summary(self) -> str:
        requests = await self.get_unread_requests_data()
        if not requests:
            return "📥 *Peticiones Yarig*\n\nSin peticiones pendientes."

        lines = ["📥 *Peticiones Yarig*\n"]
        priority_labels = {"1": "◌ Sugerencia", "2": "▣ Peticion", "3": "⚠ Urgencia"}
        for idx, request in enumerate(requests[:10], 1):
            sender = self._esc(request["sender"])
            text_value = self._esc(request["text"])
            pr = priority_labels.get(str(request["priority"]), "▣ Peticion")
            line = f"{idx}. {pr} de *{sender}*\n_{text_value}_"
            if request.get("created"):
                line += f"\n🕒 {self._esc(request['created'])}"
            lines.append(line)
        return "\n\n".join(lines)

    async def mark_request_state(self, request_id: str, state: int) -> str:
        payloads = [
            {"id": request_id, "state": state},
            {"request": request_id, "state": state},
            {"rid": request_id, "state": state},
        ]
        result = None
        for payload in payloads:
            result = await self._request(UPDATE_REQUEST_STATE_URL, payload)
            if result not in (None, False):
                break
        if result in (None, False):
            return "⚠️ No he podido actualizar esa peticion."
        return "☑ Peticion actualizada"

    async def accept_request(self, request_id: str) -> str:
        open_payloads = [
            {"id": request_id},
            {"request": request_id},
            {"rid": request_id},
        ]
        opened = None
        for payload in open_payloads:
            opened = await self._request(OPEN_TASK_FROM_REQUEST_URL, payload)
            if opened not in (None, False):
                break
        state_result = await self.mark_request_state(request_id, 2)
        if opened not in (None, False):
            return "☑ Peticion aceptada y convertida en mision"
        if state_result.startswith("✅"):
            return "☑ Peticion aceptada"
        return "⚠️ No he podido aceptar esa peticion."

    async def send_request(self, user_id: str, text: str, req_type: int = 2) -> str:
        result = await self._request(ADD_REQUEST_URL, {
            "addressees": user_id,
            "text": text,
            "type": req_type,
        })
        if result:
            types = {1: "Sugerencia", 2: "Petición", 3: "Urgencia"}
            return f"☑ {types.get(req_type, 'Peticion')} enviada"
        return "⚠️ No he podido enviar la peticion."

    # ── Proyectos ───────────────────────────────────────────

    async def search_projects(
        self,
        term: str = "",
        customer_id: str = "2396",
        refresh: bool = False,
        limit: int | None = None,
    ) -> list[dict]:
        cache_key = f"{customer_id}:{term.strip().lower() or '*'}"
        cached = self._projects_cache.get(cache_key)
        if not refresh and self._cache_is_fresh(cached):
            projects = cached.get("items", [])
            return projects[:limit] if limit is not None else projects

        result = await self._request(PROJECTS_URL, {"term": term, "customer": customer_id})
        projects = result if isinstance(result, list) else []
        if projects:
            self._projects_cache[cache_key] = {"ts": time.time(), "items": projects}
        return projects[:limit] if limit is not None else projects

    async def find_project(self, term: str, customer_id: str = "2396") -> dict | None:
        term_lower = term.lower()
        direct_matches = await self.search_projects(term=term, customer_id=customer_id)
        for project in direct_matches:
            label = (project.get("label") or project.get("value") or "").lower()
            if term_lower in label:
                return project

        cached_projects = await self.search_projects(term="", customer_id=customer_id)
        for project in cached_projects:
            label = (project.get("label") or project.get("value") or "").lower()
            if term_lower in label:
                return project

        return direct_matches[0] if direct_matches else None

    async def list_projects(self, term: str = "", customer_id: str = "2396") -> str:
        projects = await self.search_projects(term=term, customer_id=customer_id)
        if not projects:
            return "⚠️ No se encontraron proyectos"

        header = "📁 *Proyectos*\n"
        if term:
            header = f"📁 *Proyectos* — filtro: _{self._esc(term)}_\n"

        lines = [header]
        for project in projects[:15]:
            name = self._esc(project.get("label", project.get("value", "?")))
            pid = project.get("id", "?")
            lines.append(f"• {name} (id: {pid})")
        return "\n".join(lines)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
