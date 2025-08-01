from pydantic import BaseModel, ConfigDict


class CourseCreate(BaseModel):
    title: str
    description: str
    author: str
    duration_hours: int


class CourseUpdate(BaseModel):
    title: str
    description: str
    duration_hours: int


class CourseOut(BaseModel):
    id: int
    title: str
    description: str
    author: str
    duration_hours: int

    model_config = ConfigDict(from_attributes=True)
