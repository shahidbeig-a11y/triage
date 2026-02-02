from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.graph import GraphClient
from ..models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/login")
async def login():
    """
    Initiate Microsoft OAuth login flow.

    Returns:
        dict: Authorization URL for Microsoft login
    """
    graph_client = GraphClient()
    auth_url = graph_client.build_auth_url()

    return {"auth_url": auth_url}


@router.get("/callback")
async def callback(code: str = None, db: Session = Depends(get_db)):
    """
    Handle OAuth callback from Microsoft.

    Args:
        code: Authorization code from Microsoft
        db: Database session

    Returns:
        Redirect to frontend with authentication complete
    """
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code required")

    try:
        graph_client = GraphClient()
        result = await graph_client.handle_callback(code, db)

        # Redirect to frontend
        return RedirectResponse(url="http://localhost:3000")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
async def get_me(db: Session = Depends(get_db)):
    """
    Get the logged-in user's information.

    Returns:
        dict: User's display name and email
    """
    # For simplicity, get the first user (in production, use sessions/cookies)
    user = db.query(User).first()

    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        # Ensure we have a valid token
        graph_client = GraphClient()
        access_token = await graph_client.get_token(user.email, db)

        # Get fresh user info from Graph API
        user_info = await graph_client._get_user_info(access_token)

        return {
            "email": user_info["email"],
            "display_name": user_info["display_name"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
