import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import get_config
from src.services.database.admins.actions import create_admin
from src.services.database.system.models.models import Files
from src.utils.ui_images_data import get_ui_images
from src.services.database.users.models import Users, NotificationSettings
from src.services.database.system.models import Settings, TypePayments, UiImages
from src.services.database.core.database import get_db, Base
from src.services.database.referrals.utils import create_unique_referral_code
from src.services.database.referrals.models import ReferralLevels
from src.services.database.admins.models import Admins


async def create_database():
    """Создает базу данных и все таблицы в ней (если существует, то ничего не произойдёт) """
    # Сначала подключаемся к серверу PostgreSQL без указания конкретной базы
    conf = get_config()
    engine = create_async_engine(conf.db_connection.postgres_server_url, isolation_level="AUTOCOMMIT")

    try:
        # Проверяем существование базы данных и создаем если ее нет
        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname = '{conf.env.db_name}'")
            )
            database_exists = result.scalar() == 1

            if not database_exists: # если БД нет
                logging.info(f"Creating core {conf.env.db_name}...")
                await conn.execute(text(f"CREATE DATABASE {conf.env.db_name}"))
                logging.info(f"Database {conf.env.db_name} created successfully")
            else:
                logging.info(f"Database {conf.env.db_name} already exists")
    except Exception as e:
        logging.error(f"Error checking/creating core: {e}")
        raise
    finally:
        await engine.dispose()

    # создание таблицы
    await create_table()

    # заполнение таблиц
    await filling_settings()
    await filling_referral_lvl()
    await filling_admins(conf.env.main_admin)
    for type_payment in conf.app.type_payments:
        await filling_type_payment(type_payment)

    ui_images = get_ui_images()
    for key in ui_images:
        await filling_ui_image(key=key, path=str(ui_images[key]))

    example_univers_import = conf.file_keys.example_zip_for_universal_import_key
    await filling_files(key=example_univers_import.key, path=example_univers_import.name_in_dir_with_files)


async def create_table():
    """создает таблицы в целевой базе данных"""
    engine = create_async_engine(get_config().db_connection.sql_db_url)
    try:
        async with engine.begin() as conn:
            logging.info("Creating core tables...")
            await conn.run_sync(Base.metadata.create_all)
            logging.info("Database tables created successfully")
    except Exception as e:
        logging.error(f"Error creating tables: {e}")
        raise
    finally:
        await engine.dispose()


async def filling_settings():
    async with get_db() as session_db:
        result = await session_db.execute(select(Settings))
        result_settings = result.scalars().first()

        if not result_settings:
            new_settings = Settings()
            session_db.add(new_settings)
            await session_db.commit()


async def filling_ui_image(key: str, path: str):
    async with get_db() as session_db:
        result = await session_db.execute(select(UiImages).where(UiImages.key == key))
        result_image = result.scalar_one_or_none()

        if result_image is None:
            image = UiImages( key=key, file_path=path)
            session_db.add(image)
            await session_db.commit()


async def filling_files(key: str, path: str):
    async with get_db() as session_db:
        result = await session_db.execute(select(Files).where(Files.key == key))
        result_file = result.scalar_one_or_none()

        if result_file:
            return

        file = Files(key=key, file_path=path)
        session_db.add(file)
        await session_db.commit()


async def filling_referral_lvl():
    async with get_db() as session_db:
        result = await session_db.execute(select(ReferralLevels))
        result_lvl = result.scalar()

        if result_lvl is None:
            first_lvl = ReferralLevels(level=1, amount_of_achievement=0, percent=3)
            second_lvl = ReferralLevels(level=2, amount_of_achievement=2000, percent=4)

            session_db.add(first_lvl)
            session_db.add(second_lvl)

            await session_db.commit()


async def filling_admins(admin_id: int):
    """Создаст нового админа. Если в БД нет админа, то создаст его, если в БД нет, пользователя, то создаст его и уведомления для него"""
    async with get_db() as session_db:
        result = await session_db.execute(select(Admins).where(Admins.user_id == admin_id))
        result_admin = result.scalar()

    if not result_admin:
        async with get_db() as session_db:
            result = await session_db.execute(select(Users).where(Users.user_id == admin_id))
            result_user = result.scalar_one_or_none()

        if not result_user: # если в БД нет такого пользователя
            code = await create_unique_referral_code()
            new_user = Users(user_id=admin_id, unique_referral_code=code)
            new_notification_settings = NotificationSettings(user_id=admin_id)
            async with get_db() as session_db:
                session_db.add(new_user)
                session_db.add(new_notification_settings)
                await session_db.commit()

        await create_admin(admin_id)


async def filling_type_payment(type_payments: str):
    async with get_db() as session_db:
        result = await session_db.execute(select(TypePayments).where(TypePayments.name_for_admin == type_payments))
        result_payment = result.scalar()

        if not result_payment:
            result = await session_db.execute(select(TypePayments))
            all_types = result.scalars().all()
            new_index = max((service.index for service in all_types), default=-1) + 1  # вычисляем максимальный индекс

            new_type_payment = TypePayments(name_for_user=type_payments, name_for_admin=type_payments, index=new_index)
            session_db.add(new_type_payment)
            await session_db.commit()



