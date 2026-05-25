import requests
import json
import time

print("🐻 Создаю токен $GRRR в блокчейне TON...")

# Используем публичный API TON
API_URL = "https://toncenter.com/api/v2"

# Данные токена
TOKEN_NAME = "GRRR"
TOKEN_SYMBOL = "GRRR"

# Сначала проверяем, работает ли API
try:
    response = requests.get(f"{API_URL}/getMasterchainInfo", timeout=10)
    if response.status_code == 200:
        print("✅ Подключено к TON API")
        data = response.json()
        print(f"📊 Блокчейн активен, блок: {data.get('result', {}).get('last', {}).get('seqno', 'N/A')}")
    else:
        print("❌ API недоступен")
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")

print()
print("=" * 60)
print("🎯 ПЛАН ДЕЙСТВИЙ:")
print("=" * 60)
print()
print("Для создания токена $GRRR в блокчейне TON нужно:")
print()
print("1. TON кошелёк (Tonkeeper, Tonhub, @wallet)")
print("2. 0.1 TON на газ (около 20 рублей)")
print()
print("=" * 60)
print("🚀 БЫСТРЫЙ СПОСОБ (без кода):")
print("=" * 60)
print()
print("Перейди на сайт: https://minter.ton.org")
print("Там можно создать токен за 2 минуты:")
print(f"  - Название: {TOKEN_NAME}")
print(f"  - Символ: {TOKEN_SYMBOL}")
print("  - Количество: 1 000 000 000")
print("  - Decimals: 9")
print()
print("=" * 60)
print("📋 АЛЬТЕРНАТИВА (через Telegram):")
print("=" * 60)
print()
print("1. Найди бота @mint_jetton_bot")
print("2. Отправь /start")
print("3. Введи данные выше")
print()
print("=" * 60)
print("💡 ПОСЛЕ СОЗДАНИЯ ТОКЕНА:")
print("=" * 60)
print()
print("Пришли мне адрес контракта, и я сразу:")
print("✅ Интегрирую $GRRR в BearGram")
print("✅ Настрою вывод токенов пользователями")
print("✅ Добавлю обмен 💎 ↔ $GRRR")
print()
print("🐻 $GRRR — ВАЛЮТА ХИЩНИКОВ! СКОРО В БЛОКЧЕЙНЕ!")