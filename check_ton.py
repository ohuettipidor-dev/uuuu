import requests
import json
import time

print("🐻 Создаю токен $GRRR через публичный TON API...")
print()

# Данные токена
TOKEN_NAME = "GRRR"
TOKEN_SYMBOL = "GRRR"
TOTAL_SUPPLY = 1000000000
DECIMALS = 9

# Публичный API TON (testnet)
API_URL = "https://testnet.toncenter.com/api/v2"

print("=" * 60)
print("🎯 ШАГ 1: Проверка подключения к TON Testnet")
print("=" * 60)

try:
    response = requests.get(f"{API_URL}/getMasterchainInfo", timeout=10)
    if response.status_code == 200:
        data = response.json()
        block = data.get('result', {}).get('last', {}).get('seqno', 'N/A')
        print(f"✅ Подключено! Текущий блок: {block}")
    else:
        print(f"❌ Ошибка API: {response.status_code}")
except Exception as e:
    print(f"❌ Не удалось подключиться: {e}")

print()
print("=" * 60)
print("📋 ДАННЫЕ ТОКЕНА $GRRR")
print("=" * 60)
print(f"""
Название: {TOKEN_NAME}
Символ: {TOKEN_SYMBOL}
Всего токенов: {TOTAL_SUPPLY:,}
Десятичных знаков: {DECIMALS}

Сеть: TON Testnet (бесплатно)
""")

print("=" * 60)
print("🚀 ЧТО ДЕЛАТЬ ДАЛЬШЕ:")
print("=" * 60)
print("""
1. Скачай Tonkeeper на телефон (уже скачан)
2. В настройках Tonkeeper включи Testnet
   (Если нет такой опции — используй @wallet в Telegram)
3. Получи адрес своего тестового кошелька
4. Пришли мне этот адрес

Я создам смарт-контракт и отправлю его в тестовую сеть.
Твой токен $GRRR появится в блокчейне TON Testnet!
""")

print("🐻 $GRRR — ВАЛЮТА ХИЩНИКОВ! СКОРО В БЛОКЧЕЙНЕ!")
print()
print("💡 Адрес твоего тестового кошелька можно найти в Tonkeeper:")
print("   Нажми 'Receive' → скопируй адрес (начинается с EQ...)")