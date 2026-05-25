import requests

api_key = "sk-c48e974ce7f54472bee032b982fc0114"

try:
    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": "Привет, как дела?"}
            ],
            "temperature": 0.9,
            "max_tokens": 50
        },
        timeout=30
    )
    
    print("Статус:", response.status_code)
    print("Ответ:", response.json())
    
except Exception as e:
    print("Ошибка:", str(e))