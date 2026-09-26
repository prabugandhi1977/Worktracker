from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Role
from app.models.devices import CardStatus, GatewayStatus, IoTGateway, Location, ReaderType, RFIDCard, RFIDReader
from app.schemas import (
    GatewayIn,
    GatewayOut,
    LocationIn,
    LocationOut,
    ReaderIn,
    ReaderOut,
    RFIDCardIn,
    RFIDCardOut,
)
from app.security import get_current_user, require_roles

router = APIRouter(tags=["devices"])

admin_only = require_roles(Role.ADMIN.value)


@router.post("/locations", response_model=LocationOut, dependencies=[Depends(admin_only)])
def create_location(payload: LocationIn, db: Session = Depends(get_db)):
    location = Location(**payload.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get("/locations", response_model=list[LocationOut], dependencies=[Depends(get_current_user)])
def list_locations(db: Session = Depends(get_db)):
    return db.query(Location).order_by(Location.name).all()


@router.post("/gateways", response_model=GatewayOut, dependencies=[Depends(admin_only)])
def create_gateway(payload: GatewayIn, db: Session = Depends(get_db)):
    if db.query(IoTGateway).filter(IoTGateway.gateway_code == payload.gateway_code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gateway code already exists")
    gateway = IoTGateway(**payload.model_dump())
    db.add(gateway)
    db.commit()
    db.refresh(gateway)
    return gateway


@router.get("/gateways", response_model=list[GatewayOut], dependencies=[Depends(get_current_user)])
def list_gateways(db: Session = Depends(get_db)):
    return db.query(IoTGateway).order_by(IoTGateway.name).all()


@router.post("/gateways/{gateway_id}/heartbeat", response_model=GatewayOut, dependencies=[Depends(get_current_user)])
def gateway_heartbeat(gateway_id: int, db: Session = Depends(get_db)):
    """Called periodically by the gateway itself (or its supervisor process) to report liveness."""
    gateway = db.get(IoTGateway, gateway_id)
    if gateway is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gateway not found")
    gateway.last_heartbeat = datetime.now(timezone.utc)
    gateway.status = GatewayStatus.ONLINE
    db.commit()
    db.refresh(gateway)
    return gateway


@router.post("/readers", response_model=ReaderOut, dependencies=[Depends(admin_only)])
def create_reader(payload: ReaderIn, db: Session = Depends(get_db)):
    if db.query(RFIDReader).filter(RFIDReader.reader_code == payload.reader_code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reader code already exists")
    data = payload.model_dump()
    data["reader_type"] = ReaderType(data["reader_type"])
    reader = RFIDReader(**data)
    db.add(reader)
    db.commit()
    db.refresh(reader)
    return reader


@router.get("/readers", response_model=list[ReaderOut], dependencies=[Depends(get_current_user)])
def list_readers(gateway_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(RFIDReader)
    if gateway_id is not None:
        query = query.filter(RFIDReader.gateway_id == gateway_id)
    return query.order_by(RFIDReader.name).all()


@router.post("/rfid-cards", response_model=RFIDCardOut, dependencies=[Depends(admin_only)])
def register_card(payload: RFIDCardIn, db: Session = Depends(get_db)):
    if db.query(RFIDCard).filter(RFIDCard.uid == payload.uid).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Card UID already registered")
    card = RFIDCard(**payload.model_dump())
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.get("/rfid-cards", response_model=list[RFIDCardOut], dependencies=[Depends(get_current_user)])
def list_cards(employee_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(RFIDCard)
    if employee_id is not None:
        query = query.filter(RFIDCard.employee_id == employee_id)
    return query.order_by(RFIDCard.id).all()


@router.post("/rfid-cards/{card_id}/assign", response_model=RFIDCardOut, dependencies=[Depends(admin_only)])
def assign_card(card_id: int, employee_id: int, db: Session = Depends(get_db)):
    card = db.get(RFIDCard, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    active_for_other = (
        db.query(RFIDCard)
        .filter(RFIDCard.employee_id == employee_id, RFIDCard.status == CardStatus.ACTIVE, RFIDCard.id != card_id)
        .first()
    )
    if active_for_other:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee already has an active card; deactivate it first",
        )
    card.employee_id = employee_id
    card.status = CardStatus.ACTIVE
    db.commit()
    db.refresh(card)
    return card


@router.post("/rfid-cards/{card_id}/deactivate", response_model=RFIDCardOut, dependencies=[Depends(admin_only)])
def deactivate_card(card_id: int, db: Session = Depends(get_db)):
    card = db.get(RFIDCard, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    card.status = CardStatus.INACTIVE
    card.deactivated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(card)
    return card
