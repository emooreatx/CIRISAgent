"""
OAuth authentication for CIRISManager.

Provides Google Workspace OAuth for manager-level authentication,
independent of individual agent authentication.
"""

from fastapi import APIRouter, HTTPException, Request, Response, Depends, Header
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import httpx
import secrets
import json
import logging
from datetime import datetime, timedelta
import jwt
from pathlib import Path
import sqlite3
from contextlib import contextmanager
import os

logger = logging.getLogger(__name__)

# OAuth configuration
GOOGLE_CLIENT_ID = None
GOOGLE_CLIENT_SECRET = None
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

# JWT configuration
JWT_SECRET_KEY = os.getenv("MANAGER_JWT_SECRET", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Database path
DB_PATH = Path.home() / ".config" / "ciris-manager" / "auth.db"

# In-memory session storage for OAuth state (for production, use Redis)
oauth_sessions: Dict[str, Dict[str, Any]] = {}


class TokenResponse(BaseModel):
    """OAuth token response."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(default=86400)  # 24 hours
    user: Dict[str, Any]


class UserInfo(BaseModel):
    """User information from OAuth provider."""
    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    hd: Optional[str] = None  # Google Workspace domain


class ManagerUser(BaseModel):
    """Manager user information."""
    google_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime
    last_login: datetime


@contextmanager
def get_db():
    """Get database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize database tables."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS manager_sessions (
                token TEXT PRIMARY KEY,
                google_id TEXT NOT NULL,
                email TEXT NOT NULL,
                name TEXT NOT NULL,
                picture TEXT,
                created_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_google_id ON manager_sessions(google_id);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires_at ON manager_sessions(expires_at);
        """)
        conn.commit()


def load_oauth_config():
    """Load OAuth configuration from manager config."""
    global GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    
    config_path = Path.home() / ".config" / "ciris-manager" / "oauth_config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
                GOOGLE_CLIENT_ID = config.get("google_client_id")
                GOOGLE_CLIENT_SECRET = config.get("google_client_secret")
                logger.info("Loaded Google OAuth configuration for Manager")
        except Exception as e:
            logger.error(f"Failed to load OAuth config: {e}")
    else:
        logger.warning(f"OAuth config not found at {config_path}")


def create_jwt_token(user_data: dict) -> str:
    """Create JWT token for manager user."""
    payload = {
        "sub": user_data["id"],
        "email": user_data["email"],
        "name": user_data.get("name", user_data["email"]),
        "picture": user_data.get("picture"),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # Check if token exists in database and is active
        with get_db() as conn:
            result = conn.execute(
                "SELECT * FROM manager_sessions WHERE token = ? AND is_active = 1 AND expires_at > ?",
                (token, datetime.utcnow())
            ).fetchone()
            
            if not result:
                return None
                
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid token")
        return None


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Dependency to get current authenticated user.
    
    Use in protected routes:
    user = Depends(get_current_user)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    user_data = verify_token(token)
    
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user_data


def create_auth_routes() -> APIRouter:
    """Create authentication routes."""
    router = APIRouter()
    
    # Initialize database and load config on startup
    init_db()
    load_oauth_config()
    
    @router.get("/oauth/login")
    async def google_login(request: Request, redirect_uri: Optional[str] = None):
        """Initiate Google OAuth login flow."""
        if not GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=500, detail="Google OAuth not configured")
        
        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Store session data
        oauth_sessions[state] = {
            "redirect_uri": redirect_uri or f"{request.url.scheme}://{request.url.netloc}/manager",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Use appropriate callback URL based on environment
        if request.url.hostname == "localhost" or request.url.hostname == "127.0.0.1":
            callback_url = f"http://localhost:8888/manager/v1/oauth/callback"
        else:
            callback_url = "https://agents.ciris.ai/manager/oauth/callback"
        
        # Build authorization URL
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
            "hd": "ciris.ai"  # Restrict to @ciris.ai domain
        }
        
        auth_url = f"{GOOGLE_AUTH_URL}?" + "&".join(f"{k}={v}" for k, v in params.items())
        return RedirectResponse(url=auth_url)
    
    @router.get("/oauth/callback")
    async def google_callback(request: Request, code: str, state: str):
        """Handle Google OAuth callback."""
        if not GOOGLE_CLIENT_SECRET:
            raise HTTPException(status_code=500, detail="Google OAuth not configured")
        
        # Verify state token
        session_data = oauth_sessions.pop(state, None)
        if not session_data:
            raise HTTPException(status_code=400, detail="Invalid state token")
        
        # For token exchange, must use exact same URL as authorization
        if request.url.hostname == "localhost" or request.url.hostname == "127.0.0.1":
            callback_url = f"http://localhost:8888/manager/v1/oauth/callback"
        else:
            callback_url = "https://agents.ciris.ai/manager/oauth/callback"
        
        # Exchange code for token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": callback_url,
                    "grant_type": "authorization_code"
                }
            )
            
            if token_response.status_code != 200:
                logger.error(f"Token exchange failed: {token_response.text}")
                raise HTTPException(status_code=400, detail="Failed to exchange code for token")
            
            tokens = token_response.json()
            
            # Get user info
            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
            
            if userinfo_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get user info")
            
            user_data = userinfo_response.json()
            
            # Verify @ciris.ai domain
            if not user_data.get("email", "").endswith("@ciris.ai"):
                raise HTTPException(status_code=403, detail="Access restricted to @ciris.ai accounts")
            
            # Create JWT token
            jwt_token = create_jwt_token(user_data)
            
            # Store session in database
            with get_db() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO manager_sessions 
                    (token, google_id, email, name, picture, created_at, expires_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    jwt_token,
                    user_data["id"],
                    user_data["email"],
                    user_data.get("name", user_data["email"]),
                    user_data.get("picture"),
                    datetime.utcnow(),
                    datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
                    True
                ))
                conn.commit()
            
            # Log successful login
            logger.info(f"Manager login successful: {user_data['email']}")
            
            # Redirect to GUI with token
            redirect_uri = session_data["redirect_uri"]
            return RedirectResponse(url=f"{redirect_uri}?token={jwt_token}")
    
    @router.get("/auth/me")
    async def get_current_user_info(user: dict = Depends(get_current_user)):
        """Get current authenticated user information."""
        return {
            "id": user["sub"],
            "email": user["email"],
            "name": user.get("name"),
            "picture": user.get("picture"),
            "authenticated": True
        }
    
    @router.post("/auth/logout")
    async def logout(user: dict = Depends(get_current_user), authorization: str = Header(None)):
        """Logout current user."""
        token = authorization.replace("Bearer ", "")
        
        # Invalidate token in database
        with get_db() as conn:
            conn.execute(
                "UPDATE manager_sessions SET is_active = 0 WHERE token = ?",
                (token,)
            )
            conn.commit()
        
        logger.info(f"Manager logout: {user['email']}")
        
        return {"status": "logged_out", "message": "Successfully logged out"}
    
    @router.delete("/auth/sessions/expired")
    async def cleanup_expired_sessions():
        """Clean up expired sessions (maintenance endpoint)."""
        with get_db() as conn:
            result = conn.execute(
                "DELETE FROM manager_sessions WHERE expires_at < ?",
                (datetime.utcnow(),)
            )
            conn.commit()
            
        return {"deleted": result.rowcount}
    
    return router