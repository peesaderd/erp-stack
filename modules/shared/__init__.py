# Shared Module — ERP Stack
# Shared database, models, utils for all micro-services
"""
Shared module for ERP Stack micro-services.

ทุก module import จาก shared:
    from shared.database import get_db, Base
    from shared.models import User, Transaction
    from shared.erp_bridge import register_module
"""

__version__ = "1.0.0"
