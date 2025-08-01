from sqlalchemy.orm import Session

from src.models.course import Course
from src.schemas.course import CourseCreate, CourseUpdate


def get_course(db: Session, course_id: int) -> Course | None:
    return db.query(Course).filter(Course.id == course_id).one_or_none()


def get_all_courses(db: Session) -> list[type[Course]]:
    return db.query(Course).all()


def create_course(db: Session, course_data: CourseCreate) -> Course | None:
    new_course = Course(**course_data.model_dump())
    db.add(new_course)
    db.commit()
    return new_course


def update_course(db: Session, course_id: int, course_data: CourseUpdate) -> Course | None:
    course = get_course(db, course_id)
    if not course:
        return None

    for key, value in course_data.model_dump(exclude_unset=True).items():
        setattr(course, key, value)

    db.commit()
    db.refresh(course)
    return course


def delete_course(db: Session, course_id: int) -> bool:
    course = get_course(db, course_id)
    if course is None:
        return False
    db.delete(course)
    db.commit()
    return True
