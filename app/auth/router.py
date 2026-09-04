"""Authentication endpoints."""

from fastapi import APIRouter, status

from app.auth import service
from app.core.dependencies import CurrentUser, DbSession
from app.users.schemas import (
    AuthResponse,
    ConfirmEmailRequest,
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    ResendConfirmationRequest,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        status.HTTP_409_CONFLICT: {"description": "Email already in use"},
    },
)
async def register(
    payload: RegisterRequest,
    session: DbSession,
) -> MessageResponse:
    return await service.register(session, payload)


@router.post(
    "/confirm-email",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirm a registered email address",
    responses={status.HTTP_400_BAD_REQUEST: {"description": "Invalid or expired token"}},
)
async def confirm_email(payload: ConfirmEmailRequest, session: DbSession) -> None:
    await service.confirm_email(session, payload.token)


@router.post(
    "/resend-confirmation",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a replacement confirmation email",
)
async def resend_confirmation(
    payload: ResendConfirmationRequest,
    session: DbSession,
) -> MessageResponse:
    return await service.resend_confirmation(session, payload.email)


@router.post(
    "/login",
    summary="Log in with email and password",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid credentials"},
        status.HTTP_403_FORBIDDEN: {"description": "Email address not confirmed"},
    },
)
async def login(payload: LoginRequest, session: DbSession) -> AuthResponse:
    return await service.login(session, payload.email, payload.password)


@router.post(
    "/refresh",
    summary="Rotate a refresh token and issue fresh credentials",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Invalid or expired token"}},
)
async def refresh(payload: RefreshTokenRequest, session: DbSession) -> AuthResponse:
    return await service.refresh(session, payload.refresh_token)


@router.get(
    "/me",
    summary="Get the currently authenticated user",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid access token"}},
)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current refresh-token session",
)
async def logout(payload: RefreshTokenRequest, session: DbSession) -> None:
    await service.logout(session, payload.refresh_token)
