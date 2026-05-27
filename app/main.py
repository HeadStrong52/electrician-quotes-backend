from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routers import auth, clients, quotes, materials

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Electrician Quotes API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this once frontend domain is known
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
