from aiogram import Router

from . import menu, create, edit, sessions, delete


router = Router()
router.include_router(menu.router)
router.include_router(create.router)
router.include_router(edit.router)
router.include_router(sessions.router)
router.include_router(delete.router)