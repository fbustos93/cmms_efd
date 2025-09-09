import logging
import pytz
from datetime import datetime

CHILE_TZ = pytz.timezone("America/Santiago")
LOG_FILE = "main.log"
LOG_TIME_FORMAT1 = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger("CMMS_LOGGER")
logger.setLevel(logging.DEBUG)

if not logger.hasHandlers():
    fh = logging.FileHandler(LOG_FILE)
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt=LOG_TIME_FORMAT1
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)
def LOG_TIME_FORMAT() -> str:
    return datetime.now(CHILE_TZ).strftime(LOG_TIME_FORMAT1)
