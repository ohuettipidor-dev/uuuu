import os
from PIL import Image, ImageDraw, ImageFont

STICKER_FOLDER = 'static/stickers'
os.makedirs(STICKER_FOLDER, exist_ok=True)

# 6 стикеров с эмоциями (как в Telegram)
stickers = [
    {"emoji": "❤️", "text": "Люблю", "color": "#FFB7B2", "file": "sticker_love.png"},
    {"emoji": "🤗", "text": "Обнял", "color": "#B5EAD7", "file": "sticker_hug.png"},
    {"emoji": "👍", "text": "Да", "color": "#C7CEE6", "file": "sticker_yes.png"},
    {"emoji": "👎", "text": "Нет", "color": "#FFDAC1", "file": "sticker_no.png"},
    {"emoji": "🙏", "text": "Спасибо", "color": "#E2F0CB", "file": "sticker_thanks.png"},
    {"emoji": "🔄", "text": "Всегда пожалуйста", "color": "#FFC8DD", "file": "sticker_welcome.png"}
]

print("🎨 СОЗДАЮ СТИКЕРЫ...")

for s in stickers:
    img = Image.new('RGBA', (512, 512), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Фон - скругленный прямоугольник
    draw.rounded_rectangle([40, 40, 472, 472], radius=80, fill=s["color"], outline="#E0AFA0", width=4)
    
    # Мордочка мишки
    draw.ellipse([180, 150, 332, 302], fill="#F4E3D7", outline="#B4835A", width=4)
    # Уши
    draw.ellipse([160, 120, 210, 170], fill="#F4E3D7", outline="#B4835A", width=4)
    draw.ellipse([302, 120, 352, 170], fill="#F4E3D7", outline="#B4835A", width=4)
    # Глаза
    draw.ellipse([220, 210, 248, 238], fill="#333")
    draw.ellipse([264, 210, 292, 238], fill="#333")
    draw.ellipse([228, 216, 240, 228], fill="white")
    draw.ellipse([272, 216, 284, 228], fill="white")
    # Нос
    draw.ellipse([246, 250, 266, 270], fill="#B4835A")
    # Улыбка
    draw.arc([230, 260, 282, 290], start=0, end=180, fill="#B4835A", width=4)
    
    # Текст
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except:
        font = ImageFont.load_default()
    
    draw.text((256, 360), s["text"], fill="#5D3A1A", anchor="mm", font=font)
    draw.text((420, 430), s["emoji"], fill="#5D3A1A", font=font)
    
    img.save(os.path.join(STICKER_FOLDER, s["file"]))
    print(f"  ✅ {s['file']} - {s['text']}")

print("\n✅ СТИКЕРЫ СОЗДАНЫ!")