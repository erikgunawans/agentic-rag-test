import logging
from app.database import get_supabase_client

logger = logging.getLogger(__name__)


def log_action(
    user_id: str | None,
    user_email: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Write an audit log entry. Fire-and-forget — never raises."""
    try:
        client = get_supabase_client()
        client.table("audit_logs").insert(
            {
                "user_id": user_id,
                "user_email": user_email,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": details or {},
                "ip_address": ip_address,
            }
        ).execute()
    except Exception as e:
        logger.warning("Failed to write audit log: %s", e)
