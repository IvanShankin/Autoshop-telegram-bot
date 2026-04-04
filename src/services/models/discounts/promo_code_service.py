from datetime import datetime, timezone
from typing import List, Optional

from src.models.read_models import EventSentLog, LogLevel
from src.config import Config
from src.exceptions.business import AlreadyActivated
from src.exceptions.domain import PromoCodeNotFound
from src.infrastructure.rebbit_mq.producer import publish_event
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.discounts import CreatePromoCodeDTO, CreateActivatedPromoCodeDTO
from src.models.create_models.users import CreateUserAuditLogDTO
from src.models.read_models.other import PromoCodesDTO, ResultActivatePromoCodeDTO
from src.repository.database.admins import AdminActionsRepository
from src.repository.database.discount import PromoCodeRepository
from src.repository.redis import PromoCodesCacheRepository
from src.services.models.discounts import ActivatedPromoCodesService
from src.services.models.users import UserLogService
from src.utils.codes import generate_code


class PromoCodeService:

    def __init__(
        self,
        promo_repo: PromoCodeRepository,
        admin_actions_repo: AdminActionsRepository,
        cache_repo: PromoCodesCacheRepository,
        activate_promo_code_service: ActivatedPromoCodesService,
        user_log: UserLogService,
        conf: Config,
        session_db: AsyncSession,
    ):
        self.promo_repo = promo_repo
        self.admin_actions_repo = admin_actions_repo
        self.cache_repo = cache_repo
        self.activate_promo_code_service = activate_promo_code_service
        self.user_log = user_log
        self.conf = conf
        self.session_db = session_db

    async def get_promo_code_by_page(
        self,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        show_not_valid: bool = False,
    ) -> List[PromoCodesDTO]:
        if page_size is None:
            page_size = self.conf.different.page_size

        return await self.promo_repo.get_page(
            page=page,
            page_size=page_size,
            show_not_valid=show_not_valid,
        )

    async def get_count_promo_codes(self, consider_invalid: bool = False) -> int:
        """
        :param consider_invalid: Считать невалидные.
        """
        return await self.promo_repo.count(consider_invalid=consider_invalid)

    async def get_promo_code(
        self,
        code: Optional[str] = None,
        promo_code_id: Optional[int] = None,
        get_only_valid: bool = True,
    ) -> Optional[PromoCodesDTO]:
        if code and get_only_valid:
            promo = await self.cache_repo.get(code)
            if promo:
                return promo

        if code:
            return await self.promo_repo.get_by_code(code, only_valid=get_only_valid)

        if promo_code_id:
            return await self.promo_repo.get_by_id(
                promo_code_id,
                only_valid=get_only_valid,
            )

        raise ValueError("Необходимо указать хотя бы 'code' или 'promo_code_id'")

    async def create_promo_code(
        self,
        creator_id: int,
        data: CreatePromoCodeDTO,
    ) -> PromoCodesDTO:
        """
        Создаст промокод с уникальным activation_code
        :param creator_id: id админа, который создал промокод
        :raise: ValueError: если переданный code уже используется
        """
        if data.amount is not None and data.discount_percentage is not None:
            raise ValueError("Передайте только один аргумент: amount ИЛИ discount_percentage")
        if data.amount is None and data.discount_percentage is None:
            raise ValueError("Передайте хотя бы один аргумент: amount ИЛИ discount_percentage")

        code = data.code
        if code:
            if await self.cache_repo.get(code):
                raise ValueError(
                    "Данный код не уникальный! Есть ещё один активный промокод с там же кодом"
                )
        else:
            while True:
                code = generate_code()
                if not await self.cache_repo.get(code):
                    break

        promo = await self.promo_repo.create_promo_code(
            activation_code=code,
            min_order_amount=data.min_order_amount,
            amount=data.amount,
            discount_percentage=data.discount_percentage,
            number_of_activations=data.number_of_activations,
            expire_at=data.expire_at,
        )

        await self.admin_actions_repo.add_admin_action(
            user_id=creator_id,
            action_type="create_promo_code",
            message="Администрация создала новый промокод",
            details={"promo_code_id": promo.promo_code_id},
        )
        await self.session_db.commit()

        ttl = None
        if promo.expire_at:
            ttl = int((promo.expire_at - datetime.now(timezone.utc)).total_seconds())

        await self.cache_repo.set(promo, ttl=ttl)

        sale = f"Скидка от: {promo.min_order_amount} ₽\n"
        if promo.amount:
            sale += f"Сумма скидки: {promo.amount} ₽"
        elif promo.discount_percentage:
            sale += f"Процент скидки: {promo.discount_percentage} %"

        event = EventSentLog(
            text=(
                f"🛠️\n"
                f"#Админ_создал_новый_промокод \n\n"
                f"ID: {promo.promo_code_id}\n"
                f"Код активации: {promo.activation_code}\n"
                f"{sale}"
            ),
            log_lvl=LogLevel.INFO,
        )
        await publish_event(event.model_dump(), "message.send_log")

        return promo
    
    async def activate_promo_code(self, promo_code_id: int, user_id: int) -> ResultActivatePromoCodeDTO:
        """
        :except: PromoCodeNotFound
        :except: AlreadyActivated
        """
        promo_code_deactivated = False

        promo_code = await self.get_promo_code(promo_code_id=promo_code_id)
        if not promo_code:  # если промокод не найден
            raise PromoCodeNotFound()

        # проверка на повторную активацию
        activate_promo_code = await self.activate_promo_code_service.check_activate_promo_code(
            promo_code_id=promo_code_id,
            user_id=user_id
        )
        if activate_promo_code:  # если активировал ранее
            return AlreadyActivated()

        new_activated_counter = await self.promo_repo.increment_activation(
            promo_code_id=promo_code_id, current_counter=promo_code.activated_counter
        )
        promo_code.activated_counter = new_activated_counter

        await self.activate_promo_code_service.create_activate_promo_code(
            data=CreateActivatedPromoCodeDTO(
                promo_code_id=promo_code_id,
                user_id=user_id
            )
        )
        await self.user_log.create_log(
            user_id=user_id,
            data=CreateUserAuditLogDTO(
                action_type="new_activate_promo_code",
                message='Пользователь активировал промокод',
                details={
                    "promo_code_id": promo_code_id,
                },
            )
        )
        await self.session_db.commit()

        # если необходимо деактивировать
        if (
            (new_activated_counter >= promo_code.number_of_activations)
            or
            (datetime.now(timezone.utc) > promo_code.expire_at)
        ):
            promo_code = await self.promo_repo.deactivate(promo_code_id)
            await self.session_db.commit()
            promo_code_deactivated = True

        ttl = None
        if promo_code.expire_at:
            ttl = int((promo_code.expire_at - datetime.now(timezone.utc)).total_seconds())

        await self.cache_repo.set(promo_code, ttl)

        return ResultActivatePromoCodeDTO(
            promo_code=promo_code,
            deactivate=promo_code_deactivated,
        )
    
    async def deactivate_promo_code(self, user_id: int, promo_code_id: int):
        """
        :param user_id: ID админа
        :param promo_code_id: ID промокода
        """
        promo = await self.promo_repo.deactivate(promo_code_id)

        await self.admin_actions_repo.add_admin_action(
            user_id=user_id,
            action_type="deactivate_promo_code",
            message="Администрация деактивировала промокод",
            details={"promo_code_id": promo_code_id},
        )
        await self.session_db.commit()

        event = EventSentLog(
            text=(
                f"🛠️\n"
                f"#Администрация_деактивировала_промокод \n\n"
                f"promo_code_id: {promo_code_id}\n"
                f"Код промокода: {promo.activation_code if promo else '-'}\n"
                f"admin_id: {user_id}"
            ),
            log_lvl=LogLevel.INFO,
        )
        await publish_event(event.model_dump(), "message.send_log")

        if promo and promo.activation_code:
            await self.cache_repo.delete(promo.activation_code)
