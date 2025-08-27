# app/main.py
from fastapi import FastAPI, Request, HTTPException
from datetime import datetime, timezone
import logging
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from mangum import Mangum
from . import routers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(version="1.0.0")
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routers.user.router)
app.include_router(routers.auth.router)
app.include_router(routers.post.router)


@app.get("/")
def root():
    return RedirectResponse("/docs")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for Lambda"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=404, content={"detail": "Resource not found"})


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


handler = Mangum(app)
