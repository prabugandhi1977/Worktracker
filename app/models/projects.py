import enum

from sqlalchemy import Boolean, Column, Date
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database import Base


class ProjectStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    project_code = Column(String(60), unique=True, nullable=False, index=True)
    name = Column(String(160), nullable=False)
    customer = Column(String(160), nullable=True)
    project_manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    start_date = Column(Date, nullable=True)
    target_end_date = Column(Date, nullable=True)
    status = Column(SAEnum(ProjectStatus), nullable=False, default=ProjectStatus.PLANNED)
    planned_hours = Column(Numeric(10, 2), default=0)
    budgeted_manpower_cost = Column(Numeric(14, 2), default=0)

    assignments = relationship("ProjectAssignment", back_populates="project")


class ProjectAssignment(Base):
    __tablename__ = "project_assignments"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    hourly_cost_rate = Column(Numeric(10, 2), default=0)

    project = relationship("Project", back_populates="assignments")
    employee = relationship("Employee")


class ActivityCategory(str, enum.Enum):
    ENGINEERING = "ENGINEERING"
    PRODUCTION = "PRODUCTION"
    TESTING = "TESTING"
    SITE = "SITE"
    OTHER = "OTHER"


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    category = Column(SAEnum(ActivityCategory), nullable=False, default=ActivityCategory.OTHER)
    is_productive = Column(Boolean, default=True)
