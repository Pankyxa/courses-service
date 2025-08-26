from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.deps.auth import get_current_user
from src.deps.db import get_db
from src.models.auth import UserClaims
from src.schemas.course import CourseCreate, CourseOut, CourseUpdate
from src.services import course_service

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/my", response_model=list[CourseOut])
async def get_my_courses(
        current_user: UserClaims = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Получение курсов текущего пользователя
    """
    return await course_service.get_user_courses(db, current_user.sub)  # type: ignore[arg-type]


# ruff: noqa: ARG001
@router.get("/{course_id}", response_model=CourseOut)
async def get_course(
        course_id: int,
        current_user: UserClaims = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Получение курса по id
    """
    course = await course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


# ruff: noqa: ARG001
@router.get("/", response_model=list[CourseOut])
async def get_courses(
        current_user: UserClaims = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Получение всех курсов
    """
    return await course_service.get_all_courses(db)


@router.post("/", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
        course: CourseCreate,
        current_user: UserClaims = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Создание курса
    """
    # ruff: noqa: ERA001
    # if not current_user.has_role("admin"):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Admin role required"
    #     )

    return await course_service.create_course(db, course, user=current_user)


@router.put("/{course_id}", response_model=CourseOut)
async def update_course(
        course_id: int,
        course: CourseUpdate,
        current_user: UserClaims = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Обновление курса по id
    """
    existing_course = await course_service.get_course(db, course_id)
    if not existing_course:
        raise HTTPException(status_code=404, detail="Course not found")

    if existing_course.author_id != current_user.sub and not current_user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own courses"
        )

    return await course_service.update_course(db, course_id, course, user=current_user)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
        course_id: int,
        current_user: UserClaims = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Удаление курса по id
    """
    existing_course = await course_service.get_course(db, course_id)
    if not existing_course:
        raise HTTPException(status_code=404, detail="Course not found")

    if existing_course.author_id != current_user.sub and not current_user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own courses"
        )

    success = await course_service.delete_course(db, course_id, user=current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Course not found")
