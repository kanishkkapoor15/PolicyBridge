"""FastAPI route definitions — skeleton to be implemented in step 6."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "PolicyBridge"}
