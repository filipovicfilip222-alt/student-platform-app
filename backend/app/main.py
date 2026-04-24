from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.core.config import settings
from app.api.v1 import auth, professors, students

# ── Future router imports (uncomment as features are built) ───────────────────
# from app.api.v1 import users, students, professors, appointments
# from app.api.v1 import admin, search, notifications, document_requests


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize connections, warm caches, etc.
    yield
    # Shutdown: close connections


app = FastAPI(
    title="Studentska Platforma API",
    description="Platforma za zakazivanje konsultacija između studenata i profesora FON-a i ETF-a.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
# app.include_router(users.router,          prefix="/api/v1/users",         tags=["Users"])
app.include_router(students.router,       prefix="/api/v1/students",      tags=["Students"])
app.include_router(professors.router,     prefix="/api/v1/professors",    tags=["Professors"])
# app.include_router(appointments.router,   prefix="/api/v1/appointments",  tags=["Appointments"])
# app.include_router(admin.router,          prefix="/api/v1/admin",         tags=["Admin"])
# app.include_router(search.router,         prefix="/api/v1/search",        tags=["Search"])
# app.include_router(notifications.router,  prefix="/api/v1/notifications", tags=["Notifications"])


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["Health"], summary="Service health check")
async def health_check() -> dict:
    return {
        "status": "ok",
        "service": "studentska-platforma-api",
        "version": "1.0.0",
        "environment": settings.APP_ENV,
    }
