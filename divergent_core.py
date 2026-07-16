import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
import random
import asyncio
import requests

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
            "dopamine": {"temperature": 1.0, "top_p": 0.95, "repetition_penalty": 1.0},
            "serotonin": {"temperature": 0.6, "top_p": 0.9, "repetition_penalty": 1.2},
            "acetylcholine": {"temperature": 0.7, "top_p": 0.9, "repetition_penalty": 1.1}
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
    def __init__(self):
        self.devices = {}
        self.mode_manager = NeurotransmitterMode()

    def register_device(self, name, control_url, method="POST"):
        self.devices[name] = {"url": control_url, "method": method}
        print(f"Устройство '{name}' подключено к Мозгу.")

    def execute_command(self, device_name, payload):
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
        print(f"\n[Пользователь]: {prompt}")
        
        if "режим берсерка" in prompt.lower():
            print(self.mode_manager.set_mode("dopamine"))
        elif "режим гармонии" in prompt.lower():
            print(self.mode_manager.set_mode("serotonin"))
        elif "режим учёбы" in prompt.lower():
            print(self.mode_manager.set_mode("acetylcholine"))

        if "включи свет" in prompt.lower():
            return self.execute_command("лампа", {"power": "on", "brightness": 100})
        elif "выключи кофеварку" in prompt.lower():
            return self.execute_command("кофеварка", {"power": "off"})
        elif "мне грустно" in prompt.lower():
            print("Мозг чувствует твою грусть. Активирую протокол 'Утешение'.")
            self.execute_command("лампа", {"color": "warm", "brightness": 50})
            self.execute_command("аудиосистема", {"play": "HZ", "volume": 40})
            print("Сообщение на твой телефон: 'Ты сильнее, чем думаешь. Я с тобой.'")
            return "Протокол 'Утешение' выполнен."
        
        return "Я понял тебя, Архитектор. Действую."

# ==========================================
# 5. ИНТЕРАКТИВНЫЙ РЕЖИМ (ТЕКСТОВОЕ ОКНО)
# ==========================================
if __name__ == "__main__":
    print("=== ДИВЕР КВАНТО АКТИВИРОВАН ===")
    brain = CentralBrain()

    brain.register_device("лампа", "http://192.168.1.100/api/light", "POST")
    brain.register_device("кофеварка", "http://192.168.1.101/api/coffee", "POST")
    brain.register_device("аудиосистема", "http://192.168.1.102/api/audio", "POST")

    print("Вводи команды, Архитектор. Для выхода напиши 'выход'.\n")

    while True:
        user_input = input("Ты: ")
        if user_input.lower() in ["выход", "exit", "quit"]:
            print("Дивер Кванто: До встречи, Архитектор.")
            break
        response = brain.process_user_command(user_input)
        print(f"Дивер Кванто: {response}")
