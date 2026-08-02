import logging
import logging.handlers
import os

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logging():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    # File handler — everything
    fh = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, 'prompt_builder.log'),
        maxBytes=10 * 1024 * 1024, backupCount=5
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s'))
    root.addHandler(fh)

    # Console — INFO+ to stderr
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(levelname)s [%(name)s] %(message)s'))
    root.addHandler(ch)

    # Dedicated error log
    eh = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, 'error.log'),
        maxBytes=5 * 1024 * 1024, backupCount=3
    )
    eh.setLevel(logging.WARNING)
    eh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s\nTRACEBACK: %(exc_info)s'))
    root.addHandler(eh)

    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
