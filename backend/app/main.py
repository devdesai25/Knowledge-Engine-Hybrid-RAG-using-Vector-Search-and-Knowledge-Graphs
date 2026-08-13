import logging

from fastapi import FastAPI

from backend.app.core.logging import setup_logging
from backend.app.routes import upload, chat

setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI()

logger.info("Application Started")

app.include_router(upload)
app.include_router(chat)