# Authentication

## Overview

Jobs Agent uses JWT (JSON Web Token) authentication with bcrypt password hashing.

## Flow

```
┌─────────┐      ┌─────────┐      ┌─────────┐
│ Client  │      │  API    │      │  Store  │
└────┬────┘      └────┬────┘      └────┬────┘
     │                │                │
     │  POST /register │                │
     │───────────────▶│                │
     │                │  hash password │
     │                │───────────────▶│
     │                │                │
     │   User created │                │
     │◀───────────────│                │
     │                │                │
     │  POST /login   │                │
     │───────────────▶│                │
     │                │ verify password│
     │                │───────────────▶│
     │                │                │
     │   JWT token    │                │
     │◀───────────────│                │
     │                │                │
     │  GET /protected│                │
     │  (with token)  │                │
     │───────────────▶│                │
     │                │ verify JWT     │
     │                │───────────────▶│
     │                │                │
     │   Response     │                │
     │◀───────────────│                │
     │                │                │
```

## JWT Token Structure

```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "is_admin": false,
  "exp": 1704067200
}
```

- `sub`: User ID (subject)
- `email`: User email
- `is_admin`: Admin flag
- `exp`: Expiration timestamp (24 hours from creation)

## Password Security

Passwords are hashed using bcrypt with automatic salt generation:

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hashing
hashed = pwd_context.hash(password)

# Verification
is_valid = pwd_context.verify(password, hashed)
```

## Token Validation

On each request, the JWT is validated:

1. Check signature using secret key
2. Check expiration time
3. Extract user ID from `sub` claim
4. Load user from store
5. Return user object or raise 401

## Admin Role

- First registered user automatically becomes admin
- Admin status stored in user record
- Admin-only endpoints check `is_admin` flag

## Security Configuration

```python
# Required environment variable
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

# In production, use a strong random key:
# python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Frontend Integration

Token stored in localStorage and included in requests:

```typescript
// Store token after login
localStorage.setItem('auth_token', token)

// Add to requests via Axios interceptor
config.headers.Authorization = `Bearer ${token}`

// Clear on logout or 401 response
localStorage.removeItem('auth_token')
```

## Session Management

- Tokens expire after 24 hours
- No server-side session storage (stateless)
- Token must be included in every request
- Refresh tokens not implemented (re-login required)

## Security Considerations

1. **Secret Key**: Use a strong, randomly generated secret key
2. **HTTPS**: Always use HTTPS in production
3. **Token Storage**: localStorage is vulnerable to XSS; consider httpOnly cookies for sensitive apps
4. **Password Requirements**: Minimum 8 characters enforced by validation
5. **Rate Limiting**: Consider adding rate limiting for login attempts
