import logging
import certifi
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from backend.config import settings

logger = logging.getLogger(__name__)

_mongo_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None

def get_client() -> AsyncIOMotorClient:
    global _mongo_client
    if _mongo_client is None:
        uri = settings.MONGODB_URI.strip()
        if not uri:
            logger.warning(
                "MONGODB_URI is not set in environment or .env file! "
                "Attempting in-memory mock client for development/testing."
            )
            try:
                import mongomock_motor
                _mongo_client = mongomock_motor.AsyncMongoMockClient()
                logger.info("Initialized in-memory mongomock_motor client.")
            except ImportError:
                raise RuntimeError(
                    "MONGODB_URI is not set and mongomock-motor is not installed. "
                    "Please set MONGODB_URI in your .env file."
                )
        else:
            logger.info("Connecting to MongoDB Atlas...")
            # Use certifi CA file to ensure valid SSL connection on macOS and other platforms
            client_kwargs = {
                "tlsCAFile": certifi.where(),
                "serverSelectionTimeoutMS": 5000,
            }
            _mongo_client = AsyncIOMotorClient(uri, **client_kwargs)
    return _mongo_client

def get_database() -> AsyncIOMotorDatabase:
    global _database
    if _database is None:
        client = get_client()
        _database = client[settings.MONGODB_DATABASE]
    return _database

async def init_indexes():
    """
    Ensure required indexes are created on startup:
    - timestamp (descending for recent event queries)
    - session_id
    - application
    """
    db = get_database()
    events_collection = db["events"]
    try:
        await events_collection.create_index([("timestamp", -1)])
        await events_collection.create_index([("session_id", 1)])
        await events_collection.create_index([("application", 1)])
        logger.info("MongoDB indexes verified on collection 'events'.")
    except Exception as e:
        logger.warning(f"Could not initialize MongoDB indexes: {e}")

async def close_mongo_connection():
    global _mongo_client, _database
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _database = None
        logger.info("MongoDB connection closed.")
