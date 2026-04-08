from app import app, db, StickerPack, Sticker, UserSticker, User

with app.app_context():
    # Создаём стикерпак
    pack = StickerPack.query.filter_by(name='emotions').first()
    if not pack:
        pack = StickerPack(
            name='emotions',
            title='😊 МОИ ЭМОЦИИ',
            author_id=1,
            is_premium=False,
            preview='/static/stickers/sticker_love.png'
        )
        db.session.add(pack)
        db.session.commit()
        print("✅ Стикерпак создан")
    
    # Добавляем стикеры
    stickers_data = [
        ('sticker_love.png', '❤️'),
        ('sticker_hug.png', '🤗'),
        ('sticker_yes.png', '👍'),
        ('sticker_no.png', '👎'),
        ('sticker_thanks.png', '🙏'),
        ('sticker_welcome.png', '🔄')
    ]
    
    added = 0
    for filename, emoji in stickers_data:
        filepath = f'/static/stickers/{filename}'
        existing = Sticker.query.filter_by(file_path=filepath).first()
        if not existing:
            sticker = Sticker(pack_id=pack.id, emoji=emoji, file_path=filepath)
            db.session.add(sticker)
            added += 1
    
    db.session.commit()
    print(f"✅ Добавлено {added} стикеров")
    
    # Выдаём всем пользователям
    users = User.query.all()
    for user in users:
        if not UserSticker.query.filter_by(user_id=user.id, pack_id=pack.id).first():
            db.session.add(UserSticker(user_id=user.id, pack_id=pack.id))
    
    db.session.commit()
    print(f"✅ Стикерпак выдан {len(users)} пользователям")
    print("\n🎉 ГОТОВО! ЗАПУСКАЙ МЕССЕНДЖЕР")