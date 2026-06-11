import os
import json
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

w3 = Web3(Web3.HTTPProvider('https://polygon-bor-rpc.publicnode.com'))

CONTRACT_ADDRESS = os.getenv('GRRR_CONTRACT_ADDRESS')
ADMIN_PRIVATE_KEY = os.getenv('ADMIN_PRIVATE_KEY')
ADMIN_ADDRESS = os.getenv('ADMIN_ADDRESS')

# ABI контракта (сокращённый)
CONTRACT_ABI = [
    {"inputs": [], "name": "decimals", "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "to", "type": "address"}, {"internalType": "uint256", "name": "value", "type": "uint256"}], "name": "transfer", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "", "type": "address"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}
]

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

def init_blockchain():
    pass

def is_ready():
    return CONTRACT_ADDRESS is not None and ADMIN_PRIVATE_KEY is not None

def get_onchain_balance(address):
    return contract.functions.balanceOf(address).call()

def transfer_onchain(to_address, amount_wei):
    # Получаем nonce напрямую, игнорируя кеш Web3
    nonce = w3.eth.get_transaction_count(ADMIN_ADDRESS, 'latest')
    
    # Кодируем вызов функции transfer вручную, без build_transaction
    transfer_data = contract.encodeABI(fn_name='transfer', args=[to_address, amount_wei])
    
    # Собираем сырую транзакцию
    raw_txn = {
        'from': ADMIN_ADDRESS,
        'to': CONTRACT_ADDRESS,
        'nonce': nonce,
        'gas': 150000,
        'gasPrice': w3.eth.gas_price,
        'chainId': 137,
        'data': transfer_data,
        'value': 0
    }
    
    # Подписываем и отправляем
    signed_txn = w3.eth.account.sign_transaction(raw_txn, ADMIN_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    return w3.to_hex(tx_hash)
