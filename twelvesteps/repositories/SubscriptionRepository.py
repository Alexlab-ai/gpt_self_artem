from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Subscription

class SubscriptionRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_id(self, user_id: int) -> Optional[Subscription]:

        stmt   = select(Subscription).where(Subscription.user_id == user_id)
        result = await self.session.execute(stmt)

        return result.scalars().first()

    async def create_or_renew(
        self,
        user_id: int,
        plan: str = "premium",
        duration_days: int = 30,
        payment_provider: Optional[str] = None,
        payment_id: Optional[str] = None,
        is_trial: bool = False
    ) -> Subscription:
        """Создать подписку или продлить существующую"""

        sub = await self.get_by_user_id(user_id)
        now = datetime.utcnow()

        if is_trial:

            expires = now + timedelta(days=7)
            status = "trial"

        else:
            
            expires = now + timedelta(days=duration_days)
            status = "active"

        if sub:

            sub.status           = status
            sub.plan             = plan
            sub.started_at       = now
            sub.expires_at       = expires
            sub.payment_provider = payment_provider
            sub.payment_id       = payment_id
            sub.updated_at       = now
            
            if is_trial:
                sub.trial_ends_at = expires

        else:

            sub = Subscription(
                user_id          = user_id,
                status           = status,
                plan             = plan,
                started_at       = now,
                expires_at       = expires,
                payment_provider = payment_provider,
                payment_id       = payment_id
            )

            if is_trial:
                sub.trial_ends_at = expires
            
            self.session.add(sub)

        await self.session.flush()

        return sub

    async def is_premium_active(self, user_id: int) -> bool:
        """Проверка активной подписки (включая trial)"""

        sub = await self.get_by_user_id(user_id)

        if not sub:
            return False
        
        if sub.status not in ["active", "trial"]:
            return False
        
        if sub.expires_at and sub.expires_at < datetime.utcnow():
            return False
        
        if sub.trial_ends_at and sub.trial_ends_at < datetime.utcnow():
            return False
        
        return True