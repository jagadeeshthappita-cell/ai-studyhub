
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from pwdlib import PasswordHash


app = FastAPI()
password_hash = PasswordHash.recommended()

# JWT settings
SECRET_KEY = os.getenv(
    "STUDYHUB_SECRET_KEY",
    "dev-only-change-this-secret-before-deployment"
)
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Database connection
def get_connection():
    connection = sqlite3.connect("studyhub.db")
    connection.row_factory = sqlite3.Row
    return connection


# Create database tables and update old tasks table
def init_db():
    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            user_id INTEGER REFERENCES users(id)
        )
    """)

    columns = connection.execute(
        "PRAGMA table_info(tasks)"
    ).fetchall()
    column_names = [column["name"] for column in columns]

    if "user_id" not in column_names:
        connection.execute(
            "ALTER TABLE tasks ADD COLUMN user_id INTEGER REFERENCES users(id)"
        )

    connection.commit()
    connection.close()


init_db()


# Request formats
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# Verify token and find current user
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        subject = payload.get("sub")
        if subject is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
            )

        user_id = int(subject)

    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    connection = get_connection()
    user = connection.execute(
        "SELECT id FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    connection.close()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    return user_id


# Home
@app.get("/")
def home():
    return {"message": "Welcome to AI StudyHub backend!"}


# Get tasks belonging to the logged-in user
@app.get("/api/tasks")
def get_tasks(user_id: int = Depends(get_current_user)):
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT id, text, completed
        FROM tasks
        WHERE user_id = ?
        ORDER BY id
        """,
        (user_id,),
    ).fetchall()

    tasks = [dict(row) for row in rows]
    connection.close()

    return {"tasks": tasks}


# Add a task for the logged-in user
@app.post("/api/tasks")
def add_task(
    task: str,
    user_id: int = Depends(get_current_user),
):
    task = task.strip()

    if not task:
        raise HTTPException(
            status_code=400,
            detail="Task cannot be empty",
        )

    connection = get_connection()
    connection.execute(
        "INSERT INTO tasks (text, user_id) VALUES (?, ?)",
        (task, user_id),
    )
    connection.commit()
    connection.close()

    return {"message": "Task saved successfully!"}


# Delete only the logged-in user's task
@app.delete("/api/tasks/{task_id}")
def delete_task(
    task_id: int,
    user_id: int = Depends(get_current_user),
):
    connection = get_connection()

    cursor = connection.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, user_id),
    )

    connection.commit()
    deleted = cursor.rowcount
    connection.close()

    if deleted == 0:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return {"message": "Task deleted successfully!"}


# Mark a task done or undo it
@app.put("/api/tasks/{task_id}")
def update_task(
    task_id: int,
    user_id: int = Depends(get_current_user),
):
    connection = get_connection()

    cursor = connection.execute(
        """
        UPDATE tasks
        SET completed = CASE
            WHEN completed = 0 THEN 1
            ELSE 0
        END
        WHERE id = ? AND user_id = ?
        """,
        (task_id, user_id),
    )

    connection.commit()
    updated = cursor.rowcount
    connection.close()

    if updated == 0:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return {"message": "Task status updated!"}


# Signup
@app.post("/api/signup")
def signup(user: SignupRequest):
    name = user.name.strip()
    email = user.email.strip().lower()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Name cannot be empty",
        )

    if len(user.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters",
        )

    hashed_password = password_hash.hash(user.password)
    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO users (name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (name, email, hashed_password),
        )
        connection.commit()

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="This email is already registered",
        )

    finally:
        connection.close()

    return {"message": "Account created successfully!"}


# Login and generate JWT token
@app.post("/api/login")
def login(user: LoginRequest):
    email = user.email.strip().lower()

    connection = get_connection()
    row = connection.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    connection.close()

    if row is None or not password_hash.verify(
        user.password,
        row["password_hash"],
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    payload = {
        "sub": str(row["id"]),
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return {
        "message": "Login successful!",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
        },
    }
