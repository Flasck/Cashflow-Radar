from fastapi import APIRouter


router = APIRouter(tags=["health"])


@router.get("/health")
async def check_health() -> dict[str, str]:
    return {"status": "ok"}
