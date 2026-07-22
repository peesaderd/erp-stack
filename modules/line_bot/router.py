"""LINE Bot — ERP Module Registration

Imports the main app so it can be loaded as an ERP Modular plugin.
"""

from .main import app
from .handlers import handle_webhook
from .line_client import line_client
from .line_richmenu import setup_rich_menus

__all__ = ["app", "handle_webhook", "line_client", "setup_rich_menus"]
