import os
import hashlib
import hmac
from typing import Dict, Any, Optional
from datetime import datetime
import requests

from sqlalchemy.ext.asyncio import AsyncSession
from repositories.PaymentRepository import PaymentRepository

class CryptomusService:

    def __init__(self):

        self.bot_nickname = os.getenv("TELEGRAM_BOT_NICKNAME", "mafioznikos_bot")
        self.api_key      = os.getenv("CRYPTOMUS_API_KEY")
        self.merchant_id  = os.getenv("CRYPTOMUS_MERCHANT_ID")
        self.base_url     = "https://api.cryptomus.com/v1"

        if not self.api_key or not self.merchant_id:
            print("⚠️ CRYPTOMUS_API_KEY или CRYPTOMUS_MERCHANT_ID не настроены!")

    def _generate_sign(self, data: dict) -> str:
        """Генерация подписи Cryptomus (сортировка + конкатенация)"""

        data_str = ''.join(f"{k}{v}" for k, v in sorted(data.items()))
        sign = hmac.new(
            self.api_key.encode(),
            data_str.encode(),
            hashlib.sha256
        ).hexdigest()

        return sign

    async def create_payment(
        self,
        amount: float,
        currency: str,
        description: str,
        user_id: int,
        return_url: str = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        
        if not self.api_key or not self.merchant_id:
            raise ValueError("Cryptomus не настроен")

        if metadata is None:
            metadata = {}

        metadata["user_id"] = str(user_id)
        metadata["source"]  = "twelvesteps_bot"

        payload = {
            "amount": str(amount),
            "currency": currency,
            "order_id": f"order_{user_id}_{int(datetime.utcnow().timestamp())}",
            "description": description[:128],
            "url_return": return_url or f"https://t.me/{self.bot_nickname}",
            "url_success": return_url or f"https://t.me/{self.bot_nickname}",
            "metadata": metadata
        }

        sign = self._generate_sign(payload)

        headers = {
            "merchant": self.merchant_id,
            "sign": sign,
            "Content-Type": "application/json"
        }

        try:

            response = requests.post(
                f"{self.base_url}/payment",
                json=payload,
                headers=headers
            )

            response.raise_for_status()
            data = response.json()

            if data.get("result"):

                result = data["result"]

                return {
                    "id": result["uuid"],
                    "status": result["status"],
                    "payment_url": result["url"],
                    "amount": result["amount"],
                    "currency": result["currency"]
                }
            
            else:

                raise ValueError(f"Cryptomus error: {data.get('message')}")

        except Exception as e:
            print(f"[Cryptomus] Create payment error: {e}")
            raise

    async def get_payment(self, payment_id: str) -> Dict:
        """Получить статус платежа"""

        payload = {"uuid": payment_id}
        sign    = self._generate_sign(payload)

        headers = {
            "merchant": self.merchant_id,
            "sign": sign,
            "Content-Type": "application/json"
        }

        response = requests.post(
            f"{self.base_url}/payment/info",
            json    = payload,
            headers = headers
        )
        
        data   = response.json()
        result = data.get("result", {})

        return {
            "id": result.get("uuid"),
            "status": result.get("status"),
            "paid": result.get("status") == "paid",
            "amount": result.get("amount"),
            "currency": result.get("currency"),
            "metadata": result.get("metadata", {})
        }

    def is_valid_webhook(self, body: bytes, signature: str) -> bool:
        """Проверка подписи webhook"""

        try:

            sign = hmac.new(
                self.api_key.encode(),
                body,
                hashlib.sha256
            ).hexdigest()

            return sign == signature
        
        except:
            return False