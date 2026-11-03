from fastapi import APIRouter

from backend.app.api.routes import auth, workspaces

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(workspaces.router)
