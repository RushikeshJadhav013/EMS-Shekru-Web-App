from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.database import engine, SessionLocal, Base
from app.realtime.socketio_app import socket_app

# Import models so SQLAlchemy knows about all tables before create_all
from app.db.models import (  # noqa: F401
    user,
    attendance,
    leave,
    task,
    department,
    shift,
    notification,
    office_timing,
    online_status,
    task_comment,
    hiring,
    interview,
    leave_config,
    salary,  # Salary models for salary slip and increment letter
    interview_feedback,
    project,
    project_member,
    meeting,
    company,
    company_branch,
    branch_admin_assignment,
    company_admin_assignment,
    chat,
)
from app.routes import (
    user_routes,
    attendance_routes,
    leave_routes,
    leave_calendar_routes,
    task_routes,
    task_comment_routes,
    auth_routes,
    dashboard_routes,
    hiring_routes,
    interview_routes,
    shift_routes,
    department_routes,
    report_routes,
    super_admin_routes,
    subscription_routes,
    company_routes,
    company_branch_routes,
    branch_admin_assignment_routes,
    chat_routes,
    wfh_routes,
    salary_routes,  # Salary slip and increment letter routes
    interview_feedback_routes,
    project_routes,
    meeting_routes,
    project_meeting_routes,
)
from app.db.models.super_admin import SuperAdmin
import os


# Create all database tables
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created/verified successfully")
except Exception as e:
    print(f"⚠️ Warning: Could not create database tables: {e}")

# Lightweight schema safeguard for new columns (MySQL)
try:
    with engine.begin() as conn:
        # Check if 'leave_type' exists on 'leaves' table; if not, add it
        result = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'leaves'
                  AND COLUMN_NAME = 'leave_type'
                """
            )
        )
        row = result.first()
        has_leave_type = bool(row[0] if row else 0)
        if not has_leave_type:
            conn.execute(
                text("ALTER TABLE leaves ADD COLUMN leave_type VARCHAR(50) NOT NULL DEFAULT 'annual'")
            )
        
        # Check if 'work_location' exists on 'attendances' table; if not, add it
        result = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'attendances'
                  AND COLUMN_NAME = 'work_location'
                """
            )
        )
        row = result.first()
        has_work_location = bool(row[0] if row else 0)
        if not has_work_location:
            conn.execute(
                text("ALTER TABLE attendances ADD COLUMN work_location VARCHAR(50) DEFAULT 'office'")
            )
            # Update existing records to have 'office' as default
            conn.execute(
                text("UPDATE attendances SET work_location = 'office' WHERE work_location IS NULL")
            )

        # Check if 'project_id' exists on 'meetings' table; if not, add it
        result = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'meetings'
                  AND COLUMN_NAME = 'project_id'
                """
            )
        )
        row = result.first()
        has_project_id = bool(row[0] if row else 0)
        if not has_project_id:
            conn.execute(
                text("ALTER TABLE meetings ADD COLUMN project_id INT NULL")
            )
except Exception as _e:
    # Fail-soft: app will still boot; detailed error returned via middleware if used
    pass

# Initialize FastAPI
app = FastAPI(
    title="Testing Employee Management System",
    version="1.0"
)

app.mount("/socket.io", socket_app)

# Note: If you get 413 Payload Too Large errors, configure your web server:
# - nginx: client_max_body_size 50M;
# - Apache: LimitRequestBody 52428800
# - Gunicorn: --limit-request-line 8190 --limit-request-field_size 8190

@app.on_event("startup")
def create_initial_super_admin():
    db: Session = SessionLocal()
    try:
        # Check if any SuperAdmin exists
        existing = db.query(SuperAdmin).first()
        if existing:
            return

        # Create default Super Admin
        default_admin = SuperAdmin(
            name="Default Super Admin",
            email="superadmin@example.com",
            contact_no="9999999999",
            # if you add a password field later, set hashed_password here
        )
        db.add(default_admin)
        db.commit()
        db.refresh(default_admin)
        print("✅ Initial Super Admin created:", default_admin.email)
    except Exception as e:
        print("⚠️ Could not create initial Super Admin:", e)
    finally:
        db.close()

# ✅ Serve static files (profile photos, selfies, etc.)
os.makedirs("static", exist_ok=True)
os.makedirs("static/profile_photos", exist_ok=True)
os.makedirs("static/selfies", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
# --------------------------
# CORS (for React dev server)
# --------------------------
# --------------------------
# ✅ CORS Configuration
# --------------------------

# Allowed origins for CORS
origins = [
    # "https://staffly.space",    # Direct backend access
    # "https://stafflyhrms.netlify.app",  # Production deployment
    # "http://localhost:8080",
    "https://testing.staffly.space",           # Allow all origins (for development)
    "https://stafflytesting.netlify.app"       # Testing deployment
]

# Configure CORS middleware with detailed settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600
)


# Routers
app.include_router(user_routes.router)
app.include_router(attendance_routes.router)
app.include_router(leave_routes.router)
app.include_router(leave_calendar_routes.router)
app.include_router(task_routes.router)
app.include_router(task_comment_routes.router)
app.include_router(auth_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(hiring_routes.router)
app.include_router(interview_routes.router)
app.include_router(shift_routes.router)
app.include_router(department_routes.router)
app.include_router(report_routes.router)
app.include_router(super_admin_routes.router)
app.include_router(subscription_routes.router)
app.include_router(company_routes.router)
app.include_router(company_branch_routes.router)
app.include_router(branch_admin_assignment_routes.router)
app.include_router(chat_routes.router)
app.include_router(wfh_routes.router)
app.include_router(salary_routes.router)  # Salary slip and increment letter routes
app.include_router(interview_feedback_routes.router)
app.include_router(project_routes.router)
app.include_router(meeting_routes.router)
app.include_router(project_meeting_routes.router)

# Global exception handlers to ensure CORS headers are always included
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
    # Add CORS headers to error responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Make validation errors JSON-safe (ctx.error can be an Exception)
    safe_errors = []
    for err in exc.errors():
        ctx = err.get("ctx")
        if ctx and isinstance(ctx.get("error"), Exception):
            ctx = {**ctx, "error": str(ctx["error"])}
            err = {**err, "ctx": ctx}
        safe_errors.append(err)

    content = jsonable_encoder({"detail": safe_errors, "body": exc.body})
    response = JSONResponse(status_code=422, content=content)
    # Add CORS headers to validation error responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )
    # Add CORS headers to general error responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# Global exception handlers to ensure CORS headers are always included
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
    # Add CORS headers to error responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )
    # Add CORS headers to general error responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.get("/")
async def home():
    return {"message": "Testing Employee Management System API is running"}

@app.get("/test-cors", tags=["Test"], include_in_schema=False)
async def test_cors():
    """
    Test endpoint to verify CORS is working correctly
    """
    return {
        "status": "success",
        "message": "CORS is working! If you can see this, your frontend can communicate with the backend.",
        "timestamp": "2024-01-01T00:00:00Z",
        "endpoints_tested": [
            "/tasks/notifications",
            "/shift/notifications"
        ]
    }

@app.options("/tasks/notifications", tags=["Test"], include_in_schema=False)
async def test_task_notifications_cors():
    """Preflight handler for task notifications"""
    return {"message": "CORS preflight successful for task notifications"}

@app.options("/shift/notifications", tags=["Test"], include_in_schema=False)
async def test_shift_notifications_cors():
    """Preflight handler for shift notifications"""
    return {"message": "CORS preflight successful for shift notifications"}
