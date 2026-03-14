import os
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from typing import Optional

from repositories.SubscriptionRepository import SubscriptionRepository
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentUserContext, get_current_user, get_db, get_db_session
from api.schemas import (
    YookassaPaymentCreateRequest,
    YookassaPaymentResponse,
    PaymentStatusResponse,
    YookassaWebhookRequest,
    SubscriptionStatusResponse
)

from services.payment.yookassa_service import YookassaService
from services.payment.cryptomus_service import CryptomusService

#
# Yookassa router - роутер для работы с ЮKassa
#

router = APIRouter(prefix="/payment/yookassa", tags=["Payments"])

service = YookassaService()

TELEGRAM_BOT_NICKNAME = os.getenv("TELEGRAM_BOT_NICKNAME", "mafioznikos_bot")

@router.post("/create", response_model=YookassaPaymentResponse)
async def create_yookassa_payment(
    payload: YookassaPaymentCreateRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Создать платёж (вызывается из бота)"""

    try:

        return_url = payload.return_url or f"https://t.me/{current_context.user.username or TELEGRAM_BOT_NICKNAME}"
        
        result = await service.create_payment(
            amount      = payload.amount,
            description = payload.description or f"Подписка на GPT-SELF — {payload.plan_type}",
            user_id     = current_context.user.id,
            return_url  = return_url,
            metadata    = {"plan_type": payload.plan_type}
        )

        return result
    
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status/{payment_id}", response_model=PaymentStatusResponse)
async def get_payment_status(
    payment_id: str,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Проверить статус платежа"""

    try:
        payment = await service.get_payment(payment_id)
        return PaymentStatusResponse(**payment)
    
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Payment not found")


@router.post("/webhook")
async def yookassa_webhook(
    request: Request,
    x_yookassa_signature: Optional[str] = Header(None, alias="X-Yookassa-Signature"),
    session: AsyncSession = Depends(get_db_session)
):
    """Webhook от ЮKassa — обработка успешного платежа"""
    body = await request.body()
    
    if not service.is_valid_webhook(body, x_yookassa_signature or ""):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        
        webhook_data = await request.json()
        
        if webhook_data.get("event") != "payment.succeeded":
            return {"status": "ignored"}   # нас интересуют только успешные платежи

        payment_obj = webhook_data.get("object", {})
        payment_id  = payment_obj.get("id")
        amount_str  = payment_obj.get("amount", {}).get("value")
        metadata    = payment_obj.get("metadata", {})
        
        user_id_str = metadata.get("user_id")
        plan_type   = metadata.get("plan_type", "monthly")  # monthly / yearly и т.д.

        if not user_id_str:
            print("[Webhook] Нет user_id в метаданных")
            return {"status": "error_no_user"}

        user_id = int(user_id_str)

        # Работа с подпиской
        from datetime import datetime, timedelta

        # Получаем сессию
        sub_repo = SubscriptionRepository(session)

        # Определяем длительность подписки
        if plan_type == "yearly":
            duration_days = 365
        elif plan_type == "3_months":
            duration_days = 90
        else:
            duration_days = 30   # monthly по умолчанию

        now     = datetime.utcnow()
        expires = now + timedelta(days=duration_days)

        # Пытаемся найти существующую подписку
        existing_sub = await sub_repo.get_by_user_id(user_id)

        # Если оплата прошла успешно, значит это premium, если нет значит это free
        plan_str = "premium" 

        if existing_sub:

            # Продлеваем существующую подписку
            existing_sub.status           = "active" # active, expired, cancelled
            existing_sub.plan             = plan_str
            existing_sub.expires_at       = expires
            existing_sub.payment_provider = "yookassa" # yookassa, cryptomus
            existing_sub.payment_id       = payment_id
            existing_sub.updated_at       = now

            print(f"[Webhook] Продлена подписка user={user_id}, до {expires}")

        else:

            # Создаём новую подписку
            await sub_repo.create_or_renew(
                user_id          = user_id,
                plan             = plan_str,
                duration_days    = duration_days,
                payment_provider = "yookassa",
                payment_id       = payment_id
            )

            print(f"[Webhook] Создана новая подписка user={user_id}, до {expires}")

        await session.commit()

        print(f"✅ Платёж {payment_id} ({amount_str} ₽) успешно обработан для пользователя {user_id}")

        return {"status": "success"}

    except Exception as e:

        print(f"[Webhook critical error] {e}")

        import traceback
        traceback.print_exc()

        return {"status": "error"}

#    
# Cryptomus router - роутер для работы с Cryptomus
#

cryptomus_router = APIRouter(prefix="/payment/cryptomus", tags=["Payments"])

service_cryptomus = CryptomusService()

@cryptomus_router.post("/create", response_model=CryptomusPaymentResponse)
async def create_cryptomus_payment(
    payload: CryptomusPaymentCreateRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Создать платёж через Cryptomus"""

    try:

        return_url = payload.return_url or f"https://t.me/{current_context.user.username or TELEGRAM_BOT_NICKNAME}"
        
        result = await service_cryptomus.create_payment(
            amount      = payload.amount,
            currency    = payload.currency,
            description = payload.description or f"Подписка на GPT-SELF — {payload.plan_type}",
            user_id     = current_context.user.id,
            return_url  = return_url,
            metadata    = {"plan_type": payload.plan_type}
        )

        return result
    
    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc))

@cryptomus_router.get("/status/{payment_id}")
async def get_cryptomus_payment_status(
    payment_id: str,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Проверить статус платежа"""

    try:

        payment = await service_cryptomus.get_payment(payment_id)

        return PaymentStatusResponse(**payment)
    
    except Exception as exc:

        raise HTTPException(status_code=404, detail="Payment not found")

@cryptomus_router.post("/webhook")
async def cryptomus_webhook(
    request: Request,
    sign: Optional[str] = Header(None, alias="Sign"),
    session: AsyncSession = Depends(get_db_session)
):
    """Webhook от Cryptomus — обработка успешного платежа"""

    body = await request.body()
    
    if not service_cryptomus.is_valid_webhook(body, sign or ""):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:

        webhook_data = await request.json()
        
        if webhook_data.get("status") != "paid":
            return {"status": "ignored"}

        payment_id = webhook_data.get("uuid")
        amount_str = webhook_data.get("amount")
        currency   = webhook_data.get("currency")
        metadata   = webhook_data.get("metadata", {})

        user_id_str = metadata.get("user_id")
        plan_type   = metadata.get("plan_type", "monthly")

        if not user_id_str:
            return {"status": "error_no_user"}

        user_id = int(user_id_str)

        from datetime import datetime, timedelta

        # Получаем сессию
        sub_repo = SubscriptionRepository(session)

        if plan_type == "yearly":
            duration_days = 365
        elif plan_type == "3_months":
            duration_days = 90
        else:
            duration_days = 30

        now     = datetime.utcnow()
        expires = now + timedelta(days=duration_days)

        existing_sub = await sub_repo.get_by_user_id(user_id)
        plan_str     = "premium"

        if existing_sub:

            existing_sub.status           = "active"
            existing_sub.plan             = plan_str
            existing_sub.expires_at       = expires
            existing_sub.payment_provider = "cryptomus"
            existing_sub.payment_id       = payment_id
            existing_sub.updated_at       = now

        else:

            await sub_repo.create_or_renew(
                user_id          = user_id,
                plan             = plan_str,
                duration_days    = duration_days,
                payment_provider = "cryptomus",
                payment_id       = payment_id
            )

        await session.commit()

        print(f"✅ Cryptomus payment {payment_id} ({amount_str} {currency}) processed for user {user_id}")

        return {"status": "success"}

    except Exception as e:

        print(f"[Cryptomus webhook error] {e}")
        return {"status": "error"}