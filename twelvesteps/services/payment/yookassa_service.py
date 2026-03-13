import os
from typing import Dict, Any, Optional
from datetime import datetime

from yookassa import Configuration, Payment
from yookassa.domain.common import SecurityHelper
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.PaymentRepository import PaymentRepository

class YookassaService:
    def __init__(self):

        self.bot_nickname = os.getenv("TELEGRAM_BOT_NICKNAME", "mafioznikos_bot")
        self.shop_id      = os.getenv("YOOKASSA_SHOP_ID")
        self.secret_key   = os.getenv("YOOKASSA_SECRET_KEY")
        
        if self.shop_id and self.secret_key:
            Configuration.account_id = self.shop_id
            Configuration.secret_key = self.secret_key
        else:
            print("⚠️ YOOKASSA_SHOP_ID или YOOKASSA_SECRET_KEY не настроены!")

    async def create_payment(
        self,
        amount: float,
        description: str,
        user_id: int,
        return_url: str = f"https://t.me/{self.bot_nickname}",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Создаёт платёж в ЮKassa"""

        if not self.shop_id or not self.secret_key:
            raise ValueError("ЮKassa не настроена")

        if metadata is None:
            metadata = {}

        metadata["user_id"] = str(user_id)
        metadata["source"] = "twelvesteps_bot"

        try:

            payment = Payment.create({
                "amount": {
                    "value": f"{amount:.2f}",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url
                },
                "capture": True,
                "description": description[:128],
                "metadata": metadata
            }, idempotency_key=str(datetime.utcnow().timestamp()))

            return {
                "id": payment.id,
                "status": payment.status,
                "confirmation_url": payment.confirmation.confirmation_url,
                "amount": payment.amount.value,
                "description": payment.description
            }
        
        except Exception as e:
            print(f"[Yookassa] Create payment error: {e}")
            raise

    async def get_payment(self, payment_id: str) -> Dict:
        """Получить информацию о платеже"""

        payment = Payment.find_one(payment_id)

        return {
            "id": payment.id,
            "status": payment.status,
            "paid": payment.paid,
            "amount": payment.amount.value,
            "description": payment.description,
            "metadata": payment.metadata or {},
            "created_at": payment.created_at
        }

    def is_valid_webhook(self, body: bytes, signature: str) -> bool:
        """Проверка подписи webhook"""

        try:
            return SecurityHelper().check_signature(body, signature, self.secret_key)
        except:
            return False