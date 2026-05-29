import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text, inspect as sa_inspect
from app.database import Base, engine
from app.routers import auth, clients, quotes, materials


def _migrate_users_table():
    """Add new columns to users table without dropping existing data."""
    with engine.connect() as conn:
        existing = {c["name"] for c in sa_inspect(engine).get_columns("users")}
        additions = {
            "business_name": "VARCHAR(255)",
            "phone": "VARCHAR(50)",
            "address": "VARCHAR(500)",
            "rec_licence": "VARCHAR(100)",
            "logo": "TEXT",
        }
        for col, col_type in additions.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {col_type}"))
        conn.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate_users_table()
    yield


app = FastAPI(
    title="Electrician Quotes API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(quotes.router)
app.include_router(materials.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Web frontend ──────────────────────────────────────────────
FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
def serve_login():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


@app.get("/dashboard")
def serve_dashboard():
    return FileResponse(os.path.join(FRONTEND, "dashboard.html"))


@app.get("/quote")
def serve_quote_detail():
    return FileResponse(os.path.join(FRONTEND, "quote-detail.html"))
