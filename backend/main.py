import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.database import init_indexes, close_mongo_connection
from backend.routes.events import router as events_router
from backend.routes.discovery import router as discovery_router
from backend.routes.ai import router as ai_router
from backend.routes.automation import router as automation_router
from backend.routes.integrations import router as integrations_router


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("workflowos")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure indexes are initialized and safely restore execution state
    logger.info("Starting up WorkFlowOS backend...")
    await init_indexes()
    try:
        from automation.service import automation_service
        loaded_count = await automation_service.load_executions_from_db()
        recovered_ids = await automation_service.recover_interrupted_executions()
        logger.info(
            f"Restored {loaded_count} execution records from MongoDB; "
            f"recovered {len(recovered_ids)} interrupted active executions."
        )
    except Exception as e:
        logger.warning(f"Could not load or recover executions during startup: {e}")

    yield

    # Shutdown: cleanly close active Playwright browser instances and database client
    logger.info("Shutting down WorkFlowOS backend...")
    try:
        from automation.playwright_executor import close_active_executors
        await close_active_executors()
    except Exception as e:
        logger.warning(f"Error during browser cleanup on shutdown: {e}")
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
app.include_router(ai_router)
app.include_router(automation_router)
app.include_router(integrations_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=True)
