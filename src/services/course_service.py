from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.course import Course
from src.schemas.course import CourseCreate, CourseUpdate


async def get_course(db: AsyncSession, course_id: int) -> Course | None:
    result = await db.execute(select(Course).where(Course.id == course_id))
    return result.scalar_one_or_none()


async def get_all_courses(db: AsyncSession) -> Sequence[Course]:
    result = await db.execute(select(Course))
    return result.scalars().all()


async def create_course(db: AsyncSession, course_data: CourseCreate) -> Course:
    new_course = Course(**course_data.model_dump())
    db.add(new_course)
    await db.commit()
    await db.refresh(new_course)
    return new_course


async def update_course(
        db: AsyncSession,
        course_id: int,
        course_data: CourseUpdate
) -> Course | None:
    course = await get_course(db, course_id)
    if not course:
        return None

    for key, value in course_data.model_dump(exclude_unset=True).items():
        setattr(course, key, value)

    await db.commit()
    await db.refresh(course)
    return course


async def delete_course(db: AsyncSession, course_id: int) -> bool:
    course = await get_course(db, course_id)
    if not course:
        return False
    await db.delete(course)
    await db.commit()
    return True
