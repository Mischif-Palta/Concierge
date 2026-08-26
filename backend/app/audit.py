from uuid import UUID

from fastapi import APIRouter

from app.db import supabase


router = APIRouter(prefix="/audit", tags=["Audit"])


# ============================================================
# AUDIT LOGGER
# ============================================================

def log_event(
    session_id: UUID,
    action: str,
    details: dict | None = None,
):
    """
    Write an event to the audit_log table.
    """

    result = (
        supabase
        .table("audit_log")
        .insert({
            "session_id": str(session_id),
            "action": action,
            "details": details or {},
        })
        .execute()
    )

    if not result.data:
        raise RuntimeError(
            "Failed to write audit event"
        )

    return result.data[0]


# ============================================================
# GET SESSION AUDIT LOG
# ============================================================

@router.get("/session/{session_id}")
def get_session_audit(session_id: UUID):

    result = (
        supabase
        .table("audit_log")
        .select("*")
        .eq("session_id", str(session_id))
        .order("created_at", desc=False)
        .execute()
    )

    return {
        "session_id": str(session_id),
        "events": result.data or [],
        "count": len(result.data or []),
    }