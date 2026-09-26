from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Employee
from app.models.projects import Project, ProjectStatus
from app.models.tracking import ActiveWorkSession, Attendance, ExceptionStatus, SessionStatus, TimeLog
from app.models.tracking import ExceptionRecord
from app.security import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _today() -> date:
    return datetime.now(timezone.utc).date()


@router.get("/live", dependencies=[Depends(get_current_user)])
def live_workforce(db: Session = Depends(get_db)):
    """FR-017: real-time snapshot of every employee with an open session or attendance today."""
    today = _today()
    attendance_rows = db.query(Attendance).filter(Attendance.work_date == today).all()
    active_sessions = {
        s.employee_id: s
        for s in db.query(ActiveWorkSession).filter(ActiveWorkSession.status == SessionStatus.ACTIVE).all()
    }

    now = datetime.now(timezone.utc)
    result = []
    for attendance in attendance_rows:
        employee = db.get(Employee, attendance.employee_id)
        session = active_sessions.get(attendance.employee_id)

        if attendance.last_exit and (not session):
            employee_status = "OFFLINE"
        elif session and session.is_break:
            employee_status = "BREAK"
        elif session:
            employee_status = "WORKING"
        else:
            employee_status = "IDLE"

        result.append(
            {
                "employee_id": attendance.employee_id,
                "employee_name": employee.name if employee else None,
                "department_id": employee.department_id if employee else None,
                "status": employee_status,
                "project_id": session.project_id if session else None,
                "activity_id": session.activity_id if session else None,
                "session_started_at": session.started_at if session else None,
                "duration_minutes": (
                    round((now - session.started_at).total_seconds() / 60, 1) if session else None
                ),
                "first_entry": attendance.first_entry,
                "last_exit": attendance.last_exit,
            }
        )
    return result


@router.get("/employee/{employee_id}", dependencies=[Depends(get_current_user)])
def employee_dashboard(employee_id: int, db: Session = Depends(get_db)):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    today = _today()
    attendance = (
        db.query(Attendance)
        .filter(Attendance.employee_id == employee_id, Attendance.work_date == today)
        .first()
    )
    session = (
        db.query(ActiveWorkSession)
        .filter(ActiveWorkSession.employee_id == employee_id, ActiveWorkSession.status == SessionStatus.ACTIVE)
        .first()
    )
    todays_logs = (
        db.query(TimeLog)
        .filter(
            TimeLog.employee_id == employee_id,
            TimeLog.start_time >= today,
            TimeLog.start_time < today + timedelta(days=1),
        )
        .all()
    )

    return {
        "employee": {"id": employee.id, "name": employee.name, "designation": employee.designation},
        "attendance_today": attendance,
        "active_session": session,
        "time_logs_today": todays_logs,
        "project_minutes_today": sum(float(t.duration_minutes) for t in todays_logs if not t.is_break),
        "break_minutes_today": sum(float(t.duration_minutes) for t in todays_logs if t.is_break),
    }


@router.get("/supervisor/{manager_id}", dependencies=[Depends(get_current_user)])
def supervisor_dashboard(manager_id: int, db: Session = Depends(get_db)):
    today = _today()
    team = db.query(Employee).filter(Employee.manager_id == manager_id).all()
    team_ids = [e.id for e in team]

    attendance_by_employee = {
        a.employee_id: a
        for a in db.query(Attendance).filter(
            Attendance.employee_id.in_(team_ids), Attendance.work_date == today
        ).all()
    }
    active_by_employee = {
        s.employee_id: s
        for s in db.query(ActiveWorkSession)
        .filter(ActiveWorkSession.employee_id.in_(team_ids), ActiveWorkSession.status == SessionStatus.ACTIVE)
        .all()
    }
    open_exceptions = (
        db.query(ExceptionRecord)
        .filter(ExceptionRecord.employee_id.in_(team_ids), ExceptionRecord.status == ExceptionStatus.OPEN)
        .all()
    )

    team_view = []
    for employee in team:
        attendance = attendance_by_employee.get(employee.id)
        session = active_by_employee.get(employee.id)
        team_view.append(
            {
                "employee_id": employee.id,
                "employee_name": employee.name,
                "present_today": attendance is not None,
                "working_now": session is not None and not session.is_break,
                "on_break": session is not None and session.is_break,
                "missing_exit": attendance is not None and attendance.first_entry and not attendance.last_exit,
                "overtime_minutes": float(attendance.overtime_minutes) if attendance else 0,
            }
        )

    return {
        "team_size": len(team),
        "present_today": sum(1 for t in team_view if t["present_today"]),
        "working_now": sum(1 for t in team_view if t["working_now"]),
        "on_break": sum(1 for t in team_view if t["on_break"]),
        "open_exceptions": len(open_exceptions),
        "team": team_view,
    }


@router.get("/project/{project_id}", dependencies=[Depends(get_current_user)])
def project_dashboard(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    by_employee = (
        db.query(TimeLog.employee_id, func.sum(TimeLog.duration_minutes))
        .filter(TimeLog.project_id == project_id, TimeLog.is_break.is_(False))
        .group_by(TimeLog.employee_id)
        .all()
    )
    by_activity = (
        db.query(TimeLog.activity_id, func.sum(TimeLog.duration_minutes))
        .filter(TimeLog.project_id == project_id, TimeLog.is_break.is_(False))
        .group_by(TimeLog.activity_id)
        .all()
    )
    actual_minutes = sum(float(m) for _, m in by_employee)

    return {
        "project": {
            "id": project.id,
            "project_code": project.project_code,
            "name": project.name,
            "planned_hours": float(project.planned_hours or 0),
        },
        "actual_hours": round(actual_minutes / 60, 2),
        "remaining_hours": round(float(project.planned_hours or 0) - actual_minutes / 60, 2),
        "hours_by_employee": [
            {"employee_id": emp_id, "hours": round(float(minutes) / 60, 2)} for emp_id, minutes in by_employee
        ],
        "hours_by_activity": [
            {"activity_id": act_id, "hours": round(float(minutes) / 60, 2)} for act_id, minutes in by_activity
        ],
    }


@router.get("/management", dependencies=[Depends(get_current_user)])
def management_dashboard(db: Session = Depends(get_db)):
    today = _today()
    total_employees = db.query(func.count(Employee.id)).scalar()
    present_today = db.query(func.count(Attendance.id)).filter(Attendance.work_date == today).scalar()
    working_now = (
        db.query(func.count(ActiveWorkSession.id))
        .filter(ActiveWorkSession.status == SessionStatus.ACTIVE, ActiveWorkSession.is_break.is_(False))
        .scalar()
    )
    on_break_now = (
        db.query(func.count(ActiveWorkSession.id))
        .filter(ActiveWorkSession.status == SessionStatus.ACTIVE, ActiveWorkSession.is_break.is_(True))
        .scalar()
    )
    total_overtime_minutes = (
        db.query(func.coalesce(func.sum(Attendance.overtime_minutes), 0))
        .filter(Attendance.work_date == today)
        .scalar()
    )
    active_projects = db.query(func.count(Project.id)).filter(Project.status == ProjectStatus.ACTIVE).scalar()
    open_exceptions = db.query(func.count(ExceptionRecord.id)).filter(
        ExceptionRecord.status == ExceptionStatus.OPEN
    ).scalar()

    return {
        "date": today,
        "total_employees": total_employees,
        "present_today": present_today,
        "absent_today": max(0, total_employees - present_today),
        "working_now": working_now,
        "on_break_now": on_break_now,
        "total_overtime_hours_today": round(float(total_overtime_minutes) / 60, 2),
        "active_projects": active_projects,
        "open_exceptions": open_exceptions,
        "utilization_pct": round((working_now / total_employees) * 100, 1) if total_employees else 0,
    }
