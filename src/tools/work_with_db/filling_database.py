import asyncio

from sqlalchemy import select

from src.containers.app_container import AppContainer
from src.database.models.system.models import Files, Stickers, ReplenishmentService
from src.database.models.users import Users, NotificationSettings
from src.database.models.system import Settings, TypePayments, UiImages
from src.database import get_session_factory
from src.repository.database.referrals.utils import create_unique_referral_code
from src.database.models.referrals import ReferralLevels
from src.database.models.admins import Admins



async def filling():
    """Заполнит все необходимые данные в БД"""
    app_container = AppContainer()
    try:
        conf = app_container.conf

        await filling_settings()
        await filling_referral_lvl()
        await filling_admins(conf.env.main_admin, app_container)
        for type_payment in ReplenishmentService:
            await filling_type_payment(type_payment)

        for key in conf.message_event.all_keys:
            await filling_sticker(key=key)
            await filling_ui_image(key=key)

        files_data = conf.file_keys.model_dump()
        for file_key in files_data.keys():
            await filling_files(key=files_data[file_key]["key"], path=files_data[file_key]["name_in_dir_with_files"])

        app_container.logger.info("Filling successfully")
    finally:
        await app_container.shutdown()



async def filling_settings():
    async with get_session_factory() as session_db:
        result = await session_db.execute(select(Settings))
        result_settings = result.scalars().first()

        if not result_settings:
            new_settings = Settings()
            session_db.add(new_settings)
            await session_db.commit()


async def filling_sticker(key: str):
    async with get_session_factory() as session_db:
        result = await session_db.execute(select(Stickers).where(Stickers.key == key))
        result_sticker = result.scalar_one_or_none()

        if result_sticker is None:
            image = Stickers(key=key)
            session_db.add(image)
            await session_db.commit()


async def filling_ui_image(key: str):
    async with get_session_factory() as session_db:
        result = await session_db.execute(select(UiImages).where(UiImages.key == key))
        result_image = result.scalar_one_or_none()

        if result_image is None:
            image = UiImages(key=key, file_name=f"{key}.png", show=False)
            session_db.add(image)
            await session_db.commit()


async def filling_files(key: str, path: str):
    async with get_session_factory() as session_db:
        result = await session_db.execute(select(Files).where(Files.key == key))
        result_file = result.scalar_one_or_none()

        if result_file:
            return

        file = Files(key=key, file_path=path)
        session_db.add(file)
        await session_db.commit()


async def filling_referral_lvl():
    async with get_session_factory() as session_db:
        result = await session_db.execute(select(ReferralLevels))
        result_lvl = result.scalar()

        if result_lvl is None:
            first_lvl = ReferralLevels(level=1, amount_of_achievement=0, percent=3)
            second_lvl = ReferralLevels(level=2, amount_of_achievement=2000, percent=4)

            session_db.add(first_lvl)
            session_db.add(second_lvl)

            await session_db.commit()


async def filling_admins(admin_id: int, app_container: AppContainer):
    """Создаст нового админа. Если в БД нет админа, то создаст его, если в БД нет, пользователя, то создаст его и уведомления для него"""
    async with get_session_factory() as session_db:
        result = await session_db.execute(select(Admins).where(Admins.user_id == admin_id))
        result_admin = result.scalar()

    if not result_admin:
        async with get_session_factory() as session_db:
            result = await session_db.execute(select(Users).where(Users.user_id == admin_id))
            result_user = result.scalar_one_or_none()

            if not result_user: # если в БД нет такого пользователя
                code = await create_unique_referral_code()
                new_user = Users(user_id=admin_id, unique_referral_code=code)
                new_notification_settings = NotificationSettings(user_id=admin_id)
                async with get_session_factory() as session_db:
                    session_db.add(new_user)
                    session_db.add(new_notification_settings)
                    await session_db.commit()

            request_container = app_container.get_request_container(session_db)
            request_container.admin_service.create_admin(new_user.user_id)


async def filling_type_payment(service_payments: ReplenishmentService):
    async with get_session_factory() as session_db:
        result = await session_db.execute(select(TypePayments).where(TypePayments.service == service_payments))
        result_payment = result.scalar()

        if not result_payment:
            result = await session_db.execute(select(TypePayments))
            all_types = result.scalars().all()
            new_index = max((service.index for service in all_types), default=-1) + 1  # вычисляем максимальный индекс

            new_type_payment = TypePayments(name_for_user=service_payments.value, service=service_payments, index=new_index)
            session_db.add(new_type_payment)
            await session_db.commit()


if __name__ == "__main__":
    asyncio.run(filling())