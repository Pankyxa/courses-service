from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.deps.db import get_db
from src.schemas.course import CourseCreate, CourseOut, CourseUpdate
from src.services import course_service

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/{course_id}", response_model=CourseOut)
async def get_course(course_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получение курса по id
    """

    course = await course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.get("/", response_model=list[CourseOut])
async def get_courses(db: AsyncSession = Depends(get_db)):
    """
    Получение всех курсов
    """

    return await course_service.get_all_courses(db)


@router.post("/", response_model=CourseOut)
async def create_course(course: CourseCreate, db: AsyncSession = Depends(get_db)):
    """
    Создание курса
    """

    return await course_service.create_course(db, course)


@router.put("/{course_id}", response_model=CourseOut)
async def update_course(course_id: int, course: CourseUpdate, db: AsyncSession = Depends(get_db)):
    """
    Обновление курса по id
    """

    return await course_service.update_course(db, course_id, course)


@router.delete("/{course_id}")
async def delete_course(course_id: int, db: AsyncSession = Depends(get_db)):
    """
    Удаление курса по id
    """
    success = await course_service.delete_course(db, course_id)
    if not success:
        raise HTTPException(status_code=404, detail="Course not found")
