import os
import uuid
from PIL import Image, ImageDraw, ImageFont

STICKER_FOLDER = 'static/stickers'
os.makedirs(STICKER_FOLDER, exist_ok=True)

# Создаём 10 стикеров
stickers_data = [
    ('🐻', '#FFD700', 'Мишка'),
    ('❤️', '#FF6B6B', 'Сердце'),
    ('😂', '#4ECDC4', 'Смех'),
    ('😍', '#FF6B6B', 'Влюбленность'),
    ('🎉', '#95E77E', 'Праздник'),
    ('🔥', '#FF8C42', 'Огонь'),
    ('💀', '#2C3E50', 'Череп'),
    ('🤡', '#E74C3C', 'Клоун'),
    ('👑', '#F1C40F', 'Корона'),
    ('✨', '#9B59B6', 'Звезда')
]

for i, (emoji, color, name) in enumerate(stickers_data):
    # Создаём изображение 512x512
    img = Image.new('RGBA', (512, 512), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Рисуем круглый фон
    draw.ellipse([50, 50, 462, 462], fill=color)
    
    # Рисуем эмодзи (упрощённо - просто текст, но эмодзи не рисуются в PIL)
    # Поэтому используем цветной круг с текстом
    try:
        # Пробуем загрузить шрифт
        font = ImageFont.truetype("segoeui.ttf", 300)
    except:
        font = ImageFont.load_default()
    
    # Рисуем текст (номер стикера вместо эмодзи, т.к. PIL не поддерживает эмодзи)
    draw.text((256, 256), str(i+1), fill='white', anchor='mm', font=font)
    
    # Сохраняем
    filename = f"sticker_{i}_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(STICKER_FOLDER, filename)
    img.save(filepath)
    print(f"✅ Создан стикер {i+1}: {filename}")

print(f"\n✅ Создано {len(stickers_data)} стикеров в папке {STICKER_FOLDER}")
print("Теперь запусти приложение: python app.py")