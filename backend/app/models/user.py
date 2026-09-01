"""
Academix AI — User Models (Pydantic Schemas)
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# --- Request Schemas ---

class UserCreate(BaseModel):
    """Schema for creating a new user (admin operation)."""
    email: EmailStr
    password: str
    full_name: str
    role: str  # 'admin' | 'teacher' | 'student'
    department: Optional[str] = None
    phone: Optional[str] = None


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class UserRoleUpdate(BaseModel):
    """Schema for updating user role (admin only)."""
    role: str  # 'admin' | 'teacher' | 'student'


# --- Response Schemas ---

class UserResponse(BaseModel):
    """User profile response."""
    id: str
    email: str
    full_name: str
    role: str
    department: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None


class UserListResponse(BaseModel):
    """Paginated user list response."""
    users: list[UserResponse]
    total: int
    page: int
    page_size: int


# --- Auth Schemas ---

class LoginRequest(BaseModel):
    """Login request."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response with tokens."""
    access_token: str
    refresh_token: str
    user: UserResponse


class SignUpRequest(BaseModel):
    """Sign-up request (for admin creating users)."""
    email: EmailStr
    password: str
    full_name: str
    role: str = "student"
    department: Optional[str] = None
