from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.deps.db import get_db
from src.schemas.course import CourseCreate, CourseOut, CourseUpdate
from src.services import course_service

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: int, db: Session = Depends(get_db)):
    """
    Получение курса по id
    """

    course = course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.get("/", response_model=list[CourseOut])
def get_courses(db: Session = Depends(get_db)):
    """
    Получение всех курсов
    """

    return course_service.get_all_courses(db)


@router.post("/", response_model=CourseOut)
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    """
    Создание курса
    """

    return course_service.create_course(db, course)


@router.put("/{course_id}", response_model=CourseOut)
def update_course(course_id: int, course: CourseUpdate, db: Session = Depends(get_db)):
    """Обновление курса по id"""
    return course_service.update_course(db, course_id, course)


@router.delete("/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db)):
    """
    Удаление курса по id
    """
    success = course_service.delete_course(db, course_id)
    if not success:
        raise HTTPException(status_code=404, detail="Course not found")
