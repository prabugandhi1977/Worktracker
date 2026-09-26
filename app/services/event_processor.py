"""
Converts raw RFID events into attendance, active work sessions and time logs.

This is the implementation of PRD sections FR-005 through FR-014: every RFID
scan flows through `process_rfid_event`, which is idempotent on `event_uid` so
at-least-once delivery from MQTT (QoS 1) or gateway retries never double-counts
a scan.
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.devices import CardStatus, ReaderType, RFIDCard, RFIDReader
from app.models.tracking import (
    ActiveWorkSession,
    Attendance,
    EventType,
    ExceptionRecord,
    ExceptionSeverity,
    RFIDEvent,
    SessionStatus,
    TimeLog,
)


def process_rfid_event(
    db: Session,
    *,
    event_uid: str,
    card_uid: str,
    reader_code: str,
    gateway_code: str,
    event_timestamp: datetime,
    raw_payload: dict,
) -> RFIDEvent:
    """Main entry point, called from both the MQTT listener and the HTTP fallback endpoint."""

    existing = db.query(RFIDEvent).filter(RFIDEvent.event_uid == event_uid).first()
    if existing is not None:
        return existing

    reader = db.query(RFIDReader).filter(RFIDReader.reader_code == reader_code).first()
    card = (
        db.query(RFIDCard)
        .filter(RFIDCard.uid == card_uid, RFIDCard.status == CardStatus.ACTIVE)
        .first()
    )

    event = RFIDEvent(
        event_uid=event_uid,
        card_uid=card_uid,
        reader_id=reader.id if reader else None,
        gateway_id=reader.gateway_id if reader else None,
        event_timestamp=event_timestamp,
        employee_id=card.employee_id if card else None,
        raw_payload=json.dumps(raw_payload, default=str),
    )

    if card is None or card.employee_id is None:
        event.event_type = EventType.UNKNOWN
        event.processed = True
        db.add(event)
        db.commit()
        _raise_exception(
            db,
            employee_id=None,
            work_date=event_timestamp.date(),
            exception_type="UNKNOWN_CARD",
            description=f"Unrecognized RFID UID '{card_uid}' scanned at reader '{reader_code}'",
            severity=ExceptionSeverity.HIGH,
        )
        db.refresh(event)
        return event

    if reader is None:
        event.event_type = EventType.UNKNOWN
        event.processed = True
        db.add(event)
        db.commit()
        _raise_exception(
            db,
            employee_id=card.employee_id,
            work_date=event_timestamp.date(),
            exception_type="UNKNOWN_READER",
            description=f"Event from unregistered reader '{reader_code}'",
            severity=ExceptionSeverity.MEDIUM,
        )
        db.refresh(event)
        return event

    reader.last_seen = event_timestamp

    if _is_duplicate(db, card.employee_id, reader.id, event_timestamp):
        event.is_duplicate = True
        event.processed = True
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    event_type = _resolve_event_type(db, reader, card.employee_id, event_timestamp)
    event.event_type = event_type
    db.add(event)
    db.flush()

    if event_type == EventType.ENTRY:
        _handle_entry(db, card.employee_id, event_timestamp)
    elif event_type == EventType.EXIT:
        _handle_exit(db, card.employee_id, event_timestamp)
    elif event_type == EventType.PROJECT_START:
        _handle_project_start(db, card.employee_id, reader, event_timestamp)
    elif event_type == EventType.BREAK_START:
        _handle_break_start(db, card.employee_id, reader, event_timestamp)
    elif event_type == EventType.BREAK_END:
        _handle_break_end(db, card.employee_id, event_timestamp)

    event.processed = True
    db.commit()
    db.refresh(event)
    return event


def _is_duplicate(db: Session, employee_id: int, reader_id: int, event_timestamp: datetime) -> bool:
    window = timedelta(seconds=settings.DEBOUNCE_SECONDS)
    last_event = (
        db.query(RFIDEvent)
        .filter(
            RFIDEvent.employee_id == employee_id,
            RFIDEvent.reader_id == reader_id,
            RFIDEvent.is_duplicate.is_(False),
        )
        .order_by(RFIDEvent.event_timestamp.desc())
        .first()
    )
    if last_event is None:
        return False
    return abs(event_timestamp - last_event.event_timestamp) < window


def _resolve_event_type(
    db: Session, reader: RFIDReader, employee_id: int, event_timestamp: datetime
) -> EventType:
    if reader.reader_type == ReaderType.GATE:
        todays_attendance = (
            db.query(Attendance)
            .filter(
                Attendance.employee_id == employee_id,
                Attendance.work_date == event_timestamp.date(),
            )
            .first()
        )
        if todays_attendance is None or todays_attendance.first_entry is None:
            return EventType.ENTRY
        return EventType.EXIT

    if reader.reader_type == ReaderType.BREAK:
        active_break = (
            db.query(ActiveWorkSession)
            .filter(
                ActiveWorkSession.employee_id == employee_id,
                ActiveWorkSession.status == SessionStatus.ACTIVE,
                ActiveWorkSession.is_break.is_(True),
            )
            .first()
        )
        return EventType.BREAK_END if active_break else EventType.BREAK_START

    # PROJECT / WORKSTATION readers identify the project/activity to start work on.
    return EventType.PROJECT_START


def _get_or_create_attendance(db: Session, employee_id: int, work_date) -> Attendance:
    attendance = (
        db.query(Attendance)
        .filter(Attendance.employee_id == employee_id, Attendance.work_date == work_date)
        .first()
    )
    if attendance is None:
        attendance = Attendance(employee_id=employee_id, work_date=work_date)
        db.add(attendance)
        db.flush()
    return attendance


def _handle_entry(db: Session, employee_id: int, event_timestamp: datetime) -> None:
    attendance = _get_or_create_attendance(db, employee_id, event_timestamp.date())
    if attendance.first_entry is None:
        attendance.first_entry = event_timestamp


def _handle_exit(db: Session, employee_id: int, event_timestamp: datetime) -> None:
    _close_active_session(db, employee_id, event_timestamp)

    attendance = _get_or_create_attendance(db, employee_id, event_timestamp.date())
    attendance.last_exit = event_timestamp
    _recompute_attendance_totals(attendance)


def _recompute_attendance_totals(attendance: Attendance) -> None:
    if attendance.first_entry and attendance.last_exit and attendance.last_exit > attendance.first_entry:
        gross = (attendance.last_exit - attendance.first_entry).total_seconds() / 60
    else:
        gross = 0
    break_minutes = float(attendance.break_minutes or 0)
    net = max(0.0, gross - break_minutes)
    normal_minutes = settings.NORMAL_DAILY_HOURS * 60

    attendance.gross_minutes = round(gross, 2)
    attendance.net_minutes = round(net, 2)
    attendance.overtime_minutes = round(max(0.0, net - normal_minutes), 2)


def _close_active_session(db: Session, employee_id: int, ended_at: datetime) -> Optional[TimeLog]:
    session = (
        db.query(ActiveWorkSession)
        .filter(ActiveWorkSession.employee_id == employee_id, ActiveWorkSession.status == SessionStatus.ACTIVE)
        .first()
    )
    if session is None:
        return None

    started_at = session.started_at
    if ended_at <= started_at:
        ended_at = started_at

    duration_minutes = round((ended_at - started_at).total_seconds() / 60, 2)

    time_log = TimeLog(
        employee_id=employee_id,
        project_id=session.project_id,
        activity_id=session.activity_id,
        start_time=started_at,
        end_time=ended_at,
        duration_minutes=duration_minutes,
        source="RFID",
        is_break=session.is_break,
        status="CONFIRMED",
    )
    db.add(time_log)

    if session.is_break:
        attendance = _get_or_create_attendance(db, employee_id, started_at.date())
        attendance.break_minutes = round(float(attendance.break_minutes or 0) + duration_minutes, 2)
        _recompute_attendance_totals(attendance)

    session.status = SessionStatus.CLOSED
    db.flush()
    return time_log


def _handle_project_start(db: Session, employee_id: int, reader: RFIDReader, event_timestamp: datetime) -> None:
    _close_active_session(db, employee_id, event_timestamp)

    if reader.default_project_id is None:
        _raise_exception(
            db,
            employee_id=employee_id,
            work_date=event_timestamp.date(),
            exception_type="MISSING_PROJECT_MAPPING",
            description=f"Reader '{reader.reader_code}' has no default project/activity configured",
            severity=ExceptionSeverity.MEDIUM,
        )

    session = ActiveWorkSession(
        employee_id=employee_id,
        project_id=reader.default_project_id,
        activity_id=reader.default_activity_id,
        reader_id=reader.id,
        is_break=False,
        started_at=event_timestamp,
        status=SessionStatus.ACTIVE,
    )
    db.add(session)
    db.flush()


def _handle_break_start(db: Session, employee_id: int, reader: RFIDReader, event_timestamp: datetime) -> None:
    _close_active_session(db, employee_id, event_timestamp)

    session = ActiveWorkSession(
        employee_id=employee_id,
        project_id=None,
        activity_id=None,
        reader_id=reader.id,
        is_break=True,
        started_at=event_timestamp,
        status=SessionStatus.ACTIVE,
    )
    db.add(session)
    db.flush()


def _handle_break_end(db: Session, employee_id: int, event_timestamp: datetime) -> None:
    _close_active_session(db, employee_id, event_timestamp)


def _raise_exception(
    db: Session,
    *,
    employee_id: Optional[int],
    work_date,
    exception_type: str,
    description: str,
    severity: ExceptionSeverity,
) -> None:
    record = ExceptionRecord(
        employee_id=employee_id,
        work_date=work_date,
        exception_type=exception_type,
        description=description,
        severity=severity,
    )
    db.add(record)
    db.commit()
