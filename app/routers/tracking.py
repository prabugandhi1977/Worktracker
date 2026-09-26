from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Role, User
from app.models.tracking import (
    ActiveWorkSession,
    Attendance,
    CorrectionRequest,
    CorrectionStatus,
    ExceptionRecord,
    ExceptionStatus,
    SessionStatus,
    TimeLog,
)
from app.schemas import (
    ActiveSessionOut,
    AttendanceOut,
    CorrectionDecision,
    CorrectionRequestIn,
    CorrectionRequestOut,
    ExceptionOut,
    ExceptionResolve,
    TimeLogOut,
)
from app.security import get_current_user, require_roles

router = APIRouter(tags=["tracking"])

supervisor_or_admin = require_roles(Role.ADMIN.value, Role.SUPERVISOR.value, Role.HR.value)


@router.get("/attendance", response_model=list[AttendanceOut], dependencies=[Depends(get_current_user)])
def list_attendance(
    employee_id: int | None = None,
    work_date: date | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Attendance)
    if employee_id is not None:
        query = query.filter(Attendance.employee_id == employee_id)
    if work_date is not None:
        query = query.filter(Attendance.work_date == work_date)
    return query.order_by(Attendance.work_date.desc()).limit(500).all()


@router.get("/timelogs", response_model=list[TimeLogOut], dependencies=[Depends(get_current_user)])
def list_timelogs(
    employee_id: int | None = None,
    project_id: int | None = None,
    work_date: date | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(TimeLog)
    if employee_id is not None:
        query = query.filter(TimeLog.employee_id == employee_id)
    if project_id is not None:
        query = query.filter(TimeLog.project_id == project_id)
    if work_date is not None:
        query = query.filter(
            TimeLog.start_time >= work_date,
            TimeLog.start_time < work_date + timedelta(days=1),
        )
    return query.order_by(TimeLog.start_time.desc()).limit(500).all()


@router.get("/sessions/active", response_model=list[ActiveSessionOut], dependencies=[Depends(get_current_user)])
def list_active_sessions(employee_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(ActiveWorkSession).filter(ActiveWorkSession.status == SessionStatus.ACTIVE)
    if employee_id is not None:
        query = query.filter(ActiveWorkSession.employee_id == employee_id)
    return query.all()


@router.get("/exceptions", response_model=list[ExceptionOut], dependencies=[Depends(supervisor_or_admin)])
def list_exceptions(
    status_filter: str | None = None,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(ExceptionRecord)
    if status_filter is not None:
        query = query.filter(ExceptionRecord.status == ExceptionStatus(status_filter))
    if employee_id is not None:
        query = query.filter(ExceptionRecord.employee_id == employee_id)
    return query.order_by(ExceptionRecord.created_at.desc()).limit(500).all()


@router.post(
    "/exceptions/{exception_id}/resolve",
    response_model=ExceptionOut,
    dependencies=[Depends(supervisor_or_admin)],
)
def resolve_exception(
    exception_id: int,
    payload: ExceptionResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.get(ExceptionRecord, exception_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found")
    record.status = ExceptionStatus(payload.status)
    record.resolution = payload.resolution
    record.resolved_by = current_user.id
    db.commit()
    db.refresh(record)
    return record


@router.post("/corrections", response_model=CorrectionRequestOut, dependencies=[Depends(get_current_user)])
def request_correction(payload: CorrectionRequestIn, db: Session = Depends(get_db)):
    correction = CorrectionRequest(**payload.model_dump())
    db.add(correction)
    db.commit()
    db.refresh(correction)
    return correction


@router.get("/corrections", response_model=list[CorrectionRequestOut], dependencies=[Depends(get_current_user)])
def list_corrections(
    employee_id: int | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(CorrectionRequest)
    if employee_id is not None:
        query = query.filter(CorrectionRequest.employee_id == employee_id)
    if status_filter is not None:
        query = query.filter(CorrectionRequest.status == CorrectionStatus(status_filter))
    return query.order_by(CorrectionRequest.created_at.desc()).limit(500).all()


@router.post(
    "/corrections/{correction_id}/decide",
    response_model=CorrectionRequestOut,
    dependencies=[Depends(supervisor_or_admin)],
)
def decide_correction(
    correction_id: int,
    payload: CorrectionDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    correction = db.get(CorrectionRequest, correction_id)
    if correction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Correction request not found")
    if correction.status != CorrectionStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Correction already decided")

    correction.status = CorrectionStatus.APPROVED if payload.approve else CorrectionStatus.REJECTED
    correction.reviewed_by = current_user.id
    correction.reviewed_at = datetime.now(timezone.utc)

    if payload.approve and correction.time_log_id is not None:
        time_log = db.get(TimeLog, correction.time_log_id)
        if time_log is not None:
            # Original RFID events are never touched (PRD FR-015); only the derived TimeLog changes.
            if correction.requested_start is not None:
                time_log.start_time = correction.requested_start
            if correction.requested_end is not None:
                time_log.end_time = correction.requested_end
            time_log.duration_minutes = round(
                (time_log.end_time - time_log.start_time).total_seconds() / 60, 2
            )
            time_log.status = "CORRECTED"

    db.commit()
    db.refresh(correction)
    return correction
