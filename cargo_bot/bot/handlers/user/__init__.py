from aiogram import Router

from . import calculate, info, order, start, track

router = Router()
router.include_router(start.router)
router.include_router(calculate.router)
router.include_router(order.router)
router.include_router(track.router)
router.include_router(info.router)
