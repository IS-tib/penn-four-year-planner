"""Application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, SessionLocal, engine
from .routers import auth, courses, plans, programs, shared
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
app.include_router(programs.router)
app.include_router(shared.router)


@app.get("/", tags=["meta"])
def root() -> dict:
    """Say what this service is.

    Without this the bare URL answers with FastAPI's 404, which reads as a
    broken deployment to anyone who pastes the API address into a browser.
    """
    return {
        "service": "Penn Four Year Planner API",
        "docs": "/docs",
        "health": "/api/health",
        "frontend": "This is the API. The app itself is deployed separately.",
    }


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/limits", tags=["meta"])
def limits() -> dict:
    """Course-load thresholds, so the frontend does not hardcode Penn's rules."""
    return {
        "min_term_credits": settings.min_term_credits,
        "max_term_credits": settings.max_term_credits,
        "balanced_term_credits": settings.balanced_term_credits,
        "max_terms": settings.terms_per_plan,
    }
