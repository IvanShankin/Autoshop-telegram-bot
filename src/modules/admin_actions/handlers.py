from aiogram import Router

from src.middlewares.database import DataBaseSessionMiddleware

router = Router()
router.message.middleware(DataBaseSessionMiddleware())