from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tracking import RFIDEvent
from app.schemas import RFIDEventIn, RFIDEventOut
from app.security import get_current_user
from app.services.event_processor import process_rfid_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/rfid", response_model=RFIDEventOut)
def ingest_rfid_event(payload: RFIDEventIn, db: Session = Depends(get_db)):
    """
    HTTP fallback for gateways that cannot reach the MQTT broker (PRD section 13:
    offline gateways should prefer local buffering + MQTT retry, but this gives
    edge devices, test tools and the FAT bench a synchronous alternative).
    """
    event = process_rfid_event(
        db,
        event_uid=payload.event_id,
        card_uid=payload.rfid_uid,
        reader_code=payload.reader_id,
        gateway_code=payload.gateway_id,
        event_timestamp=payload.timestamp,
        raw_payload=payload.model_dump(mode="json"),
    )
    return event


@router.get("/rfid", response_model=list[RFIDEventOut], dependencies=[Depends(get_current_user)])
def list_rfid_events(
    employee_id: int | None = None,
    work_date: date | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    query = db.query(RFIDEvent)
    if employee_id is not None:
        query = query.filter(RFIDEvent.employee_id == employee_id)
    if work_date is not None:
        query = query.filter(
            RFIDEvent.event_timestamp >= work_date,
            RFIDEvent.event_timestamp < work_date + timedelta(days=1),
        )
    return query.order_by(RFIDEvent.event_timestamp.desc()).limit(min(limit, 1000)).all()
