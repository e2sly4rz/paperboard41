from aiogram import Router

from . import menu, create, edit, sessions, delete, poll, game, open


router = Router()
router.include_router(menu.router)
router.include_router(create.router)
router.include_router(edit.router)
router.include_router(sessions.router)
router.include_router(delete.router)
router.include_router(poll.router)
router.include_router(game.router)
router.include_router(open.router)