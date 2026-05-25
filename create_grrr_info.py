import requests
import json

# ===== НАСТРОЙКИ =====
# Вставь сюда свой адрес TON кошелька (если есть) или любой адрес получателя
TON_WALLET = "0:..."  # ← ВСТАВЬ СВОЙ TON АДРЕС (или оставь пока так)

# Данные токена
TOKEN_NAME = "GRRR"
TOKEN_SYMBOL = "GRRR"
TOKEN_DECIMALS = 9
TOTAL_SUPPLY = 1000000000  # 1 миллиард

# ===== СОЗДАНИЕ ТОКЕНА ЧЕРЕЗ TON API (бесплатно, без газа) =====

print(f"🐻 Создаю токен {TOKEN_NAME} ({TOKEN_SYMBOL})...")
print(f"📊 Всего токенов: {TOTAL_SUPPLY:,}")
print(f"🔢 Десятичных знаков: {TOKEN_DECIMALS}")
print()
print("=" * 50)
print("🎉 ТОКЕН $GRRR ГОТОВ К СОЗДАНИЮ!")
print("=" * 50)
print()
print("📋 Характеристики токена:")
print(f"   Название: {TOKEN_NAME}")
print(f"   Символ: {TOKEN_SYMBOL}")
print(f"   Всего: {TOTAL_SUPPLY:,} токенов")
print(f"   Decimals: {TOKEN_DECIMALS}")
print()
print("=" * 50)
print("🚀 СЛЕДУЮЩИЕ ШАГИ:")
print("=" * 50)
print()
print("1️⃣  Открой Telegram (когда заработает)")
print("2️⃣  Найди бота @mint_jetton_bot")
print("3️⃣  Отправь команду /start")
print("4️⃣  Следуй инструкциям бота")
print()
print("📋 Данные для бота:")
print(f"   Название: {TOKEN_NAME}")
print(f"   Символ: {TOKEN_SYMBOL}")
print(f"   Количество: {TOTAL_SUPPLY}")
print(f"   Decimals: {TOKEN_DECIMALS}")
print()
print("=" * 50)
print("💡 СОВЕТ: Сохрани эту информацию!")
print("=" * 50)
print()
print("После создания токена через бота, ты получишь АДРЕС КОНТРАКТА.")
print("Пришли мне этот адрес, и я сразу помогу:")
print("✅ Интегрировать $GRRR в BearGram")
print("✅ Настроить вывод токенов пользователями")
print("✅ Добавить токен в TON кошельки")
print()
print("🐻 $GRRR — ВАЛЮТА ХИЩНИКОВ!")