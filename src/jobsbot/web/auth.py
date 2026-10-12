"""Single shared HTTP Basic credential pair for the whole admin API — no
per-staff roles yet (the Telegram bot side has those via bot/permissions.py,
but replicating that here is a deliberate v1 simplification, same
trade-off the user explicitly chose for the quick-start web panel).
"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from jobsbot.config import settings

security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    # compare_digest on both (not just password) to avoid leaking via
    # early-exit timing whether the username alone was right.
    username_ok = secrets.compare_digest(credentials.username, settings.web_admin_username)
    password_ok = secrets.compare_digest(credentials.password, settings.web_admin_password)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
