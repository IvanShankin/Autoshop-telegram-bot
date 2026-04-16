import pytest

from src.exceptions import AccountCategoryNotFound
from src.exceptions.business import TheOnlyTranslation, TranslationAlreadyExists
from src.models.create_models.category import CreateCategoryTranslate
from src.models.update_models.category import UpdateCategoryTranslationsDTO


@pytest.mark.asyncio
async def test_get_all_translations_category_returns_all_rows(
    container_fix,
    create_category,
    create_translate_category,
):
    category = await create_category(filling_redis=False, name="translations-root")
    await create_translate_category(
        category_id=category.category_id,
        filling_redis=False,
        language="en",
        name="english-name",
        description="english-description",
    )

    translations = await container_fix.translations_category_service.get_all_translations_category(category.category_id)
    assert {item.lang for item in translations} == {"ru", "en"}


@pytest.mark.asyncio
async def test_create_translation_in_category_persists_and_updates_cache(
    container_fix,
    create_category,
):
    category = await create_category(filling_redis=False, name="create-translate-root")

    created = await container_fix.translations_category_service.create_translation_in_category(
        CreateCategoryTranslate(
            category_id=category.category_id,
            lang="en",
            name="english-name",
            description="english-description",
        ),
        make_commit=True,
        filling_redis=True,
    )

    assert created.language == "en"
    cached = await container_fix.categories_cache_repo.get_category(category.category_id, "en")
    assert cached is not None
    assert cached.name == "english-name"


@pytest.mark.asyncio
async def test_create_translation_in_category_rejects_duplicate_language(
    container_fix,
    create_category,
):
    category = await create_category(filling_redis=False, name="duplicate-root")

    await container_fix.translations_category_service.create_translation_in_category(
        CreateCategoryTranslate(
            category_id=category.category_id,
            lang="en",
            name="english-name",
            description="english-description",
        ),
        make_commit=True,
        filling_redis=False,
    )

    with pytest.raises(TranslationAlreadyExists):
        await container_fix.translations_category_service.create_translation_in_category(
            CreateCategoryTranslate(
                category_id=category.category_id,
                lang="en",
                name="english-name-2",
                description="english-description-2",
            ),
            make_commit=True,
            filling_redis=False,
        )


@pytest.mark.asyncio
async def test_create_translation_in_category_rejects_missing_category(container_fix):
    with pytest.raises(AccountCategoryNotFound):
        await container_fix.translations_category_service.create_translation_in_category(
            CreateCategoryTranslate(
                category_id=999999999,
                lang="en",
                name="english-name",
                description="english-description",
            ),
            make_commit=True,
            filling_redis=False,
        )


@pytest.mark.asyncio
async def test_update_category_translation_updates_rows_and_cache(
    container_fix,
    create_category,
    create_translate_category,
):
    category = await create_category(filling_redis=False, name="update-translate-root")
    await create_translate_category(
        category_id=category.category_id,
        filling_redis=False,
        language="en",
        name="english-name",
        description="english-description",
    )

    updated = await container_fix.translations_category_service.update_category_translation(
        UpdateCategoryTranslationsDTO(
            category_id=category.category_id,
            language="en",
            name="updated-name",
            description="updated-description",
        ),
        make_commit=True,
        filling_redis=True,
    )

    assert updated.name == "updated-name"
    cached = await container_fix.categories_cache_repo.get_category(category.category_id, "en")
    assert cached is not None
    assert cached.name == "updated-name"


@pytest.mark.asyncio
async def test_delete_all_category_translation_clears_cache(
    container_fix,
    create_category,
    create_translate_category,
):
    category = await create_category(filling_redis=False, name="delete-all-root")
    await create_translate_category(
        category_id=category.category_id,
        filling_redis=False,
        language="en",
        name="english-name",
        description="english-description",
    )

    await container_fix.translations_category_service.delete_all_category_translation(
        category.category_id,
        make_commit=True,
        filling_redis=True,
    )

    assert await container_fix.translations_category_service.get_all_translations_category(category.category_id) == []
    assert await container_fix.categories_cache_repo.get_category(category.category_id, "ru") is None
    assert await container_fix.categories_cache_repo.get_category(category.category_id, "en") is None


@pytest.mark.asyncio
async def test_delete_category_translation_removes_one_language_and_refreshes_cache(
    container_fix,
    create_category,
    create_translate_category,
):
    category = await create_category(filling_redis=False, name="delete-one-root")
    await create_translate_category(
        category_id=category.category_id,
        filling_redis=False,
        language="en",
        name="english-name",
        description="english-description",
    )

    await container_fix.translations_category_service.delete_category_translation(
        category.category_id,
        "en",
        make_commit=True,
        filling_redis=True,
    )

    translations = await container_fix.translations_category_service.get_all_translations_category(category.category_id)
    assert {item.lang for item in translations} == {"ru"}
    assert await container_fix.categories_cache_repo.get_category(category.category_id, "en") is None
    assert await container_fix.categories_cache_repo.get_category(category.category_id, "ru") is not None


@pytest.mark.asyncio
async def test_delete_category_translation_rejects_last_translation(
    container_fix,
    create_category,
):
    category = await create_category(filling_redis=False, name="only-translation-root")

    with pytest.raises(TheOnlyTranslation):
        await container_fix.translations_category_service.delete_category_translation(
            category.category_id,
            "ru",
            make_commit=True,
            filling_redis=False,
        )
