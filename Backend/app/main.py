from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.db import models
from app.db.database import engine
from app.routes import user_routes, attendance_routes, leave_routes, task_routes, auth_routes, dashboard_routes
import os


models.Base.metadata.create_all(bind=engine)

# Custom middleware to add CORS headers to all responses
class CORSMiddlewareWithErrorHandling(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Handle preflight requests
        if request.method == 'OPTIONS':
            response = JSONResponse(
                content={"message": "Preflight request successful"},
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                    "Access-Control-Allow-Headers": "*",
                }
            )
            return response

        try:
            response = await call_next(request)
            # Add CORS headers to all successful responses
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            response.headers["Access-Control-Allow-Headers"] = "*"
            return response
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JSONResponse(
                status_code=500,
                content={"detail": str(e)},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                    "Access-Control-Allow-Headers": "*",
                }
            )

# Initialize FastAPI with middleware
app = FastAPI(
    title="Employee Management System",
    version="1.0",
    middleware=[
        Middleware(CORSMiddlewareWithErrorHandling)
    ]
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
    "http://127.0.0.1:5173",   # Vite dev server alternative
    "http://localhost:8000",    # Direct backend access
    "http://127.0.0.1:8000",   # Direct backend access alternative
    "http://localhost:8080",    # Common frontend port
    "http://127.0.0.1:8080",   # Common frontend port alternative
    "*"                         # Allow all origins (temporary for development)
]

# Configure CORS middleware with detailed settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all headers
    max_age=600  # Cache preflight requests for 10 minutes
)


# Routers
app.include_router(user_routes.router)
app.include_router(attendance_routes.router)
app.include_router(leave_routes.router)
app.include_router(task_routes.router)
app.include_router(auth_routes.router)
app.include_router(dashboard_routes.router)

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
        "cors_headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*"
        }
    }
