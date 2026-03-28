from fastapi import APIRouter

from .sessions import router as sessions_router
from .documents import router as documents_router
from .approvals import router as approvals_router
from .chat import router as chat_router
from .export import router as export_router
from .stream import router as stream_router
from .rag import router as rag_router

api_router = APIRouter()

api_router.include_router(sessions_router, tags=["Sessions"])
api_router.include_router(documents_router, tags=["Documents"])
api_router.include_router(approvals_router, tags=["Approvals"])
api_router.include_router(chat_router, tags=["Chat"])
api_router.include_router(export_router, tags=["Export"])
api_router.include_router(stream_router, tags=["Stream"])
api_router.include_router(rag_router, tags=["RAG"])
