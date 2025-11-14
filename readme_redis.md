## Хранение в Redis

Все значения которые хранятся с TTL навсегда, меняются в зависимости от их изменений


### 1. Настройки (Settings)
**Ключ:** `settings`  
**Значение:**  
``` json
{
    "support_username": int, 
    "maintenance_mode": bool, 
    "channel_for_logging_id": int,
    "channel_for_subscription_id": int,
    "shop_name": str,
    "channel_name": str,
    "linc_info_ref_system": str,
    "api_id": int,
    "api_hash": str,
    "FAQ": str,
}
```
**TTL:** Навсегда

### 2. Изображения для разделов (UiImages)
**Ключ:** `ui_image:{key}`  
**Значение:** 
``` json
{
    "key": str, 
    "file_path": str, 
    "show": bool,
    "updated_at": str,
}
```
**TTL:** Навсегда

### 3. Все типы оплаты (TypePayments)
**Ключ:** `all_types_payments:`  
**Важно:** список отсортирован по возрастанию поля index <br>
**Значение:**  
``` json
[
    {
        "type_payment_id": int, 
        "name_for_user": str,
        "name_for_admin": str,
        "is_active": bool,
        "commission": float,
        "index": int,
        "extra_data": dict,
    }
    .....
]
```
**TTL:** Навсегда

### 4. Тип оплаты по id (TypePayments)
**Ключ:** `type_payments:{type_payment_id}`  
**Значение:**  
``` json
{
    "type_payment_id": int, 
    "name_for_user": str,
    "name_for_admin": str,
    "is_active": bool,
    "commission": float,
    "index": int,
    "extra_data": dict,
}
```
**TTL:** Навсегда

### 5. Пользователь (Users)
**Ключ:** `user:{user_id}`  
**Значение:**  
``` json
{
    "user_id": int, 
    "username": str,
    "language": str,
    "unique_referral_code": str,
    "balance": int,
    "total_sum_replenishment": int,
    "total_sum_from_referrals": int,
    "created_at": datetime,
}
```
**TTL:** 6 часов

### 6. Пользователь (Users)
**Ключ:** `subscription_prompt:{user_id}`
**Значение:** `_` выступает в роли метки  
**TTL:** 15 дней

### 7. Уровни рефералов (ReferralLevels)
**Ключ:** `referral_levels`  
**Значение:**  
``` json
[
    {
        "referral_level_id": int, 
        "level": int, 
        "amount_of_achievement": int, 
        "percent": int
    }
    .....
]
```
**TTL:** Навсегда

### 8. Админы (Admins)
**Ключ:** `admin:{user_id}`   
**Значение:** `_` выступает в роли метки  
**TTL:** Навсегда

### 9. Забаненные аккаунты (BannedAccounts)
**Ключ:** `banned_account:{user_id}`  
**Значение:** `Причина бана`  
**TTL:** Навсегда

### 10. Тип продаваемых аккаунтов (TypeAccountServices)
**Ключ:** `types_account_service`   
**Значение:** 
``` json
[
    {
        "type_account_service_id": int ,
        "name": str
    }
    .....
]

```

### 11. Тип продаваемых аккаунтов (TypeAccountServices)
**Ключ:** `type_account_service:{type_account_service_id}`   
**Значение:** 
``` json
{
    "type_account_service_id": int ,
    "name": str
}
```
**TTL:** Навсегда

### 12. Список всех сервисов у продаваемых аккаунтов (AccountServices)
**Важно:** список отсортирован по возрастанию поля index  
**Ключ:** `account_services`   
**Значение:** 
``` json
[
    {
        "account_service_id": int ,
        "name": str,
        "index": int,
        "show": bool,
        "type_account_service_id": int
    }
    .....
]
```
**TTL:** Навсегда

### 13. Сервисы у продаваемых аккаунтов (AccountServices)
**Ключ:** `account_service:{account_service_id}`  
**Значение:** 
``` json
{
    "account_service_id": int ,
    "name": str,
    "index": int,
    "show": bool,
    "type_account_service_id": int
}
```
**TTL:** Навсегда

### 14. Категории аккаунтов по id сервиса (AccountCategories)
**Ключ:** `account_categories_by_service_id:{account_service_id}:{language}`  
**Значение:** 
``` json
[
    {
        "account_category_id": int,
        "account_service_id": int,
        "ui_image_key": str
        "parent_id": int,
        
        "name": str,
        "description": str,
        "index": int,
        "show": bool,
        "number_buttons_in_row": int, 
        
        "is_main": bool, 
        "is_accounts_storage": bool, 
        
        # только для тех кто хранит аккаунты 
        "price_one_account": int or None,
        "cost_price_one_account": int or None
        
        "quantity_product_account": int
    }
    .....
]
```
**TTL:** Навсегда

### 15. Категории аккаунтов по id категории(AccountCategories)
**Ключ:** `account_categories_by_category_id:{account_category_id}:{language}`  
**Значение:** 
``` json
{
    "account_category_id": int,
    "account_service_id": int,
    "ui_image_key": str
    "parent_id": int,
    
    "name": str,
    "description": str,
    "index": int,
    "show": bool,
    "number_buttons_in_row": int, 
    
    "is_main": bool, 
    "is_accounts_storage": bool, 
    
    # только для тех кто хранит аккаунты 
    "price_one_account": int,
    "cost_price_one_account": int
    
    "quantity_product_account": int
}
```
**TTL:** Навсегда


### 16. Товары Аккаунты по id категории (ProductAccounts)
**Ключ:** `product_accounts_by_category_id:{account_category_id}`  
**Значение:** 
``` json
[
    {
        "account_id": int,
        "type_account_service_id": int,
        "account_category_id": int,
        "account_storage_id": int,
        "created_at": datetime,
    }
    .....
]
```
**TTL:** Навсегда

### 17. Товары Аккаунты по id аккаунта (ProductAccounts)
**Ключ:** `product_accounts_by_account_id:{account_id}`  
**Значение:** 
``` json
{
    "account_id": int,
    "type_account_service_id": int,
    "account_category_id": int,
    "created_at": datetime,
     
    "account_storage": {
        "account_storage_id": int,
        "storage_uuid": str,
        
        "file_path": str,
        "checksum": str,
        "status": str,
        
        "encrypted_key": str,
        "encrypted_key_nonce": str,
        "key_version": int,
        "encryption_algo": str,
        
        "phone_number": str,
        "login_encrypted": str | None,
        "password_encrypted": str | None,
        
        "is_active": bool,
        "is_valid": bool,
        
        "added_at": datetime,
        "last_check_at": datetime
    }
}
```
**TTL:** Навсегда

### 18. Проданные аккаунты по id владельца (SoldAccounts)
**Важно:** хранит только НЕ удалённые аккаунты (is_deleted == False)  
**Ключ:** `sold_accounts_by_owner_id:{owner_id}:{language}`  
**Значение:** 
``` json
[
    {
        "sold_account_id": int,
        "owner_id": int,
        "type_account_service_id": int,
        
        "phone_number": str,
        "name": str,
        "description": str,
        
        "sold_at": datetime
        
    }
    .....
]
```
**TTL:** 6 часов

### 19. Проданные аккаунты по id аккаунта (SoldAccounts)
**Важно:** хранит только НЕ удалённые аккаунты (is_deleted == False)  
**Ключ:** `sold_accounts_by_accounts_id:{sold_account_id}:{language}`  
**Значение:** 
``` json
{
    "sold_account_id": int,
    "owner_id": int,
    "type_account_service_id": int,
    
    "name": str,
    "description": str,
    
    "sold_at": datetime,
    
    "account_storage": {
        "account_storage_id": int,
        "storage_uuid": str,
        
        "file_path": str,
        "checksum": str,
        "status": str,
        
        "encrypted_key": str,
        "encrypted_key_nonce": str,
        "key_version": int,
        "encryption_algo": str,
        
        "phone_number": str,
        "login_encrypted": str | None,
        "password_encrypted": str | None,
        
        "is_active": bool,
        "is_valid": bool,
        
        "added_at": datetime,
        "last_check_at": datetime
    }
}
```
**TTL:** 6 часов


### 20. Промокоды (PromoCodes)
**Важно:** хранит только действительные (is_valid == True)  
**Ключ:** `promo_code:{activation_code}`  
**Значение:** 
``` json
{
    "promo_code_id": int,
    "activation_code": str,
    "min_order_amount": int,
    
    "activated_counter": int, # количество активаций
    "amount": int,
    "discount_percentage": int or None, # процент скидки (может быть Null)
    "number_of_activations": int or None,# разрешённое количество активаций (если нет, то может быть бесконечным)
    
    "start_at": datetime,
    "expire_at": datetime,
    "is_valid": bool,
}
```
**TTL:** До окончания срока действия

### 21. Список ваучеров (Vouchers)
**Важно:** хранит только действительные (is_valid == True), отфильтровано по дате создания `desc`   
**Ключ:** `voucher_by_user:{user_id}`  
**Значение:** 
``` json
[
    {
        voucher_id: int
        creator_id: int
        amount: int
        activation_code: str
        number_of_activations: int
    }
    .....
]
```
**TTL:** 10 часов

### 22. Ваучеры (Vouchers)
**Важно:** хранит только действительные (is_valid == True)  
**Ключ:** `voucher:{activation_code}`  
**Значение:** 
``` json
{
    "voucher_id": int,
    "creator_id": int,
    "is_created_admin": bool,
    
    "activation_code": str,
    "amount": int,
    "activated_counter": int, # количество активаций
    "number_of_activations": int or None, # разрешённое количество активаций (если нет, то бесконечное)

    "start_at": datetime,
    "expire_at": datetime,
    "is_valid": bool,
}
```

**TTL:** Навсегда

### 22. Курс доллара
**Ключ:** `dollar_rate`  
**Значение:** `float`
**TTL:** Навсегда, обновляется раз в два часа (FETCH_INTERVAL)

