from typing import Optional, Dict, Any

from pydantic import BaseModel


class UpdateSettingsDTO(BaseModel):
    maintenance_mode: Optional[bool] = None
    support_username: Optional[str] = None
    channel_for_logging_id: Optional[int] = None
    channel_for_subscription_id: Optional[int] = None
    channel_for_subscription_url: Optional[str] = None
    shop_name: Optional[str] = None
    channel_name: Optional[str] = None
    FAQ: Optional[str] = None


class UpdateFileDTO(BaseModel):
    file_path: Optional[str] = None
    file_tg_id: Optional[str] = None


class UpdateStickerDTO(BaseModel):
    file_id: Optional[str] = None
    show: Optional[bool] = None


class UpdateUiImageDTO(BaseModel):
    file_name: Optional[str] = None
    show: Optional[bool] = None
    file_id: Optional[str] = None


class UpdateTypePaymentDTO(BaseModel):
    name_for_user: Optional[str] = None
    is_active: Optional[bool] = None
    commission: Optional[float] = None
    index: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = None
