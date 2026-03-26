from datetime import datetime, timezone
from typing import List, Optional

from src.bot_actions.messages.schemas import EventSentLog, LogLevel
from src.config import Config
from src.infrastructure.rebbit_mq.producer import publish_event
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.discounts import CreatePromoCodeDTO
from src.models.read_models.other import PromoCodesDTO
from src.repository.database.admins import AdminActionsRepository
from src.repository.database.discount import PromoCodeRepository
from src.repository.redis import PromoCodesCacheRepository
from src.utils.codes import generate_code


class PromoCodeService:

    def __init__(
        self,
        promo_repo: PromoCodeRepository,
        admin_actions_repo: AdminActionsRepository,
        cache_repo: PromoCodesCacheRepository,
        conf: Config,
        session_db: AsyncSession,
    ):
        self.promo_repo = promo_repo
        self.admin_actions_repo = admin_actions_repo
        self.cache_repo = cache_repo
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
