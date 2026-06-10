import os
import json
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

# Подключение к Polygon Mainnet
w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))

# Адрес контракта и ABI берём из переменных окружения Railway
CONTRACT_ADDRESS = os.getenv('GRRR_CONTRACT_ADDRESS')
ADMIN_PRIVATE_KEY = os.getenv('ADMIN_PRIVATE_KEY')
ADMIN_ADDRESS = os.getenv('ADMIN_ADDRESS')

# Загружаем ABI из переменной окружения
CONTRACT_ABI = json.loads(os.getenv('GRRR_ABI'))

# Создаём объект контракта
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

def init_blockchain():
    """Вызывается при старте приложения (сейчас просто заглушка)"""
    pass

def is_ready():
    """Проверяет, что все данные для работы с блокчейном на месте"""
    return CONTRACT_ADDRESS is not None and ADMIN_PRIVATE_KEY is not None

def get_onchain_balance(address):
    """Возвращает реальный баланс токенов на кошельке"""
    return contract.functions.balanceOf(address).call()

def transfer_onchain(to_address, amount_wei):
    """Отправляет amount_wei токенов на указанный адрес с админского кошелька"""
    nonce = w3.eth.get_transaction_count(ADMIN_ADDRESS)
    txn = contract.functions.transfer(to_address, amount_wei).build_transaction({
        'chainId': 137,
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
    })
    signed = w3.eth.account.sign_transaction(txn, ADMIN_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    return w3.to_hex(tx_hash)
