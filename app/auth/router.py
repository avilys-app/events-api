"""Authentication endpoints."""

from fastapi import APIRouter, status

from app.auth import service
from app.core.dependencies import DbSession
from app.users.schemas import AuthResponse, LoginRequest, RegisterRequest

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={status.HTTP_409_CONFLICT: {"description": "Email already in use"}},
)
async def register(payload: RegisterRequest, session: DbSession) -> AuthResponse:
    return await service.register(session, payload)


@router.post(
    "/login",
    summary="Log in with email and password",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Invalid credentials"}},
)
async def login(payload: LoginRequest, session: DbSession) -> AuthResponse:
    return await service.login(session, payload.email, payload.password)
