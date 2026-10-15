from aiogram import Router

from . import start, schedule, my_games, host


def setup_routers() -> Router:
    router = Router()
    router.include_router(start.router)
    router.include_router(schedule.router)
    router.include_router(my_games.router)
    router.include_router(host.router)
    return router