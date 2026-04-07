"""Runner multi-bot — arranca los 8 consejeros de Telegram en un solo proceso."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from glob import glob
from pathlib import Path

from telegram.ext import Application

from src.consejero_bot import create_consejero_app

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Ruta a los perfiles — busca en AdmiraNext-Team (hermano) o local
PROFILES_PATHS = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "AdmiraNext-Team", "consejeros"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "consejeros"),
]


def find_profiles_dir() -> str:
    """Busca la carpeta de perfiles de consejeros."""
    for p in PROFILES_PATHS:
        resolved = os.path.abspath(p)
        if os.path.isdir(resolved):
            return resolved
    raise FileNotFoundError(
        f"No se encontro la carpeta de perfiles de consejeros. "
        f"Buscado en: {PROFILES_PATHS}"
    )


def load_all_profiles(profiles_dir: str) -> list[dict]:
    """Carga todos los perfiles JSON de consejeros."""
    profiles = []
    for path in sorted(glob(os.path.join(profiles_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            profile = json.load(f)
            profile["_file"] = os.path.basename(path)
            profiles.append(profile)
    return profiles


async def run_all():
    """Arranca todos los bots de consejeros en paralelo."""
    profiles_dir = find_profiles_dir()
    logger.info(f"Perfiles cargados de: {profiles_dir}")

    profiles = load_all_profiles(profiles_dir)
    if not profiles:
        logger.error("No se encontraron perfiles de consejeros")
        sys.exit(1)

    apps: list[Application] = []
    skipped: list[str] = []

    for profile in profiles:
        env_key = profile.get("bot_env_key", "")
        token = os.getenv(env_key, "")
        if not token:
            skipped.append(f"{profile['role']} ({env_key} no configurado)")
            continue

        app = create_consejero_app(token, profile)
        apps.append(app)

    if skipped:
        logger.warning(f"Consejeros sin token (saltados): {', '.join(skipped)}")

    if not apps:
        logger.error(
            "Ningun consejero tiene token configurado. "
            "Configura BOT_TOKEN_CEO, BOT_TOKEN_CFO, etc. en .env"
        )
        sys.exit(1)

    logger.info(f"Arrancando {len(apps)} bots de consejeros...")

    # Inicializar todos — tolerante a tokens invalidos, con reintentos
    running: list[Application] = []
    failed: list[Application] = []
    for app in apps:
        try:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(allowed_updates=["message", "callback_query"])
            running.append(app)
            logger.info(f"  -> {app.bot.first_name} (@{app.bot.username}) en linea")
            await asyncio.sleep(0.5)  # Espacio entre conexiones para evitar saturar TLS
        except Exception as e:
            logger.warning(f"  -> Fallo al arrancar un bot: {e}")
            failed.append(app)

    # Reintentar los fallidos tras una pausa
    if failed:
        logger.info(f"Reintentando {len(failed)} bots tras pausa...")
        await asyncio.sleep(3)
        for app in failed:
            try:
                await app.initialize()
                await app.start()
                await app.updater.start_polling(allowed_updates=["message", "callback_query"])
                running.append(app)
                logger.info(f"  -> {app.bot.first_name} (@{app.bot.username}) en linea (reintento)")
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"  -> Fallo definitivo: {e}")

    if not running:
        logger.error("Ningun bot pudo arrancar. Revisa los tokens.")
        sys.exit(1)

    apps = running
    logger.info(f"Consejeros en linea: {len(apps)}/{len(profiles)}")

    # Esperar hasta señal de parada
    stop_event = asyncio.Event()

    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: stop_event.set())
        await stop_event.wait()
    else:
        # Windows: add_signal_handler no funciona, usar sleep loop
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            pass

    # Shutdown
    logger.info("Apagando consejeros...")
    for app in apps:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

    logger.info("Todos los consejeros apagados")


def main():
    """Entry point."""
    from dotenv import load_dotenv
    load_dotenv(override=True)
    asyncio.run(run_all())


if __name__ == "__main__":
    main()
