"""
Main FastAPI application.

Роутеры разделены по зонам ответственности:
- routers/navigation.py — навигация бота (Артём): шаги, профиль, SOS, шаблоны, и т.д.
- routers/internal.py   — внутренний бекенд (разработчик): состояние, фреймы, платежи, шифрование
"""

from fastapi import FastAPI
from dotenv import load_dotenv
import pathlib

from api.routers.navigation import router as navigation_router
from api.routers.internal import router as internal_router

env_path = pathlib.Path(__file__).parent.parent.parent / "backend.env"
load_dotenv(env_path)

app = FastAPI(title="12STEPS Chat API")


# ---------------------------------------------------------------------------
#  Health checks (shared)
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Health check endpoint for Render and monitoring"""
    return {"status": "ok", "service": "twelvesteps-backend"}

@app.get("/")
async def root():
    """Root endpoint for basic health check"""
    return {"status": "ok", "service": "twelvesteps-backend", "message": "API is running"}


# ---------------------------------------------------------------------------
#  Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Initialize profile sections and update step descriptions on application startup"""
    try:
        from db.init_profile_sections import init_profile_sections
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, init_profile_sections)
        print("✅ Profile sections initialized (if needed)")
    except Exception as e:
        print(f"⚠️ Warning: Could not initialize profile sections on startup: {e}")
        import traceback
        traceback.print_exc()

    try:
        from api.update_step_descriptions import update_step_descriptions
        await update_step_descriptions()
        print("✅ Step descriptions updated")
    except Exception as e:
        print(f"⚠️ Warning: Could not update step descriptions on startup: {e}")
        import traceback
        traceback.print_exc()


# ---------------------------------------------------------------------------
#  Include routers
# ---------------------------------------------------------------------------

app.include_router(navigation_router)
app.include_router(internal_router)
