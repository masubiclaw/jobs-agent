"""User storage with TOON format persistence."""

import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Import from existing tools
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from job_agent_coordinator.tools.toon_format import to_toon, from_toon

from .password import hash_password, verify_password

logger = logging.getLogger(__name__)


class UserStore:
    """
    Persistent storage for user accounts.
    
    Features:
    - User registration with email/password
    - Password hashing with bcrypt
    - JWT-compatible user lookup
    - Admin role management
    - TOON format storage
    """
    
    def __init__(self, storage_dir: Path = None):
        self.storage_dir = Path(storage_dir) if storage_dir else Path(".job_cache")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.users_file = self.storage_dir / "users.toon"
        self._users: Dict[str, Dict[str, Any]] = self._load_users()
        
        logger.info(f"UserStore ready: {len(self._users)} users at {self.users_file}")
    
    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        """Load users from disk."""
        if self.users_file.exists():
            try:
                data = from_toon(self.users_file.read_text())
                users_data = data.get("users", data) if isinstance(data, dict) else data
                # Handle list format (TOON may deserialize nested sections as lists)
                if isinstance(users_data, list):
                    return {u["id"]: u for u in users_data if isinstance(u, dict) and "id" in u}
                return users_data if isinstance(users_data, dict) else {}
            except Exception as e:
                logger.error(f"Failed to load users: {e}")
        return {}
    
    def _save_users(self):
        """Save users to disk."""
        data = {"users": self._users, "updated_at": datetime.now().isoformat()}
        self.users_file.write_text(to_toon(data) + '\n')
    
    def _generate_id(self) -> str:
        """Generate cryptographically secure unique user ID."""
        return str(uuid.uuid4())[:12]
    
    def create(self, email: str, password: str, name: str) -> Optional[Dict[str, Any]]:
        """
        Create a new user.
        
        Args:
            email: User email (unique identifier)
            password: Plain text password (will be hashed)
            name: User's display name
            
        Returns:
            Created user dict (without password) or None if email exists
        """
        email_lower = email.lower()
        
        # Check for existing user
        for user in self._users.values():
            if user.get("email", "").lower() == email_lower:
                logger.warning(f"User with email {email} already exists")
                return None
        
        user_id = self._generate_id()
        
        # First user becomes admin
        is_admin = len(self._users) == 0
        
        # Hard-coded admin email
        if email_lower == "justin.masui@gmail.com":
            is_admin = True

        user = {
            "id": user_id,
            "email": email_lower,
            "name": name,
            "hashed_password": hash_password(password),
            "is_admin": is_admin,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        self._users[user_id] = user
        self._save_users()
        
        logger.info(f"Created user: {name} ({email_lower}){' [ADMIN]' if is_admin else ''}")
        
        # Return without password
        return {k: v for k, v in user.items() if k != "hashed_password"}
    
    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user.
        
        Args:
            email: User email
            password: Plain text password
            
        Returns:
            User dict (without password) if authenticated, None otherwise
        """
        email_lower = email.lower()
        
        for user in self._users.values():
            if user.get("email", "").lower() == email_lower:
                if verify_password(password, user.get("hashed_password", "")):
                    logger.info(f"User authenticated: {email_lower}")
                    return {k: v for k, v in user.items() if k != "hashed_password"}
                else:
                    logger.warning(f"Invalid password for: {email_lower}")
                    return None
        
        logger.warning(f"User not found: {email_lower}")
        return None
    
    def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        user = self._users.get(user_id)
        if user:
            return {k: v for k, v in user.items() if k != "hashed_password"}
        return None
    
    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        email_lower = email.lower()
        for user in self._users.values():
            if user.get("email", "").lower() == email_lower:
                return {k: v for k, v in user.items() if k != "hashed_password"}
        return None
    
    def update(self, user_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Update user fields."""
        if user_id not in self._users:
            return None
        
        user = self._users[user_id]
        
        # Update allowed fields
        for field in ["name", "email"]:
            if field in kwargs and kwargs[field] is not None:
                user[field] = kwargs[field]
        
        # Handle password update separately
        if "password" in kwargs and kwargs["password"]:
            user["hashed_password"] = hash_password(kwargs["password"])
        
        user["updated_at"] = datetime.now().isoformat()
        self._save_users()
        
        return {k: v for k, v in user.items() if k != "hashed_password"}
    
    def set_admin(self, user_id: str, is_admin: bool) -> bool:
        """Set user's admin status."""
        if user_id not in self._users:
            return False
        
        self._users[user_id]["is_admin"] = is_admin
        self._users[user_id]["updated_at"] = datetime.now().isoformat()
        self._save_users()
        return True
    
    def delete(self, user_id: str) -> bool:
        """Delete a user."""
        if user_id not in self._users:
            return False
        
        del self._users[user_id]
        self._save_users()
        logger.info(f"Deleted user: {user_id}")
        return True
    
    def list_users(self) -> List[Dict[str, Any]]:
        """List all users (admin only)."""
        return [
            {k: v for k, v in user.items() if k != "hashed_password"}
            for user in self._users.values()
        ]
    
    def count(self) -> int:
        """Get total user count."""
        return len(self._users)


# Global store instance
_user_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    """Get or create the global user store."""
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store
