from loguru import logger
from datetime import datetime
from pathlib import Path
__all__ = ['logger']

ROOT_DIR = Path(__file__).parent.parent
LOG_DIR = ROOT_DIR / "logs"
logger.add(LOG_DIR/f"{datetime.now().strftime('%y%m%d-%H%M%S')}.log", rotation="1 MB", compression="zip", enqueue=True)