import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from rag.store import ingest_knowledge_base, is_knowledge_base_ingested, get_collection_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("policybridge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure knowledge base is ingested
    if is_knowledge_base_ingested():
        stats = get_collection_stats()
        logger.info(f"Knowledge base already ingested: {stats['total']} chunks across {len(stats['frameworks'])} frameworks")
        for fw, count in sorted(stats["frameworks"].items()):
            logger.info(f"  {fw}: {count} chunks")
    else:
        logger.info("Ingesting knowledge base into ChromaDB...")
        ingest_knowledge_base()
        stats = get_collection_stats()
        logger.info(f"Ingestion complete: {stats['total']} chunks across {len(stats['frameworks'])} frameworks")
    yield


app = FastAPI(title="PolicyBridge API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
