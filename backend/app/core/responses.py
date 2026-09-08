from fastapi.responses import JSONResponse


def message(text: str, status_code: int) -> JSONResponse:
    return JSONResponse({"message": text}, status_code=status_code)
