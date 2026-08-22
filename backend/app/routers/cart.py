"""Shopping cart endpoints (Spec §8, R3).

Add / update-quantity / remove / view + subtotal. Adding or increasing quantity beyond the
available stock is rejected (Spec §8). Cart reads eager-load products via selectinload to
avoid an N+1 query per line item (Spec §16, G2).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_customer
from ..models import Cart, CartItem, Customer, Product
from ..schemas import AddCartItem, CartItemResponse, CartResponse, UpdateCartItem
from ..services.cart_query import load_cart_items

router = APIRouter(prefix="/api/cart", tags=["cart"])


def _get_or_create_cart(db: Session, customer_id: int) -> Cart:
    cart = db.scalar(
        select(Cart).where(Cart.customer_id == customer_id).options(selectinload(Cart.items))
    )
    if cart is None:
        cart = Cart(customer_id=customer_id)
        db.add(cart)
        db.flush()
    return cart


def _serialize_cart(db: Session, customer_id: int) -> CartResponse:
    """One query for items + their products (selectinload), then pure in-memory assembly."""
    rows = load_cart_items(db, customer_id)

    items, subtotal, count = [], 0.0, 0
    for item in rows:
        line_total = round(float(item.product.price) * item.quantity, 2)
        subtotal += line_total
        count += item.quantity
        items.append(
            CartItemResponse(
                id=item.id,
                product_id=item.product_id,
                name=item.product.name,
                price=float(item.product.price),
                quantity=item.quantity,
                stock_quantity=item.product.stock_quantity,
                line_total=line_total,
            )
        )
    return CartResponse(items=items, subtotal=round(subtotal, 2), item_count=count)


@router.get("", response_model=CartResponse)
def view_cart(
    db: Session = Depends(get_db), customer: Customer = Depends(get_current_customer)
) -> CartResponse:
    return _serialize_cart(db, customer.id)


@router.post("/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
def add_item(
    payload: AddCartItem,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
) -> CartResponse:
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    cart = _get_or_create_cart(db, customer.id)
    existing = db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product.id)
    )
    desired = (existing.quantity if existing else 0) + payload.quantity
    if desired > product.stock_quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {product.stock_quantity} in stock",
        )

    if existing:
        existing.quantity = desired
    else:
        db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=payload.quantity))
    db.commit()
    return _serialize_cart(db, customer.id)


@router.patch("/items/{item_id}", response_model=CartResponse)
def update_item(
    item_id: int,
    payload: UpdateCartItem,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
) -> CartResponse:
    item = _owned_item(db, item_id, customer.id)
    if payload.quantity > item.product.stock_quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {item.product.stock_quantity} in stock",
        )
    item.quantity = payload.quantity
    db.commit()
    return _serialize_cart(db, customer.id)


@router.delete("/items/{item_id}", response_model=CartResponse)
def remove_item(
    item_id: int,
    db: Session = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
) -> CartResponse:
    item = _owned_item(db, item_id, customer.id)
    db.delete(item)
    db.commit()
    return _serialize_cart(db, customer.id)


def _owned_item(db: Session, item_id: int, customer_id: int) -> CartItem:
    """Fetch a cart item and confirm it belongs to this customer (authorization, §25)."""
    item = db.scalar(
        select(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(CartItem.id == item_id, Cart.customer_id == customer_id)
        .options(selectinload(CartItem.product))
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")
    return item
