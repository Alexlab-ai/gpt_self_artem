# Подключаем Yookassa
from api.payment import router as payment_router
app.include_router(payment_router)

# Подключаем Cryptomus-роутер
from api.payment import cryptomus_router
app.include_router(cryptomus_router)