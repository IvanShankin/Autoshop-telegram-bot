## Хранение в Redis

все значения которые хранятся с TTL навсегда, меняются в зависимости от их исзменений

### 1. Пользователь (Users)
**Ключ:** `user:{user_id}`  
**Значение:**  
```json
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

### 1.1 Уровни рефералов (ReferralLevels)
**Ключ:** `referral_levels`  
**Значение:**  
```json
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

### 2. Админы (Admins)
**Ключ:** `admin:{user_id}` <br>
**Значение:** `_` выступает в роли метки <br>
**TTL:** Навсегда

### 3. Забаненные аккаунты (BannedAccounts)
**Ключ:** `banned_account:{user_id}` <br>
**Значение:** `_` выступает в роли метки <br>
**TTL:** Навсегда

### 4. Тип продоваемых аккаунтов (TypeAccountServices)
**Ключ:** `type_account_service:{name}` <br>
**Значение:** 
``` json
{
    "type_account_service_id": int ,
    "name": str
}
```
**TTL:** Навсегда


### 5. Сервисы у продоваемых аккаунтов (AccountServices)
**Ключ:** `account_service:{type_account_service_id}` <br>
**Значение:** 
``` json
{
    "account_service_id": int ,
    "name": str,
    "type_account_service_id": int
}
```
**TTL:** Навсегда

### 6. Категории аккаунтов по id сервиса (AccountCategories)
**Ключ:** `account_categories_by_service_id:{account_service_id}` <br>
**Значение:** 
``` json
[
    {
        "account_category_id": int ,
        "account_service_id": int ,
        "parent_id": int ,
        "name": str,
        "description": str,
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

### 7. Категории аккаунтов по id категории(AccountCategories)
**Ключ:** `account_categories_by_category_id:{account_category_id}` <br>
**Значение:** 
``` json
{
    "account_category_id": int,
    "account_service_id": int,
    "parent_id": int,
    "name": str,
    "description": str,
    "is_main": bool, 
    "is_accounts_storage": bool, 
    "price_one_account": int,
    "cost_price_one_account": int
}
```
**TTL:** Навсегда


### 8. Товары Аккаунты по id категории (ProductAccounts)
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

### 9. Товары Аккаунты по id аккаунта (ProductAccounts)
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

### 10. Проданные аккаунты по id владельца (SoldAccounts)
**Важно:** хранит только НЕ удалённые аккаунты (is_deleted == False) <br>
**Ключ:** `sold_accounts_by_owner_id:{owner_id}` <br>
**Значение:** 
``` json
[
    {
        "sold_account_id": int,
        "owner_id": int,
        "type_account_service_id": int,
        
        "category_name": str,
        "service_name": str,
        "type_name": str,
        
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

### 11. Проданные аккаунты по id аккаунта (SoldAccounts)
**Важно:** хранит только НЕ удалённые аккаунты (is_deleted == False) <br>
**Ключ:** `sold_accounts_by_accounts_id:{sold_account_id}` <br>
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


### 12. Промокоды (PromoCodes)
**Важно:** хранит только действительные (is_valid == True)<br>
**Ключ:** `promo_code:{activation_code}` <br>
**Значение:** 
``` json
{
    "promo_code_id": int,
    "activation_code": str,
    "min_order_amount": int,
    
    "amount": int,
    "activated_counter": int, # количество активаций
    "number_of_activations": int or None,# разрешённое количество активаций (если нет, то может быть бесконечным)
    "discount_percentage": int or None, # процент скидки (может быть Null)
    
    "start_at": datetime,
    "expire_at": datetime,
    "is_valid": bool,
}
```
**TTL:** До окончания срока действия


### 13. Ваучеры (Vouchers)
**Важно:** хранит только действительные (is_valid == True)<br>
**Ключ:** `vouchers:{activation_code}` <br>
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
**TTL:** Бесконечно
