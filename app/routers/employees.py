from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Department, Employee, EmploymentStatus, Role
from app.schemas import DepartmentIn, DepartmentOut, EmployeeIn, EmployeeOut
from app.security import get_current_user, require_roles

router = APIRouter(tags=["employees"])

admin_or_hr = require_roles(Role.ADMIN.value, Role.HR.value)


@router.post("/departments", response_model=DepartmentOut, dependencies=[Depends(admin_or_hr)])
def create_department(payload: DepartmentIn, db: Session = Depends(get_db)):
    department = Department(name=payload.name)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


@router.get("/departments", response_model=list[DepartmentOut], dependencies=[Depends(get_current_user)])
def list_departments(db: Session = Depends(get_db)):
    return db.query(Department).order_by(Department.name).all()


@router.post("/employees", response_model=EmployeeOut, dependencies=[Depends(admin_or_hr)])
def create_employee(payload: EmployeeIn, db: Session = Depends(get_db)):
    if db.query(Employee).filter(Employee.employee_code == payload.employee_code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee code already exists")
    data = payload.model_dump()
    data["employment_status"] = EmploymentStatus(data["employment_status"])
    employee = Employee(**data)
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@router.get("/employees", response_model=list[EmployeeOut], dependencies=[Depends(get_current_user)])
def list_employees(
    department_id: int | None = None,
    manager_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Employee)
    if department_id is not None:
        query = query.filter(Employee.department_id == department_id)
    if manager_id is not None:
        query = query.filter(Employee.manager_id == manager_id)
    return query.order_by(Employee.name).all()


@router.get("/employees/{employee_id}", response_model=EmployeeOut, dependencies=[Depends(get_current_user)])
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


@router.put("/employees/{employee_id}", response_model=EmployeeOut, dependencies=[Depends(admin_or_hr)])
def update_employee(employee_id: int, payload: EmployeeIn, db: Session = Depends(get_db)):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    data = payload.model_dump()
    data["employment_status"] = EmploymentStatus(data["employment_status"])
    for field, value in data.items():
        setattr(employee, field, value)
    db.commit()
    db.refresh(employee)
    return employee
