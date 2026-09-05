"""Application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .catalog import (
    CATEGORY_ORDER,
    CATEGORY_TARGETS,
    PUBLISHED_DEGREE_TOTAL_CU,
    TRACKED_TOTAL_CU,
)
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import auth, courses, plans, shared
from .seed import seed_catalog


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_catalog(db)
    yield


app = FastAPI(
    title="Penn Four Year Planner",
    version="1.0.0",
    description=(
        "Plan a Penn Computer Science BSE degree across eight terms, with "
        "prerequisite and course-load checking done on the server."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    # Every method the API actually serves has to be listed, or the browser's
    # preflight fails and the request never arrives. PUT is what undo and redo
    # use, and it is invisible to the test client, which does not preflight.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(plans.router)
app.include_router(shared.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/requirements", tags=["meta"])
def requirements() -> dict:
    """The requirement buckets, so the frontend does not hardcode them."""
    return {
        "categories": [
            {"category": category, "target": CATEGORY_TARGETS[category]}
            for category in CATEGORY_ORDER
        ],
        "terms": settings.terms_per_plan,
        "min_term_credits": settings.min_term_credits,
        "max_term_credits": settings.max_term_credits,
        "tracked_total_credits": TRACKED_TOTAL_CU,
        "published_degree_credits": PUBLISHED_DEGREE_TOTAL_CU,
    }
