from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Role
from app.models.projects import Activity, ActivityCategory, Project, ProjectAssignment, ProjectStatus
from app.schemas import (
    ActivityIn,
    ActivityOut,
    ProjectAssignmentIn,
    ProjectAssignmentOut,
    ProjectIn,
    ProjectOut,
)
from app.security import get_current_user, require_roles

router = APIRouter(tags=["projects"])

admin_or_pm = require_roles(Role.ADMIN.value, Role.PROJECT_MANAGER.value)


@router.post("/projects", response_model=ProjectOut, dependencies=[Depends(admin_or_pm)])
def create_project(payload: ProjectIn, db: Session = Depends(get_db)):
    if db.query(Project).filter(Project.project_code == payload.project_code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project code already exists")
    data = payload.model_dump()
    data["status"] = ProjectStatus(data["status"])
    project = Project(**data)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectOut], dependencies=[Depends(get_current_user)])
def list_projects(status_filter: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Project)
    if status_filter is not None:
        query = query.filter(Project.status == ProjectStatus(status_filter))
    return query.order_by(Project.project_code).all()


@router.get("/projects/{project_id}", response_model=ProjectOut, dependencies=[Depends(get_current_user)])
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.put("/projects/{project_id}", response_model=ProjectOut, dependencies=[Depends(admin_or_pm)])
def update_project(project_id: int, payload: ProjectIn, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    data = payload.model_dump()
    data["status"] = ProjectStatus(data["status"])
    for field, value in data.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.post(
    "/projects/{project_id}/assignments",
    response_model=ProjectAssignmentOut,
    dependencies=[Depends(admin_or_pm)],
)
def assign_employee(project_id: int, payload: ProjectAssignmentIn, db: Session = Depends(get_db)):
    if payload.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_id mismatch")
    assignment = ProjectAssignment(**payload.model_dump())
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get(
    "/projects/{project_id}/assignments",
    response_model=list[ProjectAssignmentOut],
    dependencies=[Depends(get_current_user)],
)
def list_assignments(project_id: int, db: Session = Depends(get_db)):
    return db.query(ProjectAssignment).filter(ProjectAssignment.project_id == project_id).all()


@router.post("/activities", response_model=ActivityOut, dependencies=[Depends(require_roles(Role.ADMIN.value))])
def create_activity(payload: ActivityIn, db: Session = Depends(get_db)):
    if db.query(Activity).filter(Activity.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Activity already exists")
    data = payload.model_dump()
    data["category"] = ActivityCategory(data["category"])
    activity = Activity(**data)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@router.get("/activities", response_model=list[ActivityOut], dependencies=[Depends(get_current_user)])
def list_activities(db: Session = Depends(get_db)):
    return db.query(Activity).order_by(Activity.name).all()
