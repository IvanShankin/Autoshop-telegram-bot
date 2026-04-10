import uuid
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.categories import ProductType
from src.exceptions import IncorrectedNumberButton, AccountCategoryNotFound, TheCategoryStorageAccount, \
    IncorrectedAmountSale, IncorrectedCostPrice, CategoryStoresSubcategories
from src.exceptions.business import NotEnoughArguments, TheCategoryStorageProducts, ValueErrorService
from src.models.create_models.category import CreateCategory, CreateCategoryTranslate
from src.models.read_models import CategoryFull, CategoriesDTO
from src.models.update_models.category import UpdateCategory
from src.repository.database.categories import CategoriesRepository, ProductAccountsRepository
from src.repository.redis import CategoriesCacheRepository, UiImagesCacheRepository
from src.application.models.categories.categories_cache_filler_service import CategoriesCacheFillerService
from src.application.models.categories.category_translate_service import TranslationsCategoryService
from src.application.models.systems.ui_image_service import UiImagesService


class CategoryService:

    def __init__(
        self,
        category_repo: CategoriesRepository,
        category_cache_repo: CategoriesCacheRepository,
        product_accounts_repository: ProductAccountsRepository,
        translations_category_service: TranslationsCategoryService,
        category_filler_service: CategoriesCacheFillerService,
        ui_image_cache_repo: UiImagesCacheRepository,
        ui_image_service: UiImagesService,
        session_db: AsyncSession,
    ):
        self.category_repo = category_repo
        self.category_cache_repo = category_cache_repo
        self.product_accounts_repository = product_accounts_repository
        self.translations_category_service = translations_category_service
        self.category_filler_service = category_filler_service
        self.ui_image_cache_repo = ui_image_cache_repo
        self.ui_image_service = ui_image_service
        self.session_db = session_db

    def _has_accounts_in_subtree(self, category: CategoryFull, all_categories: list[CategoryFull]) -> bool:
        """
        Проверяет, есть ли в поддереве категории хотя бы одна видимая категория-хранилище.
        Категории с show=False не учитываются и не "передают" наличие аккаунтов вверх.
        """

        # Если текущая категория скрыта — её поддерево не рассматриваем
        if not category.show:
            return False

        # Если текущая категория — хранилище и в ней есть аккаунты
        if category.is_product_storage and category.quantity_product > 0:
            return True

        # Находим дочерние категории
        children = [c for c in all_categories if c.parent_id == category.category_id]

        # Проверяем рекурсивно
        for child in children:
            if self._has_accounts_in_subtree(child, all_categories):
                return True

        return False

    async def create_category(self, data: CreateCategory) -> CategoryFull:

        if data.number_buttons_in_row is not None and (data.number_buttons_in_row < 1 or data.number_buttons_in_row > 8):
            raise IncorrectedNumberButton("Количество кнопок в строке, должно быть в диапазоне от 1 до 8")

        if data.parent_id:
            parent_category = await self.category_repo.get_by_id(data.parent_id)
            if not parent_category:
                raise AccountCategoryNotFound()
            if parent_category.is_product_storage:
                raise TheCategoryStorageAccount(
                    f"Родительский аккаунт (parent_id = {data.parent_id}) является хранилищем товаров. "
                    f"К данной категории нельзя прикрепить другую категорию"
                )

            is_main = False
        else:
            is_main = True

        next_index = max(await self.category_repo.get_max_index_by_parent(parent_id=data.parent_id), 0)
        new_ui_image = await self.ui_image_service.create_default_io_image()

        category = await self.category_repo.create_category(
            parent_id=data.parent_id,
            ui_image_key=new_ui_image.key,
            index=next_index,
            number_buttons_in_row=data.number_buttons_in_row,
            is_main=is_main,
        )

        return await self.translations_category_service.create_translation_in_category(
            data=CreateCategoryTranslate(
                category_id=category.category_id,
                language=data.language,
                name=data.name,
                description=data.description
            ),
            make_commit=True,
            filling_redis=True,
        )

    async def get_category_by_id(
        self,
        category_id: int,
        language: str = 'ru',
        fallback: str = 'ru',
        return_not_show: bool = False
    ) -> CategoryFull | None:

        category = await self.category_cache_repo.get_category(category_id, language)
        if not category:
            category_orm = await self.category_repo.get_by_id_with_translations(category_id)

            if not category_orm:
                return None

            quantity_map = await self.category_repo.get_quantity_products_map([category_id])
            category = CategoryFull.from_orm_with_translation(
                category=category_orm,
                quantity_product=quantity_map.get(category_orm.category_id, 0),
                lang=language,
                fallback=fallback
            )
            await self.category_filler_service.fill_category_by_id(category_id)

        if return_not_show:  # необходимо вернуть любую запись
            return category
        else:
            return category if category and category.show == True else None

    def _filter_categories(self, category_list: List[CategoryFull], return_not_show: bool = False):
        if return_not_show:
            sorted_list = category_list
        else:
            # Фильтрация по show и наличию товара в поддереве
            sorted_list = [
                category for category in category_list
                if category.show and self._has_accounts_in_subtree(category, category_list)
            ]

        return sorted(sorted_list, key=lambda category: category.index)

    async def get_categories(
        self,
        parent_id: int = None,
        language: str = 'ru',
        fallback: str = 'ru',
        return_not_show: bool = False
    ) -> List[CategoryFull]:
        if parent_id:
            category_list = await self.category_cache_repo.get_categories_by_parent(parent_id, language)
            if category_list:
                return self._filter_categories(category_list, return_not_show=return_not_show)


            categories_db = await self.category_repo.get_children_with_translations(parent_id)
            if not categories_db:
                return []

        else:
            category_list = await self.category_cache_repo.get_main_categories(language)
            if category_list:
                return self._filter_categories(category_list, return_not_show=return_not_show)

            categories_db = await self.category_repo.get_main_with_translations()
            if not categories_db:
                return []

            await self.category_cache_repo.set_main_categories(categories=category_list, language = 'ru')


        quantity_map = await self.category_repo.get_quantity_products_map(
            [cat.category_id for cat in categories_db]
        )

        category_list = [
            CategoryFull.from_orm_with_translation(
                category=cat,
                quantity_product=quantity_map.get(cat.category_id, 0),
                lang=language,
                fallback=fallback
            )
            for cat in categories_db
        ]
        if parent_id:
            await self.category_cache_repo.set_categories_by_parent(
                categories=category_list, parent_id=parent_id, language=language
            )
        else:
            await self.category_cache_repo.set_main_categories(
                categories=category_list, language=language
            )

        return self._filter_categories(category_list, return_not_show=return_not_show)

    async def get_quantity_products_in_category(self, category_id: int) -> int:
        products_map = await self.category_repo.get_quantity_products_map([category_id])
        return products_map.get(category_id)

    async def update_category(
        self,
        category_id: int,
        data: UpdateCategory,
        file_data: Optional[bytes] = None
    ) -> None:
        """
        :param file_data: поток байтов для создания нового ui_image, старый будет удалён
        :except IncorrectedAmountSale: Цена аккаунтов должна быть положительным числом или равно 0
        :except IncorrectedCostPrice: Себестоимость аккаунтов должна быть положительным числом
        :except IncorrectedNumberButton: Количество кнопок в строке, должно быть в диапазоне от 1 до 8
        :except AccountCategoryNotFound: Категория аккаунтов не найдена
        :except TheCategoryStorageAccount: Категория хранит аккаунты.
        :except CategoryStoresSubcategories: Категория хранит подкатегории.
        :except TheCategoryStorageProducts: При установке флага reuse_product == True, если имеются товары в категории.
        Необходимо извлечь их для применения изменений
        :except NotEnoughArguments: При недостаточном количестве аргументов при смене хранилища аккаунтов`is_product_storage`.
        :except ValueErrorService: Некорректное число у `index`.
        """

        ui_image_key = None
        ui_image = None

        if data.price is not None and data.price <= 0:
            raise IncorrectedAmountSale("Цена товара должна быть положительным числом")
        if data.cost_price is not None and data.cost_price < 0:
            raise IncorrectedCostPrice("Себестоимость товара должна быть положительным числом")
        if data.number_buttons_in_row is not None and (data.number_buttons_in_row < 1 or data.number_buttons_in_row > 8):
            raise IncorrectedNumberButton("Количество кнопок в строке, должно быть в диапазоне от 1 до 8")

        category = await self.category_repo.get_by_id(data.category_id)
        if not category:
            raise AccountCategoryNotFound(f"Категория с id = {data.category_id} не найдена")

        old_ui_image = category.ui_image_key

        if data.is_product_storage is not None:
            if data.is_product_storage:  # если хотим установить хранилище аккаунтов
                subcategories = await self.category_repo.get_children(parent_id=data.category_id, order_by_index=False)
                if subcategories:  # если данная категория хранит подкатегории
                    raise CategoryStoresSubcategories(
                        f"Категория с id = {data.category_id} хранит подкатегории. Сперва удалите их"
                    )

                if not data.product_type:
                    raise NotEnoughArguments("При установки хранилища необходимо указать тип продукта 'product_type'")

                if data.product_type == ProductType.ACCOUNT and not data.type_account_service:
                    raise NotEnoughArguments(
                        "При установки хранилища аккаунтов необходимо указать тип сервиса аккаунтов 'type_account_service'"
                    )

                if data.product_type == ProductType.UNIVERSAL and not data.media_type:
                    raise NotEnoughArguments(
                        "При установки хранилища универсальных товаров необходимо указать медиа тип товаров 'media_type'"
                    )

            else:  # если хотим убрать хранилище аккаунтов
                product_accounts = await self.product_accounts_repository.get_by_category_id(
                    category_id=data.category_id,
                    only_for_sale = False
                )
                if product_accounts:  # если данная категория хранит аккаунты
                    raise TheCategoryStorageAccount(
                        f"Категория с id = {data.category_id} хранит товары. "
                        f"Необходимо извлечь их для применения изменений"
                    )

        if data.reuse_product is not None:
            if data.reuse_product and await self.get_quantity_products_in_category(data.category_id) > 0:
                raise TheCategoryStorageProducts()

        if data.index is not None:
            try:
                new_index = int(data.index)
            except Exception:
                raise ValueErrorService("index должен быть целым числом")

            # индексы не могут быть отрицательными
            if new_index < 0:
                new_index = 0

            max_index = await self.category_repo.get_max_index_by_parent(category.parent_id)

            # если новый индекс больше максимально допустимого — ставим в конец
            if new_index > max_index:
                new_index = max_index

            # если старый индекс None — считаем, что был в конце
            old_index = category.index if category.index is not None else max_index

            # если индекс действительно меняется
            if new_index != old_index:
                if new_index < old_index:
                    # вверх
                    await self.category_repo.shift_indexes_in_range(
                        parent_id=category.parent_id,
                        start=new_index,
                        end=old_index - 1,
                        delta=1,
                    )
                else:
                    # вниз
                    await self.category_repo.shift_indexes_in_range(
                        parent_id=category.parent_id,
                        start=old_index + 1,
                        end=new_index,
                        delta=-1,
                    )

        if file_data is not None:
            ui_image = await self.ui_image_service.create_ui_image(
                key=str(uuid.uuid4()),
                file_data=file_data,
                show=category.ui_image.show if category.ui_image else True
            )
            ui_image_key = ui_image.key

        values = data.model_dump(exclude_unset=True)

        update_data = {**values}
        if not ui_image_key is None:
            update_data["ui_image_key"] = ui_image_key

        if update_data:
            await self.category_repo.update(category_id=category_id, **update_data)
            await self.session_db.commit()

            await self.category_filler_service.fill_need_category(categories=[category])

            if ui_image_key and ui_image_key:
                if category.ui_image_key:
                    await self.ui_image_service.delete_ui_image(old_ui_image, make_commit=True, filling_redis=True)

                await self.ui_image_cache_repo.set(ui_image)

    async def check_category_before_del(self, category_id: int) -> CategoriesDTO:
        """
        :except AccountCategoryNotFound: Категория с id = {category_id} не найдена
        :except TheCategoryStorageAccount: Данная категория не должна хранить аккаунты
        :except CategoryStoresSubcategories: У данной категории не должно быть подкатегорий (дочерних)
        """
        category = await self.category_repo.get_by_id(category_id)
        if not category:
            raise AccountCategoryNotFound(f"Категория с id = {category_id} не найдена")

        products = await self.get_quantity_products_in_category(category_id)
        if products or category.is_product_storage:
            raise TheCategoryStorageAccount(f"Данная категория не должна хранить аккаунты")

        subsidiary_category = await self.category_repo.get_children(category.category_id, order_by_index = False)
        if subsidiary_category:
            raise CategoryStoresSubcategories(f"У данной категории не должно быть подкатегорий (дочерних)")

        return category

    async def delete_category(self, category_id: int):
        """
        Удалит категорию аккаунтов и связанную UiImage
        :except AccountCategoryNotFound: Категория с id = {category_id} не найдена
        :except TheCategoryStorageAccount: Данная категория не должна хранить аккаунты
        :except CategoryStoresSubcategories: У данной категории не должно быть подкатегорий (дочерних)
        """
        category = await self.check_category_before_del(category_id)

        # удаление
        await self.category_repo.delete(category_id)
        await self.translations_category_service.delete_all_category_translation(category_id=category_id)

        # изменение последовательности индексов
        await self.category_repo.shift_indexes_after_delete(parent_id=category.parent_id, from_index=category.index)

        await self.session_db.commit()

        # обновление _redis
        await self.category_filler_service.fill_need_category(category_id)

        if category.ui_image_key:
            await self.ui_image_service.delete_ui_image(
                key=category.ui_image_key,
                delete_file=True,
                make_commit=True,
                filling_redis=True
            )
