"""
One-time bootstrap: creates the default admin user, a starter set of activities
(PRD FR-010), and a demo gateway/reader/employee/card/project so the API and
MQTT pipeline can be exercised end-to-end immediately after `docker compose up`.

Run with:  docker compose exec api python -m scripts.seed
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from datetime import date

from app.database import Base, SessionLocal, engine
from app.models.core import Department, Employee, EmploymentStatus, Role, User
from app.models.devices import GatewayStatus, IoTGateway, ReaderType, RFIDCard, RFIDReader
from app.models.projects import Activity, ActivityCategory, Project, ProjectAssignment, ProjectStatus
from app.security import hash_password

DEFAULT_ACTIVITIES = [
    ("Mechanical Design", ActivityCategory.ENGINEERING, True),
    ("Electrical Design", ActivityCategory.ENGINEERING, True),
    ("PLC Programming", ActivityCategory.ENGINEERING, True),
    ("HMI Programming", ActivityCategory.ENGINEERING, True),
    ("Robot Programming", ActivityCategory.ENGINEERING, True),
    ("Documentation", ActivityCategory.ENGINEERING, True),
    ("Mechanical Assembly", ActivityCategory.PRODUCTION, True),
    ("Electrical Wiring", ActivityCategory.PRODUCTION, True),
    ("Panel Assembly", ActivityCategory.PRODUCTION, True),
    ("Pneumatic Assembly", ActivityCategory.PRODUCTION, True),
    ("PLC Testing", ActivityCategory.TESTING, True),
    ("Robot Testing", ActivityCategory.TESTING, True),
    ("Debugging", ActivityCategory.TESTING, True),
    ("FAT", ActivityCategory.TESTING, True),
    ("Safety Testing", ActivityCategory.TESTING, True),
    ("Installation", ActivityCategory.SITE, True),
    ("Commissioning", ActivityCategory.SITE, True),
    ("Service", ActivityCategory.SITE, True),
    ("Maintenance", ActivityCategory.SITE, True),
    ("Meeting", ActivityCategory.OTHER, False),
    ("Training", ActivityCategory.OTHER, False),
    ("Material Handling", ActivityCategory.OTHER, True),
    ("Rework", ActivityCategory.OTHER, True),
    ("Waiting", ActivityCategory.OTHER, False),
    ("Break", ActivityCategory.OTHER, False),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            admin = User(username="admin", hashed_password=hash_password("ChangeMe123!"), role=Role.ADMIN)
            db.add(admin)
            print("Created admin user (username=admin, password=ChangeMe123!) - change this immediately.")

        for name, category, is_productive in DEFAULT_ACTIVITIES:
            if not db.query(Activity).filter(Activity.name == name).first():
                db.add(Activity(name=name, category=category, is_productive=is_productive))
        db.commit()

        dept = db.query(Department).filter(Department.name == "Automation").first()
        if dept is None:
            dept = Department(name="Automation")
            db.add(dept)
            db.commit()
            db.refresh(dept)

        employee = db.query(Employee).filter(Employee.employee_code == "EMP001").first()
        if employee is None:
            employee = Employee(
                employee_code="EMP001",
                name="Demo Employee",
                department_id=dept.id,
                designation="Automation Engineer",
                employment_status=EmploymentStatus.ACTIVE,
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)

        if not db.query(RFIDCard).filter(RFIDCard.uid == "CARD-DEMO-001").first():
            db.add(RFIDCard(uid="CARD-DEMO-001", employee_id=employee.id))

        gateway = db.query(IoTGateway).filter(IoTGateway.gateway_code == "GW-01").first()
        if gateway is None:
            gateway = IoTGateway(
                gateway_code="GW-01",
                name="Main Site Gateway",
                site="Main Plant",
                status=GatewayStatus.ONLINE,
            )
            db.add(gateway)
            db.commit()
            db.refresh(gateway)

        project = db.query(Project).filter(Project.project_code == "PRJ-001").first()
        if project is None:
            project = Project(
                project_code="PRJ-001",
                name="Demo Automation Line",
                customer="Demo Customer",
                status=ProjectStatus.ACTIVE,
                start_date=date.today(),
                planned_hours=500,
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            db.add(ProjectAssignment(project_id=project.id, employee_id=employee.id))

        plc_activity = db.query(Activity).filter(Activity.name == "PLC Programming").first()

        if not db.query(RFIDReader).filter(RFIDReader.reader_code == "READER-GATE-01").first():
            db.add(
                RFIDReader(
                    reader_code="READER-GATE-01",
                    name="Main Gate",
                    reader_type=ReaderType.GATE,
                    gateway_id=gateway.id,
                )
            )
        if not db.query(RFIDReader).filter(RFIDReader.reader_code == "READER-PRJ-001").first():
            db.add(
                RFIDReader(
                    reader_code="READER-PRJ-001",
                    name="Project PRJ-001 Station",
                    reader_type=ReaderType.PROJECT,
                    gateway_id=gateway.id,
                    default_project_id=project.id,
                    default_activity_id=plc_activity.id if plc_activity else None,
                )
            )

        db.commit()
        print("Seed data ready: admin user, activities, department, employee EMP001, card CARD-DEMO-001,")
        print("gateway GW-01, readers READER-GATE-01 / READER-PRJ-001, project PRJ-001.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
