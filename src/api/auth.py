from fastapi import APIRouter, Depends

from src.deps.auth import get_current_user
from src.models.auth import UserClaims

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserClaims)
async def get_user_info(current_user: UserClaims = Depends(get_current_user)):
    """Получение информации о текущем пользователе"""
    return current_user
