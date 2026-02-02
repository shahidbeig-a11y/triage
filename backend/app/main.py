from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

from .database import engine, SessionLocal, init_db
from .models import Category, Email, User, UserSettings  # Import all models before init_db()
from .routes import auth_router, emails_router, settings_router


# System categories to pre-populate
SYSTEM_CATEGORIES = [
    {"number": 1, "label": "Blocking", "tab": "P1", "description": "Critical blockers requiring immediate action", "icon": "🚨", "color": "#FF4444"},
    {"number": 2, "label": "Action Required", "tab": "P1", "description": "Important tasks that need completion", "icon": "⚡", "color": "#FF8C00"},
    {"number": 3, "label": "Waiting On", "tab": "P2", "description": "Pending response from others", "icon": "⏳", "color": "#FFB800"},
    {"number": 4, "label": "Time-Sensitive", "tab": "P2", "description": "Has a deadline or time constraint", "icon": "⏰", "color": "#FFA500"},
    {"number": 5, "label": "FYI", "tab": "Action", "description": "Informational, no action needed", "icon": "📋", "color": "#4A90E2"},
    {"number": 6, "label": "Discuss", "tab": "Action", "description": "Needs discussion or clarification", "icon": "💬", "color": "#9B59B6"},
    {"number": 7, "label": "Decide", "tab": "Action", "description": "Requires a decision to be made", "icon": "🤔", "color": "#E67E22"},
    {"number": 8, "label": "Delegate", "tab": "Action", "description": "Should be assigned to someone else", "icon": "👥", "color": "#1ABC9C"},
    {"number": 9, "label": "Read/Review", "tab": "Action", "description": "Documents or content to review", "icon": "📖", "color": "#3498DB"},
    {"number": 10, "label": "Low Priority", "tab": "P3", "description": "Can be addressed later", "icon": "📌", "color": "#95A5A6"},
    {"number": 11, "label": "Archive", "tab": "P3", "description": "Completed or no longer relevant", "icon": "📦", "color": "#7F8C8D"},
]


def seed_categories(db: Session):
    """Pre-populate database with system categories if they don't exist."""
    existing_count = db.query(Category).filter(Category.is_system == True).count()

    if existing_count == 0:
        for cat_data in SYSTEM_CATEGORIES:
            category = Category(
                number=cat_data["number"],
                label=cat_data["label"],
                tab=cat_data["tab"],
                description=cat_data["description"],
                is_system=True,
                icon=cat_data["icon"],
                color=cat_data["color"]
            )
            db.add(category)
        db.commit()
        print(f"✅ Seeded {len(SYSTEM_CATEGORIES)} system categories")
    else:
        print(f"✅ Found {existing_count} existing system categories")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: Initialize database and seed categories
    print("🚀 Starting up FastAPI application...")
    init_db()
    db = SessionLocal()
    try:
        seed_categories(db)
    finally:
        db.close()
    print("✅ Database initialized and ready")

    yield

    # Shutdown
    print("👋 Shutting down FastAPI application...")


# Create FastAPI app
app = FastAPI(
    title="Email Triage API",
    description="Backend API for intelligent email triage and classification",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(emails_router)
app.include_router(settings_router)


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint with category count."""
    db = SessionLocal()
    try:
        category_count = db.query(Category).filter(Category.is_system == True).count()
        return {
            "status": "ok",
            "categories": category_count
        }
    finally:
        db.close()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Email Triage API",
        "version": "1.0.0",
        "docs": "/docs"
    }
