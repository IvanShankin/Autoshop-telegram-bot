import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select, update

from src.database.models.admins import AdminActions
from src.database.models.discount import PromoCodes, ActivatedPromoCodes
from src.database.models.users import UserAuditLogs
from src.exceptions.business import AlreadyActivated
from src.exceptions.domain import PromoCodeNotFound
from src.infrastructure.redis import get_redis
from src.models.create_models.discounts import CreatePromoCodeDTO
from src.repository.database.discount import PromoCodeRepository, ActivatedPromoCodeRepository
from src.repository.redis import PromoCodesCacheRepository
from src.application.models.discounts import PromoCodeService, ActivatedPromoCodesService


@pytest.fixture()
def stub_publish_event(monkeypatch):
    calls = []

    async def _fake_publish_event(payload, routing_key):
        calls.append((payload, routing_key))

    monkeypatch.setattr("src.infrastructure.rabbit_mq.producer.publish_event", _fake_publish_event)
    monkeypatch.setattr("src.application.models.discounts.promo_code_service.publish_event", _fake_publish_event)
    monkeypatch.setattr("src.application.events.publish_event_handler.publish_event", _fake_publish_event)
    return calls


class TestPromoCodeService:

    @pytest.mark.asyncio
    async def test_get_promo_code_by_page_filters_invalid(
        self,
        session_db_fix,
        container_fix,
        create_promo_code,
    ):
        first_code = f"page_{uuid.uuid4().hex}"
        second_code = f"page_{uuid.uuid4().hex}"

        await create_promo_code(activation_code=first_code)
        await create_promo_code(activation_code=second_code)

        await session_db_fix.execute(
            update(PromoCodes)
            .where(PromoCodes.activation_code == second_code)
            .values(is_valid=False)
        )
        await session_db_fix.commit()

        result = await container_fix.promo_code_service.get_promo_code_by_page(page=1, page_size=10)
        assert all(code.is_valid for code in result)
        assert len(result) == 1

        full_result = await container_fix.promo_code_service.get_promo_code_by_page(show_not_valid=True)
        assert len(full_result) >= 2

    @pytest.mark.asyncio
    async def test_get_count_promo_codes_respects_invalid_flag(
        self,
        session_db_fix,
        container_fix,
        create_promo_code,
    ):
        await create_promo_code(activation_code=f"count_{uuid.uuid4().hex}")
        second = await create_promo_code(activation_code=f"count_{uuid.uuid4().hex}")

        await session_db_fix.execute(
            update(PromoCodes)
            .where(PromoCodes.promo_code_id == second.promo_code_id)
            .values(is_valid=False)
        )
        await session_db_fix.commit()

        assert await container_fix.promo_code_service.get_count_promo_codes() == 1
        assert await container_fix.promo_code_service.get_count_promo_codes(consider_invalid=True) == 2

    @pytest.mark.asyncio
    async def test_get_promo_code_reads_cache_and_db(
        self,
        container_fix,
        create_new_user,
    ):
        user = await create_new_user()
        code = f"cache_{uuid.uuid4().hex}"
        dto = CreatePromoCodeDTO(
            code=code,
            min_order_amount=10,
            amount=50,
            number_of_activations=2,
            expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        )

        created = await container_fix.promo_code_service.create_promo_code(
            creator_id=user.user_id,
            data=dto,
        )

        assert await get_redis().get(f"promo_code:{created.activation_code}")

        cached = await container_fix.promo_code_service.get_promo_code(code=code)
        assert cached and cached.activation_code == code

        by_id = await container_fix.promo_code_service.get_promo_code(promo_code_id=created.promo_code_id)
        assert by_id and by_id.promo_code_id == created.promo_code_id

    @pytest.mark.asyncio
    async def test_get_promo_code_requires_parameters(self, container_fix):
        with pytest.raises(ValueError):
            await container_fix.promo_code_service.get_promo_code()

    @pytest.mark.asyncio
    async def test_create_promo_code_validates_arguments(
        self,
        container_fix,
        create_new_user,
    ):
        user = await create_new_user()

        too_many = CreatePromoCodeDTO(
            min_order_amount=0,
            amount=10,
            discount_percentage=5,
            number_of_activations=1,
        )
        with pytest.raises(ValueError):
            await container_fix.promo_code_service.create_promo_code(creator_id=user.user_id, data=too_many)

        none_provided = CreatePromoCodeDTO(
            min_order_amount=0,
            number_of_activations=1,
        )
        with pytest.raises(ValueError):
            await container_fix.promo_code_service.create_promo_code(creator_id=user.user_id, data=none_provided)

    @pytest.mark.asyncio
    async def test_create_promo_code_persists_and_emits_event(
        self,
        container_fix,
        create_new_user,
        stub_publish_event,
        session_db_fix,
    ):
        user = await create_new_user()
        code = f"create_{uuid.uuid4().hex}"
        dto = CreatePromoCodeDTO(
            code=code,
            min_order_amount=5,
            amount=20,
            number_of_activations=2,
            expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        )

        created = await container_fix.promo_code_service.create_promo_code(
            creator_id=user.user_id,
            data=dto,
        )

        result = await session_db_fix.execute(
            select(PromoCodes).where(PromoCodes.promo_code_id == created.promo_code_id)
        )
        db_promo = result.scalar_one()
        assert db_promo.activation_code == code

        actions = await session_db_fix.execute(
            select(AdminActions).where(AdminActions.user_id == user.user_id)
        )
        assert actions.scalar_one_or_none() is not None

        assert await get_redis().get(f"promo_code:{code}")
        assert stub_publish_event and stub_publish_event[-1][1] == "message.send_log"

    @pytest.mark.asyncio
    async def test_activate_promo_code_creates_logs_and_deactivates(
        self,
        container_fix,
        create_new_user,
        session_db_fix,
        stub_publish_event,
    ):
        creator = await create_new_user()
        target = await create_new_user()
        dto = CreatePromoCodeDTO(
            code=f"activate_{uuid.uuid4().hex}",
            min_order_amount=1,
            amount=10,
            number_of_activations=1,
            expire_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )

        promo = await container_fix.promo_code_service.create_promo_code(
            creator_id=creator.user_id,
            data=dto,
        )

        result = await container_fix.promo_code_service.activate_promo_code(
            promo_code_id=promo.promo_code_id,
            user_id=target.user_id,
        )

        assert result.deactivate is True

        activation = await session_db_fix.execute(
            select(ActivatedPromoCodes).where(
                ActivatedPromoCodes.promo_code_id == promo.promo_code_id,
                ActivatedPromoCodes.user_id == target.user_id,
            )
        )
        assert activation.scalar_one_or_none() is not None

        promo_row = await session_db_fix.execute(
            select(PromoCodes).where(PromoCodes.promo_code_id == promo.promo_code_id)
        )
        assert promo_row.scalar_one().is_valid is False

        logs = await session_db_fix.execute(
            select(UserAuditLogs).where(UserAuditLogs.user_id == target.user_id)
        )
        assert logs.scalars().first() is not None
        assert stub_publish_event and stub_publish_event[-1][1] == "message.send_log"

    @pytest.mark.asyncio
    async def test_activate_promo_code_already_activated(
        self,
        container_fix,
        create_new_user,
    ):
        creator = await create_new_user()
        target = await create_new_user()
        dto = CreatePromoCodeDTO(
            code=f"activate_twice_{uuid.uuid4().hex}",
            min_order_amount=1,
            amount=10,
            number_of_activations=2,
            expire_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )

        promo = await container_fix.promo_code_service.create_promo_code(
            creator_id=creator.user_id,
            data=dto,
        )

        await container_fix.promo_code_service.activate_promo_code(
            promo_code_id=promo.promo_code_id,
            user_id=target.user_id,
        )

        with pytest.raises(AlreadyActivated):
            await container_fix.promo_code_service.activate_promo_code(
                promo_code_id=promo.promo_code_id,
                user_id=target.user_id,
            )

    @pytest.mark.asyncio
    async def test_activate_promo_code_not_found_raises(
        self,
        container_fix,
        create_new_user,
    ):
        user = await create_new_user()
        with pytest.raises(PromoCodeNotFound):
            await container_fix.promo_code_service.activate_promo_code(
                promo_code_id=999999999,
                user_id=user.user_id,
            )

    @pytest.mark.asyncio
    async def test_deactivate_promo_code_clears_cache_and_logs(
        self,
        container_fix,
        create_new_user,
        session_db_fix,
    ):
        user = await create_new_user()
        code = f"deactivate_{uuid.uuid4().hex}"
        dto = CreatePromoCodeDTO(
            code=code,
            min_order_amount=1,
            amount=5,
            number_of_activations=2,
            expire_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )

        promo = await container_fix.promo_code_service.create_promo_code(
            creator_id=user.user_id,
            data=dto,
        )

        assert await get_redis().get(f"promo_code:{code}")
        await container_fix.promo_code_service.deactivate_promo_code(
            promo_code_id=promo.promo_code_id,
            user_id=user.user_id,
        )

        assert await get_redis().get(f"promo_code:{code}") is None

        actions = await session_db_fix.execute(
            select(AdminActions).where(
                AdminActions.user_id == user.user_id,
                AdminActions.action_type == "deactivate_promo_code",
            )
        )
        assert actions.scalar_one_or_none() is not None
