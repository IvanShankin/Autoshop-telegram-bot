import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import MAIN_ADMIN, TYPE_PAYMENTS, TYPE_ACCOUNT_SERVICES, UI_IMAGES
from src.services.system.models.models import UiImages
from src.services.users.models import Users, NotificationSettings
from src.services.system.models import Settings, TypePayments
from src.services.database.database import Base
from src.services.database.database import get_db, SQL_DB_URL, DB_NAME, POSTGRES_SERVER_URL
from src.services.referrals.utils import create_unique_referral_code
from src.services.admins.models import MessageForSending
from src.services.admins.models import Admins
from src.services.referrals.models import ReferralLevels
from src.services.selling_accounts.models import TypeAccountServices


async def create_database():
    """Создает базу данных и все таблицы в ней (если существует, то ничего не произойдёт) """
    # Сначала подключаемся к серверу PostgreSQL без указания конкретной базы
    engine = create_async_engine(POSTGRES_SERVER_URL, isolation_level="AUTOCOMMIT")
    try:
        # Проверяем существование базы данных и создаем если ее нет
        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
            )
            database_exists = result.scalar() == 1

            if not database_exists: # если БД нет
                logging.info(f"Creating database {DB_NAME}...")
                await conn.execute(text(f"CREATE DATABASE {DB_NAME}"))
                logging.info(f"Database {DB_NAME} created successfully")
            else:
                logging.info(f"Database {DB_NAME} already exists")
    except Exception as e:
        logging.error(f"Error checking/creating database: {e}")
        raise
    finally:
        await engine.dispose()

    # создание таблицы
    await create_table()

    # заполнение таблиц
    await filling_settings()
    await filling_referral_lvl()
    await filling_admins(MAIN_ADMIN)
    for type_payment in TYPE_PAYMENTS:
        await filling_type_payment(type_payment)
    for type_account_services in TYPE_ACCOUNT_SERVICES:
        await filling_type_account_services(type_account_services)
    for key in UI_IMAGES:
        await filling_ui_image(key=key, path=UI_IMAGES[key])

async def create_table():
    """создает таблицы в целевой базе данных"""
    engine = create_async_engine(SQL_DB_URL)
    try:
        async with engine.begin() as conn:
            logging.info("Creating database tables...")
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
            new_message_for_sending = MessageForSending(user_id=admin_id)
            async with get_db() as session_db:
                session_db.add(new_user)
                session_db.add(new_notification_settings)
                session_db.add(new_message_for_sending)
                await session_db.commit()

        async with get_db() as session_db:
            new_admin = Admins(user_id=admin_id)
            session_db.add(new_admin)
            await session_db.commit()

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

async def filling_type_account_services(type_account_services: str):
    async with get_db() as session_db:
        result = await session_db.execute(select(TypeAccountServices).where(TypeAccountServices.name == type_account_services))
        result_payment = result.scalar()

        if not result_payment:
            new_type_account_services = TypeAccountServices(name=type_account_services)
            session_db.add(new_type_account_services)
            await session_db.commit()








