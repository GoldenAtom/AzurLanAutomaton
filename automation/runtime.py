import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import threading


def configure_logging(name):
    directory = Path(os.environ.get("AUTOMATON_LOG_DIR", Path(__file__).resolve().parents[1] / "logs"))
    directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
                        handlers=[logging.StreamHandler(), RotatingFileHandler(directory / (name + ".log"), maxBytes=2_000_000, backupCount=3)])


def run(stop, interval=30):
    log = logging.getLogger("automaton")
    log.info("Running in idle mode; no screenshots, taps, or game actions")
    while not stop.wait(interval):
        log.info("Heartbeat: idle framework is running")
    log.info("Stopped cleanly")


def main():
    configure_logging("automaton")
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    run(stop)
