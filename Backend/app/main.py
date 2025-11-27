from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
from app.db import models
from app.db.database import engine
from app.routes import (
    user_routes,
    attendance_routes,
    leave_routes,
    task_routes,
    task_comment_routes,
    auth_routes,
    dashboard_routes,
    hiring_routes,
    shift_routes,
    department_routes,
    report_routes,
)
import os


# Create all database tables
try:
    models.Base.metadata.create_all(bind=engine)
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
except Exception as _e:
    # Fail-soft: app will still boot; detailed error returned via middleware if used
    pass

# Initialize FastAPI
app = FastAPI(
    title="Employee Management System",
    version="1.0"
)

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
    "http://localhost:3000",    # React dev server
    "http://127.0.0.1:3000",   # React dev server alternative
    "http://localhost:5173",    # Vite dev server
    # "http://127.0.0.1:5173",   # Vite dev server alternative
    # "http://localhost:8000",    # Direct backend access
    "https://staffly.space",   # Direct backend access alternative
    # "http://localhost:8080",    # Common frontend port
    # "http://127.0.0.1:8080",   # Common frontend port alternative
    # "http://localhost:4173",    # Vite preview server
    # "http://127.0.0.1:4173",   # Vite preview server alternative
    "https://stafflyhrms.netlify.app",  # Production deployment
    "https://staffly.space"                         # Allow all origins (for development)
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
app.include_router(task_routes.router)
app.include_router(task_comment_routes.router)
app.include_router(auth_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(hiring_routes.router)
app.include_router(shift_routes.router)
app.include_router(department_routes.router)
app.include_router(report_routes.router)

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
    response = JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )
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

@app.get("/")
async def home():
    return {"message": "Employee Management System API is running"}

@app.get("/test-cors", tags=["Test"])
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

@app.options("/tasks/notifications", tags=["Test"])
async def test_task_notifications_cors():
    """Preflight handler for task notifications"""
    return {"message": "CORS preflight successful for task notifications"}

@app.options("/shift/notifications", tags=["Test"])
async def test_shift_notifications_cors():
    """Preflight handler for shift notifications"""
    return {"message": "CORS preflight successful for shift notifications"}
