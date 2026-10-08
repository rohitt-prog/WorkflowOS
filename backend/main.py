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
from backend.routes.workflows import router as workflows_router
from backend.routes.privacy import router as privacy_router
from backend.routes.applications import router as applications_router
from backend.routes.system import router as system_router


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("workflowos")

async def restore_persistent_integrations() -> None:
    """
    Restores connection state for persistent integrations on backend startup.
    Loads encrypted credentials from MongoDB, decrypts them with WORKFLOWOS_CREDENTIAL_KEY,
    and updates adapter connection status without making unnecessary external API requests.
    """
    try:
        from integrations.registry import integration_registry
        from integrations.models import IntegrationStatus
        adapter = integration_registry.get("gmail")
        if not adapter:
            return

        storage = adapter._get_storage()
        if await storage.has_credential("gmail"):
            stored = await storage.get_credential("gmail")
            if stored and stored.get("access_token"):
                adapter._status = IntegrationStatus.CONNECTED
                adapter._last_error = None
                logger.info("[Startup] Restored persistent Gmail integration state (CONNECTED).")
            else:
                adapter._status = IntegrationStatus.ERROR
                adapter._last_error = "Stored Gmail credential could not be decrypted. Please reconnect."
                logger.warning("[Startup] Persistent Gmail credential exists but could not be decrypted. Set status to ERROR.")
    except Exception as e:
        logger.warning(f"[Startup] Error restoring persistent integrations: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure indexes are initialized and safely restore execution state
    logger.info("Starting up WorkFlowOS backend...")

    # SEC-05: Reject wildcard FRONTEND_ORIGIN to prevent cookie-bearing cross-origin leaks
    _raw_origin = settings.FRONTEND_ORIGIN
    if "*" in _raw_origin.split(","):
        raise RuntimeError(
            "SECURITY: FRONTEND_ORIGIN must not contain '*'. "
            "Set it to explicit origin(s) such as 'http://localhost:3000'."
        )

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

    # Restore persistent integration state from MongoDB (e.g. Gmail)
    await restore_persistent_integrations()

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
    description="AI-Powered Workflow Automation System",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    # Explicit header allowlist — avoids exposing arbitrary custom headers cross-origin
    allow_headers=["Content-Type", "Accept", "Authorization", "X-Request-ID"],
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
app.include_router(workflows_router)
app.include_router(privacy_router)
app.include_router(applications_router)
app.include_router(system_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=True)
