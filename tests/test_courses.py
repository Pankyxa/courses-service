from fastapi import status
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_create_course():
    response = client.post("/courses", json={
        "title": "Python 101",
        "description": "Basic course",
        "author": "Anton",
        "duration_hours": 10
    })
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["title"] == "Python 101"
    assert "id" in data


def test_get_all_courses():
    response = client.get("/courses")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


def test_get_single_course():
    response = client.post("/courses", json={
        "title": "Flask 101",
        "description": "Flask base",
        "author": "Anton",
        "duration_hours": 5
    })
    course_id = response.json()["id"]

    response = client.get(f"/courses/{course_id}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["title"] == "Flask 101"


def test_update_course():
    response = client.post("/courses", json={
        "title": "To Update",
        "description": "",
        "author": "Anton",
        "duration_hours": 1
    })
    course_id = response.json()["id"]

    response = client.put(f"/courses/{course_id}", json={
        "title": "Updated title",
        "description": "Updated desc",
        "author": "Updated author",
        "duration_hours": 99
    })

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["title"] == "Updated title"


def test_delete_course():
    response = client.post("/courses", json={
        "title": "To Delete",
        "description": "",
        "author": "Anton",
        "duration_hours": 1
    })
    course_id = response.json()["id"]

    response = client.delete(f"/courses/{course_id}")
    assert response.status_code in {status.HTTP_200_OK, status.HTTP_204_NO_CONTENT}

    response = client.get(f"/courses/{course_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
