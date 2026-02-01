## Хранение в Redis

Все значения которые хранятся с TTL навсегда, меняются в зависимости от их изменений


### Настройки (Settings)
**Ключ:** `settings`  
**Значение:**  
```json
{
    "support_username": "int",
    "maintenance_mode": "bool", 
    "channel_for_logging_id": "int",
    "channel_for_subscription_id": "int",
    "shop_name": "str",
    "channel_name": "str",
    "FAQ": "str"
}
```
**TTL:** Навсегда

### Изображения для разделов (UiImages)
**Ключ:** `ui_image:{key}`  
**Значение:** 
```json
{
    "key": "str", 
    "file_name": "str", 
    "show": "bool",
    "updated_at": "str"
}
```
**TTL:** Навсегда

### Все типы оплаты (TypePayments)
**Ключ:** `all_types_payments:`  
**Важно:** список отсортирован по возрастанию поля index <br>
**Значение:**  
```json
[
    {
        "type_payment_id": "int",
        "name_for_user": "str",
        "name_for_admin": "str",
        "is_active": "bool",
        "commission": "float",
        "index": "int",
        "extra_data": "dict"
    }
]
```
**TTL:** Навсегда

### Тип оплаты по id (TypePayments)
**Ключ:** `type_payments:{type_payment_id}`  
**Значение:**  
```json
{
    "type_payment_id": "int", 
    "name_for_user": "str",
    "name_for_admin": "str",
    "is_active": "bool",
    "commission": "float",
    "index": "int",
    "extra_data": "dict"
}
```
**TTL:** Навсегда

### Пользователь (Users)
**Ключ:** `user:{user_id}`  
**Значение:**  
```json
{
    "user_id": "int", 
    "username": "str",
    "language": "str",
    "unique_referral_code": "str",
    "balance": "int",
    "total_sum_replenishment": "int",
    "total_sum_from_referrals": "int",
    "created_at": "2024-01-15T10:30:45+03:00"
}
```
**TTL:** 6 часов


### Просьба подписаться на канал (Users)
**Ключ:** `subscription_prompt:{user_id}`
**Значение:** `_` выступает в роли метки  
**TTL:** 15 дней


### Уровни рефералов (ReferralLevels)
**Ключ:** `referral_levels`  
**Значение:**  
```json
[
    {
        "referral_level_id": "int", 
        "level": "int", 
        "amount_of_achievement": "int", 
        "percent": "int"
    }
]
```
**TTL:** Навсегда


### Админы (Admins)
**Ключ:** `admin:{user_id}`   
**Значение:** `_` выступает в роли метки  
**TTL:** Навсегда


### Забаненные аккаунты (BannedAccounts)
**Ключ:** `banned_account:{user_id}`  
**Значение:** `Причина бана`  
**TTL:** Навсегда


### Главные категории (категории где is_main == True)
**Ключ:** `main_categories:{lang}`
**Значение:**
```json
[
  {
    "category_id": "int",
    "ui_image_key": "str",
    "parent_id": "int",
    
    "language": "str",
    "name": "str",
    "description": "str",
    "index": "int",
    "show": "bool",
    "number_buttons_in_row": "int", 
    
    "is_main": "bool", 
    "is_product_storage": "bool",
    "allow_multiple_purchase": "bool",
    
    // только для тех кто хранит товары,
    "product_type": "ProductType", 
    "type_account_service": "AccountServiceType", 
    "media_type": "UniversalMediaType", 
    
    // только для категорий которые хранят универсальные товары 
    "reuse_product": "str",
    
    "price": "int",
    "cost_price": "int",
    
    "quantity_product": "int"
  }
]
```
**TTL:** навсегда


### Категории по parent_id
**Ключ:** `categories_by_parent:{parent_id}:{lang}`
**Значение:**
```json
[
  {
    "category_id": "int",
    "ui_image_key": "str",
    "parent_id": "int",
    
    "language": "str",
    "name": "str",
    "description": "str",
    "index": "int",
    "show": "bool",
    "number_buttons_in_row": "int", 
    
    "is_main": "bool",
    "is_product_storage": "bool",
    "allow_multiple_purchase": "bool",
    
    // только для тех кто хранит товары,
    "product_type": "ProductType", 
    "type_account_service": "AccountServiceType",  
    "media_type": "UniversalMediaType", 
    
    // только для категорий которые хранят универсальные товары 
    "reuse_product": "str",
    
    "price": "int",
    "cost_price": "int",
    
    "quantity_product": "int"
  }
]
```
**TTL:** навсегда


### Категория по id
**Ключ:** `category:{category_id}:{lang}`
**Значение:**
```json
{
    "category_id": "int",
    "ui_image_key": "str",
    "parent_id": "int",
    
    "language": "str",
    "name": "str",
    "description": "str",
    "index": "int",
    "show": "bool",
    "number_buttons_in_row": "int", 
    
    "is_main": "bool", 
    "is_product_storage": "bool", 
    "allow_multiple_purchase": "bool",
    
    // только для тех кто хранит товары,
    "product_type": "ProductType", 
    "type_account_service": "AccountServiceType",  
    "media_type": "UniversalMediaType", 
  
    // только для категорий которые хранят универсальные товары 
    "reuse_product": "str",
  
    "price": "int",
    "cost_price": "int",
    
    "quantity_product": "int"
}
```
**TTL:** навсегда



## ProductAccounts по category_id
**Ключ:** `product_accounts_by_category:{category_id}`
**Значение:**
```json
[
  {
    "account_id": "int",
    "category_id": "int",
    "type_account_service": "int",
    "account_storage_id": "int",
    "created_at": "2024-01-15T10:30:45+03:00"
  }
]
```
**TTL:** навсегда


## ProductAccounts по account_id
**Ключ:** `product_account:{account_id}`
**Значение:**
```json
{
    "account_id": "int",
    "category_id": "int",
    "type_account_service": "int",
    "created_at": "2024-01-15T10:30:45+03:00",
  
    "account_storage": {
        "account_storage_id": "int",
        "storage_uuid": "str",
        
        "file_path": "str",
        "checksum": "str",
        "status": "str",
        
        "encrypted_key": "str",
        "encrypted_key_nonce": "str",
        "key_version": "int",
        "encryption_algo": "str",
        
        "tg_id": "int",
        "phone_number": "str",
        "login_encrypted": "str | None",
        "login_nonce": "str | None",
        "password_encrypted": "str | None",
        "password_nonce": "str | None",
        
        "is_active": "bool",
        "is_valid": "bool",
        
        "added_at": "2024-01-15T10:30:45+03:00",
        "last_check_at": "2024-01-15T10:30:45+03:00"
    }
}
```
**TTL:** навсегда


### Проданные аккаунты по id владельца (SoldAccounts)
**Важно:** хранит только НЕ удалённые аккаунты (is_deleted == False)  
**Ключ:** `sold_accounts_by_owner_id:{owner_id}:{language}`  
**Значение:** 
```json
[
    {
        "sold_account_id": "int",
        "owner_id": "int",
        "type_account_service": "AccountServiceType",
        
        "phone_number": "str",
        "name": "str",
        "description": "str",
        
        "sold_at": "2024-01-15T10:30:45+03:00"
        
    }
]
```
**TTL:** 6 часов

### Проданные аккаунты по id аккаунта (SoldAccounts)
**Важно:** хранит только НЕ удалённые аккаунты (is_deleted == False)  
**Ключ:** `sold_account:{sold_account_id}:{language}`  
**Значение:** 
```json
{
    "sold_account_id": "int",
    "owner_id": "int",
    "type_account_service": "AccountServiceType",
    
    "name": "str",
    "description": "str",
    
    "sold_at": "2024-01-15T10:30:45+03:00",
    
    "account_storage": {
        "account_storage_id": "int",
        "storage_uuid": "str",
        
        "file_path": "str",
        "checksum": "str",
        "status": "str",
        
        "encrypted_key": "str",
        "encrypted_key_nonce": "str",
        "key_version": "int",
        "encryption_algo": "str",
        
        "tg_id": "int",
        "phone_number": "str",
        "login_encrypted": "str | None",
        "login_nonce": "str | None",
        "password_encrypted": "str | None",
        "password_nonce": "str | None",
        
        "is_active": "bool",
        "is_valid": "bool",
        
        "added_at": "2024-01-15T10:30:45+03:00",
        "last_check_at": "2024-01-15T10:30:45+03:00"
    }
}
```
**TTL:** 6 часов


## ProductUniversal по category_id
**Ключ:** `product_universal_by_category:{category_id}`
**Значение:**
```json
[
  {
    "product_universal_id": "int",
    "universal_storage_id": "int",
    "category_id": "int",
    "created_at": "2024-01-15T10:30:45+03:00"
  }
]
```
**TTL:** навсегда


## ProductUniversal по product_universal_id
**Ключ:** `product_universal:{product_universal_id}`
**Значение:**
```json
{
    "product_universal_id": "int",
    "universal_storage_id": "int",
    "category_id": "int",
    "created_at": "2024-01-15T10:30:45+03:00",
  
    "universal_storage": {
        "universal_storage_id": "int",
        "storage_uuid": "str",
        
        "file_path": "str | None",
        "original_filename": "str | None",
        "encrypted_tg_file_id": "str | None",
        "encrypted_tg_file_id_nonce": "str | None",
        "checksum": "str",
        
        "encrypted_key": "str",
        "encrypted_key_nonce": "str",
        "key_version": "int",
        "encryption_algo": "str",
        
        "status": "UniversalStorageStatus",
        "media_type": "UniversalMediaType",
        "name": "str",
        "encrypted_description": "str | None",
        "encrypted_description_nonce": "str | None",
        
        "is_active": "bool",
        
        "created_at": "2024-01-15T10:30:45+03:00"
    }
}
```
**TTL:** навсегда


### Проданные универсальные товары по id владельца (SoldUniversal)
**Важно:** хранит только НЕ удалённые аккаунты (is_active == False)  
**Ключ:** `sold_universal_by_owner_id:{owner_id}:{language}`  
**Значение:** 
```json
[
    {
        "sold_universal_id": "int",
        "owner_id": "int",
        "universal_storage_id": "int",
        
        "name": "str",
        
        "sold_at": "2024-01-15T10:30:45+03:00"
    }
]
```
**TTL:** 6 часов

### Проданные универсальные товары по id аккаунта (SoldUniversal)
**Важно:** хранит только НЕ удалённые аккаунты (is_active == False)  
**Ключ:** `sold_universal:{sold_universal_id}:{language}`  
**Значение:** 
```json
{
    "sold_universal_id": "int",
    "owner_id": "int",
    "universal_storage_id": "int",
    
    "sold_at": "2024-01-15T10:30:45+03:00",
    
    "universal_storage": {
        "universal_storage_id": "int",
        "storage_uuid": "str",
        
        "file_path": "str | None",
        "original_filename": "str | None",
        "encrypted_tg_file_id": "str | None",
        "encrypted_tg_file_id_nonce": "str | None",
        "checksum": "str",
        
        "encrypted_key": "str",
        "encrypted_key_nonce": "str",
        "key_version": "int",
        "encryption_algo": "str",
        
        "status": "UniversalStorageStatus",
        "media_type": "UniversalMediaType",
        "name": "str",
        "encrypted_description": "str | None",
        "encrypted_description_nonce": "str | None",
        
        "is_active": "bool",
        
        "created_at": "2024-01-15T10:30:45+03:00"
    }
}
```
**TTL:** 6 часов


### Промокоды (PromoCodes)
**Важно:** хранит только действительные (is_valid == True)  
**Ключ:** `promo_code:{activation_code}`  
**Значение:** 
```json
{
    "promo_code_id": "int",
    "activation_code": "str",
    "min_order_amount": "int",
    
    "activated_counter": "int",             // количество активаций
    "amount": "int",
    "discount_percentage": "int | None",    // процент скидки (может быть Null)
    "number_of_activations": "int | None",  // разрешённое количество активаций (если нет, то может быть бесконечным)
    
    "start_at": "2024-01-15T10:30:45+03:00",
    "expire_at": "2024-01-15T10:30:45+03:00",
    "is_valid": "bool"
}
```
**TTL:** До окончания срока действия

### Список ваучеров (Vouchers)
**Важно:** хранит только действительные (is_valid == True), отфильтровано по дате создания `desc`   
**Ключ:** `voucher_by_user:{user_id}`  
**Значение:** 
```json
[
    {
        "voucher_id": "int",
        "creator_id": "int",
        "amount": "int",
        "activation_code": "str",
        "number_of_activations": "int | None",
        "is_valid": "bool"
    }
]
```
**TTL:** 10 часов

### Ваучеры (Vouchers)
**Важно:** хранит только действительные (is_valid == True)  
**Ключ:** `voucher:{activation_code}`  
**Значение:** 
```json
{
    "voucher_id": "int",
    "creator_id": "int",
    "is_created_admin": "bool",
    
    "activation_code": "str",
    "amount": "int",
    "activated_counter": "int",               // количество активаций
    "number_of_activations": "int | None",    // разрешённое количество активаций (если нет, то бесконечное)

    "start_at": "2024-01-15T10:30:45+03:00",
    "expire_at": "2024-01-15T10:30:45+03:00 | None", 
    "is_valid": "bool"
}
```

**TTL:** Навсегда

### Курс доллара
**Ключ:** `dollar_rate`  
**Значение:** `float`
**TTL:** Навсегда, обновляется раз в два часа (get_config().different.fetch_interval)

