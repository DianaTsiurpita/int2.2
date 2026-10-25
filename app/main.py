"""Student API.

Anyone may read the students and their grades. Changing a grade
requires the Dean's Seal, a secret token that arrives as a FILE,
never as an environment variable.
"""

import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# The app does NOT know where the secret lives, the deployment tells it.
# The default follows the Docker convention /run/secrets/<name>, so the same
# code works with `docker run -v`, compose `secrets:` and swarm `--secret`.
GRADE_TOKEN_FILE = Path(os.getenv("GRADE_TOKEN_FILE", "/run/secrets/grade_token"))


class Student(BaseModel):
    id: int
    name: str
    course: str
    grade: int | None = None   # None = not graded yet


class StudentPatch(BaseModel):
    """Only the fields you want to change."""
    name: str | None = None
    course: str | None = None
    grade: int | None = None


students: dict[int, Student] = {
    1: Student(id=1, name="Alice", course="Docker 101", grade=60),
}


def read_grade_token() -> str:
    """The universal secret interface: a file at a fixed path."""
    try:
        return GRADE_TOKEN_FILE.read_text().strip()
    except OSError as exc:
        raise RuntimeError(
            f"Dean's Seal is not mounted at {GRADE_TOKEN_FILE} — refusing to start."
        ) from exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast: a container without the seal crashes at birth
    # instead of serving an unprotected endpoint.
    read_grade_token()
    yield


app = FastAPI(title="Student API", version="0.2.0", lifespan=lifespan)


def require_dean(x_grade_token: str) -> None:
    # Re-read the file on EVERY request: the seal can be rotated
    # without restarting the container.
    expected = read_grade_token()
    # Constant-time comparison — even the check must not leak information.
    if not hmac.compare_digest(x_grade_token.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="The Dean's Seal does not match.")


@app.get("/")
def read_root() -> dict:
    return {"message": "Hello from FastAPI running inside Docker!"}


@app.get("/students")
def list_students() -> list[Student]:
    return list(students.values())


@app.get("/students/{student_id}")
def get_student(student_id: int) -> Student:
    if student_id not in students:
        raise HTTPException(status_code=404, detail="Student not found")
    return students[student_id]


@app.post("/students", status_code=201)
def create_student(student: Student) -> Student:
    students[student.id] = student
    return student


@app.patch("/students/{student_id}")
def update_student(
    student_id: int,
    patch: StudentPatch,
    x_grade_token: str = Header(),   # FastAPI maps this to header "x-grade-token"
) -> Student:
    """Change a grade — the Dean's privilege only."""
    if student_id not in students:
        raise HTTPException(status_code=404, detail="Student not found")
    require_dean(x_grade_token)

    changes = patch.model_dump(exclude_unset=True)
    students[student_id] = students[student_id].model_copy(update=changes)
    return students[student_id]