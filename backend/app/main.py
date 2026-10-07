import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, events, orders

# Uvicorn only sets up its own loggers. Show our app's INFO lines too, e.g. the
# confirmation "email", which runs inside the API when Celery runs tasks inline.
_app_logger = logging.getLogger("app")
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    _app_logger.addHandler(_handler)
    _app_logger.setLevel(logging.INFO)

app = FastAPI(title=settings.app_name)

# Browsers block a page on localhost:3000 from reading responses from localhost:8000
# unless the API says that origin is allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(orders.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
