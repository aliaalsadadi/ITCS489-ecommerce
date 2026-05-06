from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

import app.models  # noqa: F401
from app.api.v1 import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.services.auction_service import auto_close_expired_auctions
from app.services.ws_manager import auction_ws_manager

settings = get_settings()
logger = logging.getLogger(__name__)
PRODUCT_UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads" / "products"
PROFILE_UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads" / "profiles"
PRODUCT_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _ensure_order_tracking_columns() -> None:
    statements = [
        "ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS tracking_number text",
        "ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS shipping_carrier text",
        "ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS shipping_method text",
        "ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS estimated_delivery_at timestamptz",
        "CREATE INDEX IF NOT EXISTS idx_orders_tracking_number ON public.orders(tracking_number)",
    ]

    async with engine.begin() as conn:
        for statement in statements:
            await conn.execute(text(statement))


async def _auction_auto_close_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            async with AsyncSessionLocal() as db:
                closed_auctions = await auto_close_expired_auctions(db)
                for auction in closed_auctions:
                    await auction_ws_manager.broadcast(
                        auction.id,
                        {
                            "event": "auction_closed",
                            "auction_id": str(auction.id),
                            "winner_id": str(auction.highest_bidder_id) if auction.highest_bidder_id else None,
                            "final_bid": str(auction.current_highest_bid) if auction.highest_bidder_id else None,
                            "timestamp": _now_iso(),
                        },
                    )
        except Exception as exc:
            logger.warning("Auction auto-close sweep skipped due to error: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop_event = asyncio.Event()
    auto_close_task: asyncio.Task | None = None

    if settings.auto_create_tables:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as exc:
            logger.warning("Database initialization skipped due to connection error: %s", exc)

    try:
        await _ensure_order_tracking_columns()
    except Exception as exc:
        logger.warning("Order tracking column migration skipped due to database error: %s", exc)

    auto_close_task = asyncio.create_task(_auction_auto_close_loop(stop_event))

    yield

    stop_event.set()
    if auto_close_task is not None:
        auto_close_task.cancel()
        try:
            await auto_close_task
        except asyncio.CancelledError:
            pass

    await engine.dispose()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads/products", StaticFiles(directory=PRODUCT_UPLOADS_DIR), name="product_images")
app.mount("/uploads/profiles", StaticFiles(directory=PROFILE_UPLOADS_DIR), name="profile_images")

app.include_router(api_router, prefix=settings.api_v1_prefix)

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
