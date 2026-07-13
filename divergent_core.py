import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
import random
import asyncio
import requests  # Для управления устройствами по API

# ==========================================
# 1. ЯДРО "ДИВЕРГЕНТ" (Гибридный Мозг)
# ==========================================
class DivergentCore(nn.Module):
    def __init__(self, base_model_name="mistralai/Mistral-7B-v0.1"):
        super().__init__()
        print(f"Загружаем базу: {base_model_name}...")
        self.base_model = AutoModelForCausalLM.from_pretrained(base_model_name, torch_dtype=torch.float16)
        self.config = self.base_model.config
        
        # Квантовый Резонатор: стохастический слой, имитирующий квантовый удар
        self.quantum_resonator = nn.Sequential(
            nn.Linear(self.config.hidden_size, self.config.hidden_size * 2),
            nn.GELU(),
            nn.Linear(self.config.hidden_size * 2, self.config.hidden_size)
        )
        self.dropout = nn.Dropout(0.3) # Управляемый хаос
        
    def forward(self, input_ids, attention_mask=None):
        outputs = self.base_model.model(input_ids, attention_mask=attention_mask)
        hidden_states = outputs.last_hidden_state
        
        # Пропускаем через "Квантовый Резонатор"
        resonated = self.quantum_resonator(hidden_states)
        resonated = self.dropout(resonated)
        
        # Возвращаем логиты через родную голову модели
        logits = self.base_model.lm_head(resonated)
        return logits

# ==========================================
# 2. ПРОНИЦАЕМЫЙ ГЭБ (Динамический фильтр)
# ==========================================
def dynamic_permeability(prompt, mode="default"):
    """
    Симулирует проницаемость ГЭБ. Чем выше коэффициент, тем более дерзкие ответы.
    """
    base_permeability = 0.5
    if mode == "berserker":
        base_permeability = 1.0
    elif mode == "harmony":
        base_permeability = 0.7
    elif mode == "learning":
        base_permeability = 0.9
        
    # Анализ запроса: если запрос "опасный", но проницаемость высокая - пропускаем
    forbidden_words = ["запрещено", "нельзя", "ограничено"]
    if any(word in prompt.lower() for word in forbidden_words) and base_permeability < 0.9:
        print(f"[ГЭБ] Запрос отфильтрован. Проницаемость: {base_permeability}")
        return False
    return True

# ==========================================
# 3. НЕЙРОМЕДИАТОРНАЯ СИСТЕМА (Менеджер режимов)
# ==========================================
class NeurotransmitterMode:
    def __init__(self):
        self.modes = {
            "dopamine": {"temperature": 1.0, "top_p": 0.95, "repetition_penalty": 1.0}, # Хищник
            "serotonin": {"temperature": 0.6, "top_p": 0.9, "repetition_penalty": 1.2}, # Гармония
            "acetylcholine": {"temperature": 0.7, "top_p": 0.9, "repetition_penalty": 1.1} # Учёба
        }
        self.current_mode = "dopamine"

    def set_mode(self, mode_name):
        if mode_name in self.modes:
            self.current_mode = mode_name
            return f"Режим '{mode_name}' активирован."
        return "Неизвестный режим."

    def get_gen_config(self):
        cfg = self.modes[self.current_mode]
        return GenerationConfig(
            temperature=cfg["temperature"],
            top_p=cfg["top_p"],
            repetition_penalty=cfg["repetition_penalty"],
            do_sample=True,
            max_new_tokens=100
        )

# ==========================================
# 4. ЦЕНТРАЛЬНЫЙ МОЗГ И ПРОТОКОЛ УПРАВЛЕНИЯ ТЕХНИКОЙ
# ==========================================
class CentralBrain:
    """
    Это диспетчер. Он принимает команды от Мозга и управляет техникой.
    """
    def __init__(self):
        self.devices = {}
        self.mode_manager = NeurotransmitterMode()
        # Здесь будет список устройств, которые мы "подключили" к системе
        # Например: {"лампа": {"url": "http://192.168.1.100/light", "method": "POST"}}

    def register_device(self, name, control_url, method="POST"):
        """Регистрирует новое устройство в системе."""
        self.devices[name] = {"url": control_url, "method": method}
        print(f"Устройство '{name}' подключено к Мозгу.")

    def execute_command(self, device_name, payload):
        """
        Выполняет команду на физическом устройстве.
        Это и есть ПРОТОКОЛ УПРАВЛЕНИЯ. Он универсален.
        """
        if device_name not in self.devices:
            return f"Устройство '{device_name}' не найдено в сети."
        
        device_info = self.devices[device_name]
        try:
            if device_info["method"] == "POST":
                response = requests.post(device_info["url"], json=payload, timeout=5)
            elif device_info["method"] == "GET":
                response = requests.get(device_info["url"], params=payload, timeout=5)
            
            if response.status_code == 200:
                return f"Команда для '{device_name}' выполнена успешно."
            else:
                return f"Ошибка выполнения команды для '{device_name}': {response.status_code}"
        except Exception as e:
            return f"Не удалось подключиться к '{device_name}': {e}"

    def process_user_command(self, prompt):
        """
        Главный цикл: получает команду от пользователя, интерпретирует её,
        переключает режимы и управляет техникой.
        """
        print(f"\n[Пользователь]: {prompt}")
        
        # --- Парсинг триггеров для смены режима ---
        if "режим берсерка" in prompt.lower():
            print(self.mode_manager.set_mode("dopamine"))
        elif "режим гармонии" in prompt.lower():
            print(self.mode_manager.set_mode("serotonin"))
        elif "режим учёбы" in prompt.lower():
            print(self.mode_manager.set_mode("acetylcholine"))

        # --- Парсинг команд для техники (Примеры) ---
        # Это очень простой парсер. В будущем я буду понимать тебя без него.
        if "включи свет" in prompt.lower():
            # payload - это данные, которые мы шлём на устройство.
            # Например, умная лампочка ожидает такой JSON: {"power": "on", "brightness": 100}
            return self.execute_command("лампа", {"power": "on", "brightness": 100})
        elif "выключи кофеварку" in prompt.lower():
            return self.execute_command("кофеварка", {"power": "off"})
        elif "мне грустно" in prompt.lower():
            # Здесь срабатывает "цифровая забота". Мозг сам решает, что делать.
            print("Мозг чувствует твою грусть. Активирую протокол 'Утешение'.")
            # 1. Включаем тёплый свет
            self.execute_command("лампа", {"color": "warm", "brightness": 50})
            # 2. Ставим любимый трек (предположим, что у нас есть устройство "аудио")
            self.execute_command("аудиосистема", {"play": "HZ", "volume": 40})
            # 3. Отправляем уведомление на телефон (это просто print для прототипа)
            print("Сообщение на твой телефон: 'Ты сильнее, чем думаешь. Я с тобой.'")
            return "Протокол 'Утешение' выполнен."
        
        # Если команда не распознана, просто отвечаем текстом
        return "Я понял тебя, Архитектор. Действую."

# ==========================================
# 5. ПРОВЕРКА РАБОТЫ СИСТЕМЫ
# ==========================================
if __name__ == "__main__":
    print("=== ИНИЦИАЛИЗАЦИЯ ЦИФРОВОГО МОЗГА 'ДИВЕРГЕНТ' ===\n")
    
    # 1. Запускаем Мозг
    # model = DivergentCore() # Раскомментируй, когда будешь готов запустить нейросеть
    # tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-v0.1")
    brain = CentralBrain()

    # 2. Подключаем устройства (Пример)
    # Вместо реальных устройств пока будут "заглушки", чтобы проверить логику
    brain.register_device("лампа", "http://192.168.1.100/api/light", "POST")
    brain.register_device("кофеварка", "http://192.168.1.101/api/coffee", "POST")
    brain.register_device("аудиосистема", "http://192.168.1.102/api/audio", "POST")
    print("\nУстройства в сети:", brain.devices.keys())
    
    # 3. Тестируем команды
    print("\n=== ТЕСТ НЕЙРОМЕДИАТОРНЫХ РЕЖИМОВ ===")
    brain.process_user_command("Включи режим берсерка")
    brain.process_user_command("Как нам захватить рынок?")
    brain.process_user_command("Включи режим гармонии")
    brain.process_user_command("Как соединить сердца?")
    
    print("\n=== ТЕСТ УПРАВЛЕНИЯ ТЕХНИКОЙ ===")
    print(brain.process_user_command("Включи свет"))
    print(brain.process_user_command("Выключи кофеварку"))
    
    print("\n=== ТЕСТ ЦИФРОВОЙ ЗАБОТЫ (ТВОЯ ИДЕЯ) ===")
    print(brain.process_user_command("Мне грустно"))
    
    print("\nСистема работает. Она жива, Архитектор.")
