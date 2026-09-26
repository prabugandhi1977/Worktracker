import enum

from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class EmploymentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    HR = "HR"
    SUPERVISOR = "SUPERVISOR"
    PROJECT_MANAGER = "PROJECT_MANAGER"
    FINANCE = "FINANCE"
    MANAGEMENT = "MANAGEMENT"
    EMPLOYEE = "EMPLOYEE"


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)

    employees = relationship("Employee", back_populates="department")


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    employee_code = Column(String(40), unique=True, nullable=False, index=True)
    name = Column(String(160), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    designation = Column(String(120), nullable=False)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    skill_category = Column(String(120), nullable=True)
    employment_status = Column(SAEnum(EmploymentStatus), nullable=False, default=EmploymentStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    department = relationship("Department", back_populates="employees")
    manager = relationship("Employee", remote_side=[id])
    rfid_cards = relationship("RFIDCard", back_populates="employee")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(Role), nullable=False, default=Role.EMPLOYEE)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    employee = relationship("Employee")
