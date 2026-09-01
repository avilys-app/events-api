"""Registration, login, and token handling."""

from app.users.models import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

REGISTRATION = {
    "email": "new@example.com",
    "password": "long-enough-password",
    "firstName": "New",
    "lastName": "Person",
}


async def test_register_returns_token_and_user(client: AsyncClient) -> None:
    response = await client.post("/api/auth/register", json=REGISTRATION)

    assert response.status_code == 201
    body = response.json()
    assert body["accessToken"]
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["favoriteEventIds"] == []
    assert "passwordHash" not in body["user"]


async def test_register_rejects_duplicate_email(client: AsyncClient) -> None:
    await client.post("/api/auth/register", json=REGISTRATION)
    response = await client.post("/api/auth/register", json=REGISTRATION)

    assert response.status_code == 409
    assert response.json() == {
        "statusCode": 409,
        "message": "A user with this email already exists",
        "error": "Conflict",
    }


async def test_register_rejects_short_password(client: AsyncClient) -> None:
    response = await client.post("/api/auth/register", json={**REGISTRATION, "password": "short"})

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "Bad Request"
    assert isinstance(body["message"], list)


async def test_login_succeeds_with_correct_password(client: AsyncClient, user: User) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
    )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.id


async def test_login_rejects_wrong_password(client: AsyncClient, user: User) -> None:
    response = await client.post("/api/auth/login", json={"email": user.email, "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password"


async def test_login_hides_whether_email_exists(client: AsyncClient, user: User) -> None:
    known = await client.post("/api/auth/login", json={"email": user.email, "password": "wrong"})
    unknown = await client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
    )

    assert known.status_code == unknown.status_code == 401
    assert known.json() == unknown.json()


async def test_password_is_hashed_not_stored(client: AsyncClient, session: AsyncSession) -> None:
    await client.post("/api/auth/register", json=REGISTRATION)

    stored = await session.scalar(
        User.__table__.select().where(User.email == "new@example.com")  # type: ignore[arg-type]
    )
    assert stored is not None
    assert REGISTRATION["password"] not in str(stored)


async def test_protected_route_rejects_missing_token(client: AsyncClient) -> None:
    response = await client.get("/api/users/profile")

    assert response.status_code == 401
    assert response.json() == {"statusCode": 401, "message": "Unauthorized"}


async def test_protected_route_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.get("/api/users/profile", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


async def test_profile_returns_authenticated_user(
    client: AsyncClient, user: User, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/users/profile", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["email"] == user.email
