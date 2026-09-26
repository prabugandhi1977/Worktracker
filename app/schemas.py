from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Auth ----


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    employee_id: Optional[int] = None


class UserOut(ORMModel):
    id: int
    username: str
    role: str
    employee_id: Optional[int] = None
    is_active: bool


# ---- Departments / Employees ----


class DepartmentIn(BaseModel):
    name: str


class DepartmentOut(ORMModel):
    id: int
    name: str


class EmployeeIn(BaseModel):
    employee_code: str
    name: str
    department_id: int
    designation: str
    manager_id: Optional[int] = None
    skill_category: Optional[str] = None
    employment_status: str = "ACTIVE"


class EmployeeOut(ORMModel):
    id: int
    employee_code: str
    name: str
    department_id: int
    designation: str
    manager_id: Optional[int] = None
    skill_category: Optional[str] = None
    employment_status: str


# ---- Devices ----


class LocationIn(BaseModel):
    name: str
    site: Optional[str] = None


class LocationOut(ORMModel):
    id: int
    name: str
    site: Optional[str] = None


class GatewayIn(BaseModel):
    gateway_code: str
    name: str
    site: str
    ip_address: Optional[str] = None
    software_version: Optional[str] = None


class GatewayOut(ORMModel):
    id: int
    gateway_code: str
    name: str
    site: str
    status: str
    last_heartbeat: Optional[datetime] = None


class ReaderIn(BaseModel):
    reader_code: str
    name: str
    reader_type: str
    gateway_id: int
    location_id: Optional[int] = None
    default_project_id: Optional[int] = None
    default_activity_id: Optional[int] = None


class ReaderOut(ORMModel):
    id: int
    reader_code: str
    name: str
    reader_type: str
    gateway_id: int
    location_id: Optional[int] = None
    default_project_id: Optional[int] = None
    default_activity_id: Optional[int] = None
    last_seen: Optional[datetime] = None


class RFIDCardIn(BaseModel):
    uid: str
    employee_id: Optional[int] = None


class RFIDCardOut(ORMModel):
    id: int
    uid: str
    employee_id: Optional[int] = None
    status: str
    issued_at: datetime


# ---- Projects / Activities ----


class ProjectIn(BaseModel):
    project_code: str
    name: str
    customer: Optional[str] = None
    project_manager_id: Optional[int] = None
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    status: str = "PLANNED"
    planned_hours: float = 0
    budgeted_manpower_cost: float = 0


class ProjectOut(ORMModel):
    id: int
    project_code: str
    name: str
    customer: Optional[str] = None
    project_manager_id: Optional[int] = None
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    status: str
    planned_hours: float
    budgeted_manpower_cost: float


class ProjectAssignmentIn(BaseModel):
    project_id: int
    employee_id: int
    hourly_cost_rate: float = 0


class ProjectAssignmentOut(ORMModel):
    id: int
    project_id: int
    employee_id: int
    hourly_cost_rate: float


class ActivityIn(BaseModel):
    name: str
    category: str = "OTHER"
    is_productive: bool = True


class ActivityOut(ORMModel):
    id: int
    name: str
    category: str
    is_productive: bool


# ---- RFID events / tracking ----


class RFIDEventIn(BaseModel):
    """HTTP fallback ingestion payload, mirrors the MQTT message schema."""

    event_id: str
    rfid_uid: str
    reader_id: str
    gateway_id: str
    timestamp: datetime


class RFIDEventOut(ORMModel):
    id: int
    event_uid: str
    card_uid: str
    event_type: str
    event_timestamp: datetime
    employee_id: Optional[int] = None
    processed: bool
    is_duplicate: bool


class ActiveSessionOut(ORMModel):
    id: int
    employee_id: int
    project_id: Optional[int] = None
    activity_id: Optional[int] = None
    is_break: bool
    started_at: datetime
    status: str


class TimeLogOut(ORMModel):
    id: int
    employee_id: int
    project_id: Optional[int] = None
    activity_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    duration_minutes: float
    is_break: bool
    status: str


class AttendanceOut(ORMModel):
    id: int
    employee_id: int
    work_date: date
    first_entry: Optional[datetime] = None
    last_exit: Optional[datetime] = None
    gross_minutes: float
    break_minutes: float
    net_minutes: float
    overtime_minutes: float


class ExceptionOut(ORMModel):
    id: int
    employee_id: Optional[int] = None
    work_date: Optional[date] = None
    exception_type: str
    description: Optional[str] = None
    severity: str
    status: str
    created_at: datetime
    resolution: Optional[str] = None


class ExceptionResolve(BaseModel):
    resolution: str
    status: str = "RESOLVED"


class CorrectionRequestIn(BaseModel):
    employee_id: int
    time_log_id: Optional[int] = None
    requested_start: Optional[datetime] = None
    requested_end: Optional[datetime] = None
    reason: str


class CorrectionRequestOut(ORMModel):
    id: int
    employee_id: int
    time_log_id: Optional[int] = None
    requested_start: Optional[datetime] = None
    requested_end: Optional[datetime] = None
    reason: str
    status: str
    created_at: datetime
    reviewed_at: Optional[datetime] = None


class CorrectionDecision(BaseModel):
    approve: bool
