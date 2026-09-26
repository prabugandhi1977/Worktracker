import enum

from sqlalchemy import Boolean, Column, Date, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.sql import func

from app.database import Base


class EventType(str, enum.Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    PROJECT_START = "PROJECT_START"
    BREAK_START = "BREAK_START"
    BREAK_END = "BREAK_END"
    UNKNOWN = "UNKNOWN"


class RFIDEvent(Base):
    """Immutable raw event as received from a gateway. Never updated after insert."""

    __tablename__ = "rfid_events"

    id = Column(Integer, primary_key=True)
    event_uid = Column(String(80), unique=True, nullable=False, index=True)
    card_uid = Column(String(80), nullable=False, index=True)
    reader_id = Column(Integer, ForeignKey("rfid_readers.id"), nullable=True)
    gateway_id = Column(Integer, ForeignKey("iot_gateways.id"), nullable=True)
    event_type = Column(SAEnum(EventType), nullable=False, default=EventType.UNKNOWN)
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    processed = Column(Boolean, default=False)
    is_duplicate = Column(Boolean, default=False)
    raw_payload = Column(Text, nullable=True)


class SessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class ActiveWorkSession(Base):
    """At most one ACTIVE row per employee, enforced by the event-processing service."""

    __tablename__ = "active_work_sessions"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=True)
    reader_id = Column(Integer, ForeignKey("rfid_readers.id"), nullable=True)
    is_break = Column(Boolean, default=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(SAEnum(SessionStatus), nullable=False, default=SessionStatus.ACTIVE, index=True)


class TimeLog(Base):
    __tablename__ = "time_logs"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Numeric(10, 2), nullable=False)
    source = Column(String(20), default="RFID")
    is_break = Column(Boolean, default=False)
    status = Column(String(20), default="CONFIRMED")


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)
    first_entry = Column(DateTime(timezone=True), nullable=True)
    last_exit = Column(DateTime(timezone=True), nullable=True)
    gross_minutes = Column(Numeric(10, 2), default=0)
    break_minutes = Column(Numeric(10, 2), default=0)
    net_minutes = Column(Numeric(10, 2), default=0)
    overtime_minutes = Column(Numeric(10, 2), default=0)


class ExceptionSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ExceptionStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


class ExceptionRecord(Base):
    __tablename__ = "exceptions"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    work_date = Column(Date, nullable=True)
    exception_type = Column(String(60), nullable=False)
    description = Column(String(255), nullable=True)
    severity = Column(SAEnum(ExceptionSeverity), default=ExceptionSeverity.MEDIUM)
    status = Column(SAEnum(ExceptionStatus), default=ExceptionStatus.OPEN, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution = Column(String(255), nullable=True)


class CorrectionStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class CorrectionRequest(Base):
    __tablename__ = "correction_requests"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    time_log_id = Column(Integer, ForeignKey("time_logs.id"), nullable=True)
    requested_start = Column(DateTime(timezone=True), nullable=True)
    requested_end = Column(DateTime(timezone=True), nullable=True)
    reason = Column(String(255), nullable=False)
    status = Column(SAEnum(CorrectionStatus), default=CorrectionStatus.PENDING, index=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
