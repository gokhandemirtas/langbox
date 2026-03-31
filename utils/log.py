"""Central logging setup using Rich.

All modules import logger from here:
    from utils.log import logger

Call set_level(debug=True) once at boot to enable DEBUG output.
"""

import logging
import tempfile
from pathlib import Path

from rich.logging import RichHandler

LOG_FILE = Path(tempfile.gettempdir()) / "langbox_debug.log"

_handler = RichHandler(
    rich_tracebacks=True,
    show_path=False,
    markup=False,
    log_time_format="[%Y-%m-%d %H:%M:%S]",
)

# File handler for the debug web UI — truncated on each boot (mode="w")
_file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(
    "%(levelname)s|%(asctime)s|%(message)s",
    datefmt="%H:%M:%S",
))

logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    handlers=[_handler],
)

logger = logging.getLogger("langbox")
logger.setLevel(logging.INFO)
logger.addHandler(_file_handler)


def set_level(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)
    _file_handler.setLevel(level)
