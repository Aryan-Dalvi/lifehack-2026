from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.router import router as agent_router
from app.db import init_databases
from app.settings import settings
from merchant.router import catalog_router, consumer_router, merchant_router
from payments import visa_client
from payments.router import bank_router, pay_router, trust_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_databases()
    from seed.reset import seed_if_empty

    seed_if_empty()
    yield


app = FastAPI(
    title="Sway Skincare Commerce API",
    version="0.1.0",
    description="Grounded conversational shopping with explicit consent and TAP-shaped payment verification.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https?://.*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)
app.include_router(merchant_router)
app.include_router(catalog_router)
app.include_router(consumer_router)
app.include_router(bank_router)
app.include_router(pay_router)
app.include_router(trust_router)


@app.get("/health")
def health() -> dict[str, str | bool]:
    payment_ready = True
    if settings.payment_adapter == "visa":
        try:
            visa_client.validate_configuration()
        except visa_client.VisaConfigurationError:
            payment_ready = False
    return {
        "status": "ok",
        "category": "skincare",
        "payment_mode": settings.payment_adapter,
        "payment_ready": payment_ready,
    }


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Sway Skincare Commerce API",
        "docs": "/docs",
        "health": "/health",
    }

