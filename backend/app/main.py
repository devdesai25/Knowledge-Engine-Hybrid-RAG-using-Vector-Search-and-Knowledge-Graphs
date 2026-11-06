import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from backend.app.lifespan_method import lifespan
from backend.app.core.logging import setup_logging
from backend.app.core.exceptions.exception_handlers import validation_exception_handler
from backend.app.routes import upload, chat, auth

setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI(title="Knowledge Engine API", lifespan=lifespan)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)

logger.info("Application Started")

app.include_router(upload)
app.include_router(chat)
app.include_router(auth)
