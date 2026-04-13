import os
import shutil
from typing import Generator

import pytest_asyncio

from src.config import Config, FileKeysConf, FilePathAndKey


@pytest_asyncio.fixture(autouse=True)
async def replace_paths_in_config(container_fix):
    conf = container_fix.config
    path_products = replacement_path_product(conf)
    path_ui_image = replacement_path_ui_image(conf)
    path_sent_mass_msg_image = replacement_path_sent_mass_msg_image(conf)
    path_temp = replacement_path_temp(conf)
    path_files = replacement_path_files(conf)

    # создаст временные директории, второй раз удалит их
    next(path_products)
    next(path_ui_image)
    next(path_sent_mass_msg_image)
    next(path_temp)
    next(path_files)

    yield

    # удалит временные директории
    next(path_products)
    next(path_ui_image)
    next(path_sent_mass_msg_image)
    next(path_temp)
    next(path_files)


def replacement_path_product(conf: Config) -> Generator[None, None, None]:
    base_dir = conf.paths.products_dir.parent
    product_dir = base_dir / "product_test"

    conf.paths.products_dir = product_dir
    conf.paths.accounts_dir = product_dir / "accounts_test"
    conf.paths.universals_dir = product_dir / "universals_test"

    os.makedirs(product_dir, exist_ok=True)
    os.makedirs(conf.paths.accounts_dir, exist_ok=True)
    os.makedirs(conf.paths.universals_dir, exist_ok=True)

    yield

    if os.path.isdir(product_dir):
        shutil.rmtree(product_dir) # удаляет директорию созданную для тестов

    yield


def replacement_path_ui_image(conf: Config) -> Generator[None, None, None]:
    base_dir = conf.paths.ui_sections_dir.parent
    new_ui_section_dir = base_dir / "ui_sections_test"
    conf.paths.ui_sections_dir = new_ui_section_dir

    os.makedirs(new_ui_section_dir, exist_ok=True)

    yield

    if os.path.isdir(new_ui_section_dir):
        shutil.rmtree(new_ui_section_dir)  # удаляет директорию созданную для тестов

    yield


def replacement_path_sent_mass_msg_image(conf: Config) -> Generator[None, None, None]:
    base_dir = conf.paths.sent_mass_msg_image_dir.parent
    new_sent_mass_msg_dir = base_dir / "sent_mass_msg_image_test"
    conf.paths.sent_mass_msg_image_dir = new_sent_mass_msg_dir

    os.makedirs(new_sent_mass_msg_dir, exist_ok=True)

    yield

    if os.path.isdir(new_sent_mass_msg_dir):
        shutil.rmtree(new_sent_mass_msg_dir)  # удаляет директорию созданную для тестов

    yield


def replacement_path_temp(conf: Config) -> Generator[None, None, None]:
    base_dir = conf.paths.temp_dir.parent
    new_temp_dir = base_dir / "temp_test"
    conf.paths.temp_dir = new_temp_dir

    os.makedirs(new_temp_dir, exist_ok=True)

    yield

    if os.path.isdir(new_temp_dir):
        shutil.rmtree(new_temp_dir)  # удаляет директорию созданную для тестов

    yield


def replacement_path_files(conf: Config) -> Generator[None, None, None]:
    base_dir = conf.paths.files_dir.parent
    new_files_dir = base_dir / "files_test"
    conf.paths.files_dir = new_files_dir

    os.makedirs(new_files_dir, exist_ok=True)

    conf.file_keys = FileKeysConf(
        example_zip_for_universal_import_key=FilePathAndKey(
            key="example_zip_for_universal_import",
            path=new_files_dir / "example_zip_for_universal_import.zip",
            name_in_dir_with_files="example_zip_for_universal_import.zip"
        ),
        example_zip_for_import_tg_acc_key=FilePathAndKey(
            key="example_zip_for_import_tg_acc",
            path=new_files_dir / "example_zip_for_import_tg_acc.zip",
            name_in_dir_with_files="example_zip_for_import_tg_acc.zip"
        ),
        example_csv_for_import_other_acc_key=FilePathAndKey(
            key="example_csv_for_import_other_acc",
            path=new_files_dir / "example_csv_for_import_other_acc.csv",
            name_in_dir_with_files="example_csv_for_import_other_acc.csv"
        )
    )

    yield

    if os.path.isdir(new_files_dir):
        shutil.rmtree(new_files_dir)  # удаляет директорию созданную для тестов

    yield
