import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.database import init_indexes, close_mongo_connection
from backend.routes.events import router as events_router
from backend.routes.discovery import router as discovery_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("workflowos")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure indexes are initialized
    logger.info("Starting up WorkFlowOS backend...")
    await init_indexes()
    yield
    # Shutdown: cleanly close database client
    logger.info("Shutting down WorkFlowOS backend...")
    await close_mongo_connection()

app = FastAPI(
    title="WorkFlowOS API",
    description="Observational Event Ingestion & Workflow OS Backend - Phase 1",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok"}

# Include routers
app.include_router(events_router)
app.include_router(discovery_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=True)
