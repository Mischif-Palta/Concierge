from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import UUID
from app.db import supabase

router = APIRouter(prefix="/sessions", tags=["Sessions"])

class SessionCreate(BaseModel):
    actor_type: str


class SessionResponse(BaseModel):
    session_id: UUID
    actor_type: str
    status: str


@router.post("", response_model=SessionResponse)
def create_session(payload: SessionCreate):
    if payload.actor_type not in ["chat", "bare_agent"]:
        raise HTTPException(
            status_code=400,
            detail="actor_type must be 'chat' or 'bare_agent'"
        )

    result = (
        supabase
        .table("sessions")
        .insert({
            "actor_type": payload.actor_type,
            "status": "active"
        })
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Failed to create session"
        )

    session = result.data[0]

    return {
        "session_id": session["id"],
        "actor_type": session["actor_type"],
        "status": session["status"]
    }


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: UUID):
    result = (
        supabase
        .table("sessions")
        .select("id, actor_type, status")
        .eq("id", str(session_id))
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    session = result.data[0]

    return {
        "session_id": session["id"],
        "actor_type": session["actor_type"],
        "status": session["status"]
    }