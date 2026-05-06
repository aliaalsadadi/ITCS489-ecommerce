import uuid
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_profile, require_roles
from app.api.v1.admin import _log_action
from app.core.constants import AdminTargetType, OrderStatus, ProductAction, UserRole
from app.db.session import get_db
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.profile import Profile
from app.schemas.product import ProductCreateRequest, ProductResponse, ProductUpdateRequest

router = APIRouter(prefix="/products", tags=["products"])
POPULAR_ORDER_STATUSES = (
    OrderStatus.PAID.value,
    OrderStatus.PROCESSING.value,
    OrderStatus.SHIPPED.value,
    OrderStatus.DELIVERED.value,
)
UPLOAD_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/avif": ".avif",
    "image/bmp": ".bmp",
}
UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "products"


def _product_units_sold_subquery():
    return (
        select(
            OrderItem.product_id.label("product_id"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.status.in_(POPULAR_ORDER_STATUSES), OrderItem.product_id.is_not(None))
        .group_by(OrderItem.product_id)
        .subquery()
    )


def _product_response(
    product: Product,
    *,
    artist_name: str | None = None,
    artist_shop_name: str | None = None,
    artist_profile_image_url: str | None = None,
    units_sold: int | None = None,
) -> ProductResponse:
    return ProductResponse.model_validate(product).model_copy(
        update={
            "artist_name": artist_name,
            "artist_shop_name": artist_shop_name,
            "artist_profile_image_url": artist_profile_image_url,
            "units_sold": int(units_sold or 0),
        }
    )


def _guess_image_suffix(upload: UploadFile) -> str:
    if upload.content_type and upload.content_type in UPLOAD_MIME_TYPES:
        return UPLOAD_MIME_TYPES[upload.content_type]

    if upload.filename:
        suffix = Path(upload.filename).suffix.lower()
        if suffix:
            return suffix

    return ".bin"


async def _store_uploaded_image(request: Request, upload: UploadFile | None) -> str | None:
    if upload is None:
        return None

    if upload.content_type is None or not upload.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must be an image")

    image_bytes = await upload.read()
    filename = f"{uuid4().hex}{_guess_image_suffix(upload)}"
    file_path = UPLOAD_DIR / filename
    file_path.write_bytes(image_bytes)
    return str(request.url_for("product_images", path=filename))


async def _create_product(
    *,
    payload: dict,
    db: AsyncSession,
    current_profile: Profile,
    image_url: str | None = None,
) -> Product:
    product = Product(artist_id=current_profile.id, image_url=image_url, **payload)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Log product creation
    await _log_action(
        db,
        current_profile.id,
        ProductAction.CREATED.value,
        AdminTargetType.PRODUCT,
        str(product.id),
        {
            "name": product.name,
            "price": str(product.price),
            "stock_quantity": product.stock_quantity,
            "category": product.category,
        },
    )
    await db.commit()
    
    return product


@router.get("", response_model=list[ProductResponse])
async def list_products(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    artist_id: uuid.UUID | None = Query(default=None),
    sort: Literal["newest", "price_asc", "price_desc", "popular"] = Query(default="newest"),
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ProductResponse]:
    units_sold = _product_units_sold_subquery()
    stmt = (
        select(
            Product,
            Profile.full_name.label("artist_name"),
            Profile.shop_name.label("artist_shop_name"),
            Profile.profile_image_url.label("artist_profile_image_url"),
            func.coalesce(units_sold.c.units_sold, 0).label("units_sold"),
        )
        .join(Profile, Product.artist_id == Profile.id)
        .outerjoin(units_sold, Product.id == units_sold.c.product_id)
        .where(Profile.is_suspended.is_(False))
    )
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    if artist_id:
        stmt = stmt.where(Product.artist_id == artist_id)
    if category:
        stmt = stmt.where(Product.category.ilike(category))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(Product.name.ilike(pattern), Product.description.ilike(pattern)))

    if sort == "popular":
        stmt = stmt.order_by(func.coalesce(units_sold.c.units_sold, 0).desc(), Product.created_at.desc())
    elif sort == "price_asc":
        stmt = stmt.order_by(Product.price.asc(), Product.created_at.desc())
    elif sort == "price_desc":
        stmt = stmt.order_by(Product.price.desc(), Product.created_at.desc())
    else:
        stmt = stmt.order_by(Product.created_at.desc())

    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).all()
    return [
        _product_response(
            product,
            artist_name=artist_name,
            artist_shop_name=artist_shop_name,
            artist_profile_image_url=artist_profile_image_url,
            units_sold=units_sold_value,
        )
        for product, artist_name, artist_shop_name, artist_profile_image_url, units_sold_value in rows
    ]


@router.post("", response_model=ProductResponse)
async def create_product(
    payload: ProductCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(require_roles(UserRole.ARTISAN, UserRole.ADMIN)),
) -> Product:
    return await _create_product(payload=payload.model_dump(), db=db, current_profile=current_profile)


@router.post("/upload", response_model=ProductResponse)
async def create_product_with_image(
    request: Request,
    name: str = Form(..., max_length=255),
    description: str = Form(...),
    category: str = Form(..., max_length=120),
    price: Decimal = Form(..., gt=0),
    stock_quantity: int = Form(..., ge=0),
    image_file: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(require_roles(UserRole.ARTISAN, UserRole.ADMIN)),
) -> Product:
    payload = {
        "name": name,
        "description": description,
        "category": category,
        "price": price,
        "stock_quantity": stock_quantity,
    }
    image_url = await _store_uploaded_image(request, image_file)
    return await _create_product(payload=payload, db=db, current_profile=current_profile, image_url=image_url)


@router.get("/mine", response_model=list[ProductResponse])
async def list_my_products(
    include_inactive: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(require_roles(UserRole.ARTISAN, UserRole.ADMIN)),
) -> list[Product]:
    stmt: Select[tuple[Product]] = select(Product).where(Product.artist_id == current_profile.id)
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))

    stmt = stmt.order_by(Product.created_at.desc()).offset(offset).limit(limit)
    return list((await db.scalars(stmt)).all())


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ProductResponse:
    units_sold = _product_units_sold_subquery()
    stmt = (
        select(
            Product,
            Profile.full_name.label("artist_name"),
            Profile.shop_name.label("artist_shop_name"),
            Profile.profile_image_url.label("artist_profile_image_url"),
            func.coalesce(units_sold.c.units_sold, 0).label("units_sold"),
        )
        .join(Profile, Product.artist_id == Profile.id)
        .outerjoin(units_sold, Product.id == units_sold.c.product_id)
        .where(Product.id == product_id, Product.is_active.is_(True), Profile.is_suspended.is_(False))
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product, artist_name, artist_shop_name, artist_profile_image_url, units_sold_value = row
    return _product_response(
        product,
        artist_name=artist_name,
        artist_shop_name=artist_shop_name,
        artist_profile_image_url=artist_profile_image_url,
        units_sold=units_sold_value,
    )


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

    # Capture old values before update
    old_values = {
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "price": str(product.price),
        "stock_quantity": product.stock_quantity,
        "is_active": product.is_active,
    }
    
    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(product, field_name, value)

    await db.commit()
    await db.refresh(product)
    
    # Log product update with changed fields
    if updates:
        new_values = {k: str(getattr(product, k)) if isinstance(getattr(product, k), Decimal) else getattr(product, k) for k in updates.keys()}
        await _log_action(
            db,
            current_profile.id,
            ProductAction.UPDATED.value,
            AdminTargetType.PRODUCT,
            str(product.id),
            {
                "changed_fields": list(updates.keys()),
                "old_values": {k: old_values[k] for k in updates.keys()},
                "new_values": new_values,
            },
        )
        await db.commit()
    
    return product


@router.patch("/{product_id}/upload", response_model=ProductResponse)
async def update_product_with_image(
    product_id: uuid.UUID,
    request: Request,
    name: str | None = Form(default=None, max_length=255),
    description: str | None = Form(default=None),
    category: str | None = Form(default=None, max_length=120),
    price: Decimal | None = Form(default=None, gt=0),
    stock_quantity: int | None = Form(default=None, ge=0),
    is_active: bool | None = Form(default=None),
    image_file: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    current_profile: Profile = Depends(get_current_profile),
) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    is_admin = current_profile.role == UserRole.ADMIN.value
    if not is_admin and product.artist_id != current_profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    if name is not None:
        product.name = name
    if description is not None:
        product.description = description
    if category is not None:
        product.category = category
    if price is not None:
        product.price = price
    if stock_quantity is not None:
        product.stock_quantity = stock_quantity
    if is_active is not None:
        product.is_active = is_active

    image_url = await _store_uploaded_image(request, image_file)
    if image_url is not None:
        product.image_url = image_url

    await db.commit()
    await db.refresh(product)
    
    # Log product update with changed fields
    changed_fields = []
    if name is not None:
        changed_fields.append("name")
    if description is not None:
        changed_fields.append("description")
    if category is not None:
        changed_fields.append("category")
    if price is not None:
        changed_fields.append("price")
    if stock_quantity is not None:
        changed_fields.append("stock_quantity")
    if is_active is not None:
        changed_fields.append("is_active")
    if image_url is not None:
        changed_fields.append("image_url")
    
    if changed_fields:
        old_values = {
            "name": product.name,
            "description": product.description,
            "category": product.category,
            "price": str(product.price),
            "stock_quantity": product.stock_quantity,
            "is_active": product.is_active,
            "image_url": product.image_url,
        }
        await _log_action(
            db,
            current_profile.id,
            ProductAction.UPDATED.value,
            AdminTargetType.PRODUCT,
            str(product.id),
            {
                "changed_fields": changed_fields,
                "old_values": {k: old_values[k] for k in changed_fields},
            },
        )
        await db.commit()
    
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
    
    # Log product deletion (archiving)
    await _log_action(
        db,
        current_profile.id,
        ProductAction.DELETED.value,
        AdminTargetType.PRODUCT,
        str(product.id),
        {"archived": True},
    )
    await db.commit()
    
    return product


@router.post("/{product_id}/restore", response_model=ProductResponse)
async def restore_product(
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

    product.is_active = True
    await db.commit()
    await db.refresh(product)
    return product
