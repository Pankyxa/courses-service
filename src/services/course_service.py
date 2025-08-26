from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.auth import UserClaims
from src.models.course import Course
from src.schemas.course import CourseCreate, CourseUpdate


async def get_course(db: AsyncSession, course_id: int) -> Course | None:
    """Получить курс по ID"""
    result = await db.execute(select(Course).where(Course.id == course_id))
    return result.scalar_one_or_none()


async def get_all_courses(db: AsyncSession) -> Sequence[Course]:
    """Получить все курсы"""
    result = await db.execute(select(Course))
    return result.scalars().all()


async def get_user_courses(db: AsyncSession, user_id: str) -> Sequence[Course]:
    """Получить курсы, созданные пользователем"""
    result = await db.execute(select(Course).where(Course.author_id == user_id))
    return result.scalars().all()


async def create_course(
        db: AsyncSession,
        course_data: CourseCreate,
        user: UserClaims
) -> Course:
    """Создать курс от имени пользователя"""
    course_dict = course_data.model_dump()
    # Преобразуем email в строку или используем пустую строку, если email отсутствует
    author_email = str(user.email) if user.email is not None else "null@pochta.net"

    new_course = Course(
        **course_dict,
        author_id=user.sub,
        author_email=author_email
    )
    db.add(new_course)
    await db.commit()
    await db.refresh(new_course)
    return new_course


async def update_course(
        db: AsyncSession,
        course_id: int,
        course_data: CourseUpdate,
        user: UserClaims
) -> Course | None:
    """Обновить курс от имени пользователя"""
    course = await get_course(db, course_id)
    if not course:
        return None

    if course.author_id != user.sub and not user.has_role("admin"):
        return None

    for key, value in course_data.model_dump(exclude_unset=True).items():
        setattr(course, key, value)

    await db.commit()
    await db.refresh(course)
    return course


async def delete_course(
        db: AsyncSession,
        course_id: int,
        user: UserClaims
) -> bool:
    """Удалить курс от имени пользователя"""
    course = await get_course(db, course_id)
    if not course:
        return False

    if course.author_id != user.sub and not user.has_role("admin"):
        return False

    await db.delete(course)
    await db.commit()
    return True
