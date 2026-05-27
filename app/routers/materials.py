from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.material import Material
from app.models.user import User
from app.schemas.material import MaterialCreate, MaterialUpdate, MaterialOut
from app.auth import get_current_user

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("", response_model=list[MaterialOut])
def list_materials(
    q: str | None = None,
    category: str | None = None,
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Material).filter(Material.is_active == True)
    if q:
        query = query.filter(Material.name.ilike(f"%{q}%"))
    if category:
        query = query.filter(Material.category == category)
    return query.order_by(Material.name).offset(skip).limit(limit).all()


@router.get("/categories", response_model=list[str])
def list_categories(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = (
        db.query(Material.category)
        .filter(Material.category.isnot(None), Material.is_active == True)
        .distinct()
        .order_by(Material.category)
        .all()
    )
    return [r[0] for r in rows]


@router.post("", response_model=MaterialOut, status_code=201)
def create_material(
    body: MaterialCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    material = Material(**body.model_dump())
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.get("/{material_id}", response_model=MaterialOut)
def get_material(
    material_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(404, "Material not found")
    return material


@router.patch("/{material_id}", response_model=MaterialOut)
def update_material(
    material_id: int,
    body: MaterialUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(404, "Material not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(material, field, value)
    db.commit()
    db.refresh(material)
    return material


@router.delete("/{material_id}", status_code=204)
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(404, "Material not found")
    material.is_active = False  # soft delete
    db.commit()
