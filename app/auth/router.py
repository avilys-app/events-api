"""Authentication endpoints."""

from fastapi import APIRouter, status

from app.auth import service
from app.core.dependencies import DbSession
from app.mailer.dependencies import EmailSenderDependency
from app.users.schemas import (
    AuthResponse,
    ConfirmEmailRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResendConfirmationRequest,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        status.HTTP_409_CONFLICT: {"description": "Email already in use"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Confirmation email unavailable"},
    },
)
async def register(
    payload: RegisterRequest,
    session: DbSession,
    email_sender: EmailSenderDependency,
) -> MessageResponse:
    return await service.register(session, payload, email_sender)


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
    email_sender: EmailSenderDependency,
) -> MessageResponse:
    return await service.resend_confirmation(session, payload.email, email_sender)


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
