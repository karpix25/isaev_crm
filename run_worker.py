import asyncio
import logging
import signal

from src.services.background_job_service import start_background_job_loop
from src.services.followup_service import start_followup_loop
from src.services.whatsapp.evolution_monitor_service import start_evolution_monitor_loop


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("crm_worker")


async def main() -> None:
    stop_event = asyncio.Event()

    def stop() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, stop)
        except NotImplementedError:
            pass

    logger.info("Starting CRM background worker")
    followup_task = asyncio.create_task(start_followup_loop(stop_event=stop_event))
    background_jobs_task = asyncio.create_task(start_background_job_loop(stop_event=stop_event))
    evolution_monitor_task = asyncio.create_task(start_evolution_monitor_loop(stop_event=stop_event))

    await stop_event.wait()
    logger.info("Stopping CRM background worker")
    for task in (followup_task, background_jobs_task, evolution_monitor_task):
        task.cancel()
    for task in (followup_task, background_jobs_task, evolution_monitor_task):
        try:
            await task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
