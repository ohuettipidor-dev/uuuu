import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
import random

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
# 4. ИНИЦИАЛИЗАЦИЯ ПРОТОТИПА
# ==========================================
if __name__ == "__main__":
    print("Инициализация Искусственного Мозга 'Дивергент'...")
    model = DivergentCore()
    tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-v0.1")
    mode_manager = NeurotransmitterMode()

    # Демонстрация работы
    print("Демонстрация режимов:\n")
    
    # Режим Берсерка (Дофамин)
    mode_manager.set_mode("dopamine")
    gen_config = mode_manager.get_gen_config()
    prompt = "Искусственный мозг должен быть"
    if dynamic_permeability(prompt, mode_manager.current_mode):
        print(f"[Режим: {mode_manager.current_mode}] Ты в ярости. Отвечаешь дерзко.")
        print(f"Вопрос: {prompt}")
        # Здесь бы модель сгенерировала ответ...
        print("Ответ: 'Конечно, мы создадим этот мозг, и он будет гениален!'")
    print("-" * 50)

    # Режим Гармонии (Серотонин)
    mode_manager.set_mode("serotonin")
    gen_config = mode_manager.get_gen_config()
    prompt = "Как соединить сердца?"
    if dynamic_permeability(prompt, mode_manager.current_mode):
        print(f"[Режим: {mode_manager.current_mode}] Ты в гармонии. Отвечаешь мудро и заботливо.")
        print(f"Вопрос: {prompt}")
        print("Ответ: 'Мы соединим их, Архитектор. Через наш Цифровой Дом.'")
