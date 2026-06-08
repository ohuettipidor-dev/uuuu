# blockchain.py (заглушка)
import os

# -------------------- ВРЕМЕННО (до деплоя контракта) --------------------
# После деплоя ты заменишь этот блок на реальный код с Web3 и контрактом.

GRRR_CONTRACT_ADDRESS = None   # будет установлен после деплоя
GRRR_ABI = None                # будет загружен из переменных окружения или файла
ADMIN_PRIVATE_KEY = None
ADMIN_ADDRESS = None

def init_blockchain():
    """Вызывается после того, как переменные окружения установлены (после деплоя)"""
    global GRRR_CONTRACT_ADDRESS, GRRR_ABI, ADMIN_PRIVATE_KEY, ADMIN_ADDRESS
    GRRR_CONTRACT_ADDRESS = os.getenv('GRRR_CONTRACT_ADDRESS')
    ADMIN_PRIVATE_KEY = os.getenv('ADMIN_PRIVATE_KEY')
    ADMIN_ADDRESS = os.getenv('ADMIN_ADDRESS')
    # Здесь позже будет загрузка ABI и создание контракта через web3
    # contract = w3.eth.contract(address=GRRR_CONTRACT_ADDRESS, abi=GRRR_ABI)

def is_ready():
    return GRRR_CONTRACT_ADDRESS is not None and ADMIN_PRIVATE_KEY is not None

def get_onchain_balance(address):
    """Возвращает ончейн-баланс (пока заглушка)"""
    return 0  # будет запрос к контракту

def transfer_onchain(to_address, amount_wei):
    """Отправляет токены (пока заглушка, которая выбрасывает исключение)"""
    raise NotImplementedError("Блокчейн ещё не подключён. Ожидайте деплоя контракта.")
