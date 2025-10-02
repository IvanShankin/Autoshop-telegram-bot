## Хранение в Redis

Все значения которые хранятся с TTL навсегда, меняются в зависимости от их изменений


### 1. Настройки (Settings)
**Ключ:** `settings`  
**Значение:**  
``` json
{
    "support_username": int, 
    "hash_token_logger_bot": str,
    "channel_for_logging_id": int,
    "channel_for_subscription_id": int,
    "FAQ": str,
}
```
**TTL:** Навсегда

### 2. Все типы оплаты (TypePayments)
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

### 3. Тип оплаты по id (TypePayments)
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

### 4. Пользователь (Users)
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

### 5 Уровни рефералов (ReferralLevels)
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

### 6. Админы (Admins)
**Ключ:** `admin:{user_id}` <br>
**Значение:** `_` выступает в роли метки <br>
**TTL:** Навсегда

### 7. Забаненные аккаунты (BannedAccounts)
**Ключ:** `banned_account:{user_id}` <br>
**Значение:** `_` выступает в роли метки <br>
**TTL:** Навсегда

### 8. Тип продаваемых аккаунтов (TypeAccountServices)
**Ключ:** `types_account_service` <br>
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

### 9. Тип продаваемых аккаунтов (TypeAccountServices)
**Ключ:** `type_account_service:{type_account_service_id}` <br>
**Значение:** 
``` json
{
    "type_account_service_id": int ,
    "name": str
}
```
**TTL:** Навсегда

### 10. Список всех сервисов у продаваемых аккаунтов (AccountServices)
**Важно:** список отсортирован по возрастанию поля index <br>
**Ключ:** `account_services` <br>
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

### 11. Сервисы у продаваемых аккаунтов (AccountServices)
**Ключ:** `account_service:{account_service_id}` <br>
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

### 12. Категории аккаунтов по id сервиса (AccountCategories)
**Ключ:** `account_categories_by_service_id:{account_service_id}:{language}` <br>
**Значение:** 
``` json
[
    {
        "account_category_id": int ,
        "account_service_id": int ,
        "parent_id": int ,
        "name": str,
        "description": str,
        "index": int,
        "show": bool,
        "is_main": bool, 
        "is_accounts_storage": bool, 
        
        # только для тех кто хранит аккаунты 
        "price_one_account": int or None,
        "cost_price_one_account": int or None
    }
    .....
]
```
**TTL:** Навсегда

### 13. Категории аккаунтов по id категории(AccountCategories)
**Ключ:** `account_categories_by_category_id:{account_category_id}:{language}` <br>
**Значение:** 
``` json
{
    "account_category_id": int,
    "account_service_id": int,
    "parent_id": int,
    "name": str,
    "description": str,
    "index": int,
    "show": bool,
    "is_main": bool, 
    "is_accounts_storage": bool, 
    "price_one_account": int,
    "cost_price_one_account": int
}
```
**TTL:** Навсегда


### 14. Товары Аккаунты по id категории (ProductAccounts)
**Ключ:** `product_accounts_by_category_id:{account_category_id}` <br>
**Значение:** 
``` json
[
    {
        "account_id": int,
        "type_account_service_id": int,
        "account_category_id": int,
        "created_at": datatime,
        
        "hash_login": str or None,
        "hash_password": str or None,
    }
    .....
]
```
**TTL:** Навсегда

### 15. Товары Аккаунты по id аккаунта (ProductAccounts)
**Ключ:** `product_accounts_by_account_id:{account_id}` <br>
**Значение:** 
``` json
{
    "account_id": int,
    "type_account_service_id": int,
    "account_category_id": int,
    "created_at": datatime,
    
    "hash_login": str or None,
    "hash_password": str or None,
}
```
**TTL:** Навсегда

### 16. Проданные аккаунты по id владельца (SoldAccounts)
**Важно:** хранит только НЕ удалённые аккаунты (is_deleted == False) <br>
**Ключ:** `sold_accounts_by_owner_id:{owner_id}:{language}` <br>
**Значение:** 
``` json
[
    {
        "sold_account_id": int,
        "owner_id": int,
        "type_account_service_id": int,
        
        "category_name": str,
        "service_name": str,
        "name": str,
        "description": str,
        
        "is_valid": bool,
        "is_deleted": bool,
        
        # Специфичные поля (могут быть NULL)
        "hash_login": str or None,
        "hash_password": str or None,
        
    }
    .....
]
```
**TTL:** 6 часов

### 17. Проданные аккаунты по id аккаунта (SoldAccounts)
**Важно:** хранит только НЕ удалённые аккаунты (is_deleted == False) <br>
**Ключ:** `sold_accounts_by_accounts_id:{sold_account_id}:{language}` <br>
**Значение:** 
``` json
{
    "sold_account_id": int,
    "owner_id": int,
    "type_account_service_id": int,
    
    "category_name": str,
    "service_name": str,
    "type_name": str,
    
    "is_valid": bool,
    "is_deleted": bool,
    
    # Специфичные поля (могут быть None)
    "hash_login": str or None,
    "hash_password": str or None,
    
}
```
**TTL:** 6 часов


### 18. Промокоды (PromoCodes)
**Важно:** хранит только действительные (is_valid == True)<br>
**Ключ:** `promo_code:{activation_code}` <br>
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


### 19. Ваучеры (Vouchers)
**Важно:** хранит только действительные (is_valid == True)<br>
**Ключ:** `voucher:{activation_code}` <br>
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
