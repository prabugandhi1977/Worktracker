import enum

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class GatewayStatus(str, enum.Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class CardStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    LOST = "LOST"


class ReaderType(str, enum.Enum):
    GATE = "GATE"
    PROJECT = "PROJECT"
    WORKSTATION = "WORKSTATION"
    BREAK = "BREAK"


class IoTGateway(Base):
    __tablename__ = "iot_gateways"

    id = Column(Integer, primary_key=True)
    gateway_code = Column(String(60), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    site = Column(String(120), nullable=False)
    ip_address = Column(String(60), nullable=True)
    software_version = Column(String(40), nullable=True)
    status = Column(SAEnum(GatewayStatus), nullable=False, default=GatewayStatus.OFFLINE)
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)

    readers = relationship("RFIDReader", back_populates="gateway")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    site = Column(String(120), nullable=True)


class RFIDReader(Base):
    __tablename__ = "rfid_readers"

    id = Column(Integer, primary_key=True)
    reader_code = Column(String(60), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    reader_type = Column(SAEnum(ReaderType), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    gateway_id = Column(Integer, ForeignKey("iot_gateways.id"), nullable=False)
    default_project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    default_activity_id = Column(Integer, ForeignKey("activities.id"), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)

    gateway = relationship("IoTGateway", back_populates="readers")
    location = relationship("Location")


class RFIDCard(Base):
    __tablename__ = "rfid_cards"

    id = Column(Integer, primary_key=True)
    uid = Column(String(80), unique=True, nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    status = Column(SAEnum(CardStatus), nullable=False, default=CardStatus.ACTIVE)
    issued_at = Column(DateTime(timezone=True), server_default=func.now())
    deactivated_at = Column(DateTime(timezone=True), nullable=True)

    employee = relationship("Employee", back_populates="rfid_cards")
