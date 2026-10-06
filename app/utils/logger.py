import logging
import colorlog
from app.utils.config import get_config

_cfg = get_config()

_LOG_COLORS = {
    "DEBUG":    "cyan",
    "INFO":     "green",
    "WARNING":  "yellow",
    "ERROR":    "red",
    "CRITICAL": "bold_red",
}

_SECONDARY_COLORS = {
    "asctime":  {"DEBUG": "white", "INFO": "white", "WARNING": "white", "ERROR": "white", "CRITICAL": "white"},
    "name":     {"DEBUG": "cyan",  "INFO": "blue",  "WARNING": "yellow","ERROR": "red",   "CRITICAL": "bold_red"},
}

_FMT = "%(asctime)s  %(log_color)s%(levelname)-8s%(reset)s  %(name_log_color)s%(name)s%(reset)s  %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def _setup():
    global _initialized
    if _initialized:
        return

    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            fmt=_FMT,
            datefmt=_DATEFMT,
            log_colors=_LOG_COLORS,
            secondary_log_colors=_SECONDARY_COLORS,
            reset=True,
        )
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, _cfg.LOG_LEVEL, logging.INFO))

    # remove any default handlers before adding ours
    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("werkzeug").setLevel(logging.INFO)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    _setup()
    return logging.getLogger(name)
