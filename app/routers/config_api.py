"""Config + domain-mapping REST API (also driven by the settings UI)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DomainMapping
from ..schemas import ConfigIn, ConfigOut, DomainMappingIn, DomainMappingOut
from ..seed import get_config

router = APIRouter(prefix="/api/v1", tags=["config"])


@router.get("/config", response_model=ConfigOut)
def read_config(db: Session = Depends(get_db)) -> ConfigOut:
    return ConfigOut.model_validate(get_config(db))


@router.put("/config", response_model=ConfigOut)
def update_config(payload: ConfigIn, db: Session = Depends(get_db)) -> ConfigOut:
    config = get_config(db)
    for key, val in payload.model_dump().items():
        setattr(config, key, val)
    db.commit()
    db.refresh(config)
    return ConfigOut.model_validate(config)


@router.get("/domains", response_model=list[DomainMappingOut])
def list_domains(db: Session = Depends(get_db)) -> list[DomainMapping]:
    return list(db.execute(select(DomainMapping).order_by(DomainMapping.company)).scalars())


@router.post("/domains", response_model=DomainMappingOut, status_code=status.HTTP_201_CREATED)
def create_domain(payload: DomainMappingIn, db: Session = Depends(get_db)) -> DomainMapping:
    existing = db.execute(
        select(DomainMapping).where(DomainMapping.company == payload.company)
    ).scalar_one_or_none()
    if existing is not None:
        existing.domain = payload.domain
        db.commit()
        db.refresh(existing)
        return existing
    mapping = DomainMapping(company=payload.company, domain=payload.domain)
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@router.delete("/domains/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain(mapping_id: int, db: Session = Depends(get_db)) -> None:
    mapping = db.get(DomainMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    db.delete(mapping)
    db.commit()
