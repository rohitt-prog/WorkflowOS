import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # MongoDB settings
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "workflowos")
    
    # Server configuration
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # CORS: Allowed origins for frontend access
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    
    # AI / Gemini Configuration (Phase 3)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Playwright / Automation Configuration (Phase 4.3)
    PLAYWRIGHT_BASE_URL: str = os.getenv("PLAYWRIGHT_BASE_URL", "http://localhost:3000")
    PLAYWRIGHT_HEADLESS: bool = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() in ("true", "1", "yes")
    
    @property
    def cors_origins(self) -> List[str]:
        # Return unique list of configured origins
        origins = []
        for raw in self.FRONTEND_ORIGIN.split(","):
            cleaned = raw.strip()
            if cleaned and cleaned not in origins:
                origins.append(cleaned)
        if "http://localhost:3000" not in origins:
            origins.append("http://localhost:3000")
        if "http://127.0.0.1:3000" not in origins:
            origins.append("http://127.0.0.1:3000")
        return [o.rstrip("/") for o in origins if o]

settings = Settings()
