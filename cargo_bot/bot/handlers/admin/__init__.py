from aiogram import Router

from . import broadcast, crud, export, menu, orders, tracks

router = Router()
router.include_router(menu.router)
router.include_router(orders.router)
router.include_router(tracks.router)
router.include_router(broadcast.router)
router.include_router(export.router)
router.include_router(crud.router)
