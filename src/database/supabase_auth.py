"""
Supabase Authentication Module for Tax Extraction System.
Handles user registration, login, and token management.
"""

import os
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import asyncio
from dotenv import load_dotenv

from supabase import create_client, Client
from supabase.client import AsyncClient, create_async_client
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

load_dotenv()

# ========================= Configuration =========================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("Please set SUPABASE_URL and SUPABASE_KEY environment variables")

# ========================= Auth Manager =========================

class SupabaseAuthManager:
    """Manages Supabase authentication operations."""
    
    def __init__(self):
        """Initialize Supabase client for auth operations."""
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        self.service_client: Optional[Client] = None
        if SUPABASE_SERVICE_KEY:
            self.service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    # =================== User Registration ===================
    
    def register_user(self, email: str, password: str, metadata: Optional[Dict] = None) -> Dict:
        """
        Register a new user with email and password.
        
        Args:
            email: User's email address
            password: User's password (min 6 characters)
            metadata: Optional user metadata (name, company, etc.)
        
        Returns:
            Dict with user info and session
        """
        try:
            # Sign up the user
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": metadata or {}
                }
            })
            
            if response.user:
                return {
                    "success": True,
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "created_at": response.user.created_at,
                        "metadata": response.user.user_metadata
                    },
                    "session": {
                        "access_token": response.session.access_token if response.session else None,
                        "refresh_token": response.session.refresh_token if response.session else None,
                        "expires_at": response.session.expires_at if response.session else None
                    } if response.session else None,
                    "message": "User registered successfully. Please check your email for verification."
                }
            else:
                return {
                    "success": False,
                    "message": "Registration failed"
                }
                
        except Exception as e:
            error_msg = str(e)
            if "User already registered" in error_msg:
                return {
                    "success": False,
                    "message": "This email is already registered"
                }
            return {
                "success": False,
                "message": f"Registration error: {error_msg}"
            }
    
    # =================== User Login ===================
    
    def login_user(self, email: str, password: str) -> Dict:
        """
        Login user with email and password.
        
        Args:
            email: User's email address
            password: User's password
        
        Returns:
            Dict with user info and session tokens
        """
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user and response.session:
                return {
                    "success": True,
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "role": response.user.role,
                        "metadata": response.user.user_metadata
                    },
                    "session": {
                        "access_token": response.session.access_token,
                        "refresh_token": response.session.refresh_token,
                        "expires_at": response.session.expires_at,
                        "expires_in": response.session.expires_in
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "Invalid email or password"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Login error: {str(e)}"
            }
    
    # =================== Token Management ===================
    
    def verify_token(self, access_token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Verify an access token and get user info.
        
        Args:
            access_token: JWT access token
        
        Returns:
            Tuple of (is_valid, user_info)
        """
        try:
            # Get user from token
            response = self.client.auth.get_user(access_token)
            
            if response and response.user:
                return True, {
                    "id": response.user.id,
                    "email": response.user.email,
                    "role": response.user.role,
                    "metadata": response.user.user_metadata
                }
            
            return False, None
            
        except Exception as e:
            return False, None
    
    def refresh_token(self, refresh_token: str) -> Dict:
        """
        Refresh an access token using refresh token.
        
        Args:
            refresh_token: Refresh token
        
        Returns:
            Dict with new session info
        """
        try:
            response = self.client.auth.refresh_session(refresh_token)
            
            if response.session:
                return {
                    "success": True,
                    "session": {
                        "access_token": response.session.access_token,
                        "refresh_token": response.session.refresh_token,
                        "expires_at": response.session.expires_at,
                        "expires_in": response.session.expires_in
                    }
                }
            
            return {
                "success": False,
                "message": "Failed to refresh token"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Refresh error: {str(e)}"
            }
    
    def logout_user(self, access_token: str) -> Dict:
        """
        Logout user and invalidate token.
        
        Args:
            access_token: Current access token
        
        Returns:
            Dict with logout status
        """
        try:
            # Set the session first
            self.client.auth.set_session(access_token, "")
            # Then sign out
            self.client.auth.sign_out()
            
            return {
                "success": True,
                "message": "Logged out successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Logout error: {str(e)}"
            }
    
    # =================== User Management ===================
    
    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """
        Get user profile information.
        
        Args:
            user_id: User's UUID
        
        Returns:
            User profile data or None
        """
        if not self.service_client:
            return None
            
        try:
            # Use service client to get user data
            response = self.service_client.auth.admin.get_user_by_id(user_id)
            
            if response:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "created_at": response.user.created_at,
                    "updated_at": response.user.updated_at,
                    "metadata": response.user.user_metadata
                }
            
            return None
            
        except Exception as e:
            print(f"Error getting user profile: {e}")
            return None
    
    def update_user_metadata(self, user_id: str, metadata: Dict) -> bool:
        """
        Update user metadata.
        
        Args:
            user_id: User's UUID
            metadata: New metadata to merge
        
        Returns:
            Success status
        """
        if not self.service_client:
            return False
            
        try:
            response = self.service_client.auth.admin.update_user_by_id(
                user_id,
                {"user_metadata": metadata}
            )
            return response is not None
            
        except Exception as e:
            print(f"Error updating user metadata: {e}")
            return False
    
    # =================== Password Management ===================
    
    def request_password_reset(self, email: str) -> Dict:
        """
        Request password reset email.
        
        Args:
            email: User's email address
        
        Returns:
            Status dict
        """
        try:
            self.client.auth.reset_password_email(email)
            
            return {
                "success": True,
                "message": "Password reset email sent. Please check your inbox."
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Password reset error: {str(e)}"
            }
    
    def update_password(self, access_token: str, new_password: str) -> Dict:
        """
        Update user password (requires valid session).
        
        Args:
            access_token: Current access token
            new_password: New password
        
        Returns:
            Status dict
        """
        try:
            # Set the session
            self.client.auth.set_session(access_token, "")
            
            # Update the password
            response = self.client.auth.update_user({
                "password": new_password
            })
            
            if response.user:
                return {
                    "success": True,
                    "message": "Password updated successfully"
                }
            
            return {
                "success": False,
                "message": "Failed to update password"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Password update error: {str(e)}"
            }

# ========================= FastAPI Dependencies =========================

security = HTTPBearer()
auth_manager = SupabaseAuthManager()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """
    FastAPI dependency to get current authenticated user.
    
    Args:
        credentials: Bearer token from request
    
    Returns:
        User info dict
    
    Raises:
        HTTPException: If token is invalid
    """
    token = credentials.credentials
    
    # Verify the token
    is_valid, user_info = auth_manager.verify_token(token)
    
    if not is_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_info

async def get_optional_user(request: Request) -> Optional[Dict]:
    """
    FastAPI dependency to optionally get authenticated user.
    Returns None if no valid token, instead of raising exception.
    
    Args:
        request: FastAPI request object
    
    Returns:
        User info dict or None
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.replace("Bearer ", "")
    is_valid, user_info = auth_manager.verify_token(token)
    
    return user_info if is_valid else None

# ========================= Utility Functions =========================

def create_test_users():
    """Create test users for development."""
    auth = SupabaseAuthManager()
    
    test_users = [
        {
            "email": "admin@taxextractor.com",
            "password": "Admin123!@#",
            "metadata": {
                "name": "Admin User",
                "role": "admin",
                "company": "Tax Extractor System"
            }
        },
        {
            "email": "user@taxextractor.com",
            "password": "User123!@#",
            "metadata": {
                "name": "Test User",
                "role": "user",
                "company": "Test Company"
            }
        }
    ]
    
    print("Creating test users...")
    for user_data in test_users:
        result = auth.register_user(
            email=user_data["email"],
            password=user_data["password"],
            metadata=user_data["metadata"]
        )
        
        if result["success"]:
            print(f"✓ Created user: {user_data['email']}")
        else:
            print(f"✗ Failed to create {user_data['email']}: {result['message']}")
    
    print("\nTest user credentials:")
    print("  Admin: admin@taxextractor.com / Admin123!@#")
    print("  User: user@taxextractor.com / User123!@#")

def test_authentication():
    """Test authentication flow."""
    auth = SupabaseAuthManager()
    
    print("\n" + "="*60)
    print("TESTING SUPABASE AUTHENTICATION")
    print("="*60)
    
    # Test login
    print("\n1. Testing login...")
    login_result = auth.login_user("admin@taxextractor.com", "Admin123!@#")
    
    if login_result["success"]:
        print("✓ Login successful")
        print(f"  User ID: {login_result['user']['id']}")
        print(f"  Email: {login_result['user']['email']}")
        print(f"  Token expires at: {login_result['session']['expires_at']}")
        
        access_token = login_result['session']['access_token']
        refresh_token = login_result['session']['refresh_token']
        
        # Test token verification
        print("\n2. Testing token verification...")
        is_valid, user_info = auth.verify_token(access_token)
        if is_valid:
            print("✓ Token is valid")
            print(f"  User: {user_info['email']}")
        else:
            print("✗ Token validation failed")
        
        # Test token refresh
        print("\n3. Testing token refresh...")
        refresh_result = auth.refresh_token(refresh_token)
        if refresh_result["success"]:
            print("✓ Token refreshed successfully")
            print(f"  New token expires at: {refresh_result['session']['expires_at']}")
        else:
            print("✗ Token refresh failed")
        
        # Test logout
        print("\n4. Testing logout...")
        logout_result = auth.logout_user(access_token)
        if logout_result["success"]:
            print("✓ Logout successful")
        else:
            print("✗ Logout failed")
    else:
        print(f"✗ Login failed: {login_result['message']}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "create-users":
            create_test_users()
        elif sys.argv[1] == "test":
            test_authentication()
        else:
            print("Usage: python supabase_auth.py [create-users|test]")
    else:
        print("Supabase Auth Module")
        print("Usage: python supabase_auth.py [create-users|test]")
        print("  create-users - Create test users")
        print("  test - Test authentication flow")