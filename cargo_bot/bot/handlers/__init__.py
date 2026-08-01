from aiogram import Router

from . import admin, user

router = Router()
# админский роутер первым: его фильтры строже (IsAdmin + состояния)
router.include_router(admin.router)
router.include_router(user.router)
