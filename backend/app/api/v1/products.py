import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_profile, require_roles
from app.core.constants import UserRole
from app.db.session import get_db
from app.models.product import Product
from app.models.profile import Profile
from app.schemas.product import ProductCreateRequest, ProductResponse, ProductUpdateRequest

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductResponse])
async def list_products(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[Product]:
    stmt: Select[tuple[Product]] = select(Product)
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    if category:
        stmt = stmt.where(Product.category.ilike(category))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(Product.name.ilike(pattern), Product.description.ilike(pattern)))

    stmt = stmt.order_by(Product.created_at.desc()).offset(offset).limit(limit)
    return list((await db.scalars(stmt)).all())


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Product:
    product = await db.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.post("", response_model=ProductResponse)
async def create_product(
    payload: ProductCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(require_roles(UserRole.ARTISAN, UserRole.ADMIN)),
) -> Product:
    product = Product(artist_id=current_profile.id, **payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    is_admin = current_profile.role == UserRole.ADMIN.value
    if not is_admin and product.artist_id != current_profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(product, field_name, value)

    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", response_model=ProductResponse)
async def archive_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    is_admin = current_profile.role == UserRole.ADMIN.value
    if not is_admin and product.artist_id != current_profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    product.is_active = False
    await db.commit()
    await db.refresh(product)
    return product
