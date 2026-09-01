"""The error envelope this API returns.

Every failure response carries a ``statusCode`` and a ``message``, plus an
``error`` reason phrase on everything except a 401:

* thrown exceptions -> ``{"statusCode": 409, "message": "...", "error": "Conflict"}``
* request validation -> ``{"statusCode": 400, "message": [...], "error": "Bad Request"}``
* rejected auth      -> ``{"statusCode": 401, "message": "Unauthorized"}``

``message`` is a single string for a thrown exception and a list of strings for
a validation failure, each entry naming the field it concerns.

This shape is a published contract that clients parse, so it deliberately
overrides FastAPI's default ``{"detail": ...}`` body and should not be changed
without versioning the API.
"""

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

_BODY_LOCATIONS = frozenset({"body", "query", "path", "header", "cookie"})


def _reason_phrase(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def _format_validation_message(error: Any) -> str:
    field = ".".join(str(part) for part in error["loc"] if part not in _BODY_LOCATIONS)
    return f"{field} {error['msg']}" if field else str(error["msg"])


async def handle_http_exception(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    body: dict[str, Any] = {"statusCode": exc.status_code, "message": exc.detail}
    # A 401 carries no reason phrase: the contract specifies just the two keys.
    if exc.status_code != status.HTTP_401_UNAUTHORIZED:
        body["error"] = _reason_phrase(exc.status_code)
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


async def handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "statusCode": status.HTTP_400_BAD_REQUEST,
            "message": [_format_validation_message(error) for error in exc.errors()],
            "error": "Bad Request",
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
