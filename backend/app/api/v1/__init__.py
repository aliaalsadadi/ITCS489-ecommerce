from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.artisans import router as artisans_router
from app.api.v1.auth import router as auth_router
from app.api.v1.auctions import router as auctions_router
from app.api.v1.cart import router as cart_router
from app.api.v1.orders import router as orders_router
from app.api.v1.products import router as products_router

api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(artisans_router)
api_router.include_router(auth_router)
api_router.include_router(products_router)
api_router.include_router(cart_router)
api_router.include_router(orders_router)
api_router.include_router(auctions_router)
