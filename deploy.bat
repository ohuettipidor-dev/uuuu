@echo off
cd C:\Users\Люба\Desktop\my-messenger-final

echo Скачиваю актуальную базу...
curl -k -o current_base.db "https://beargram.up.railway.app/super-secret-backup-download?token=MEGA_SECRET_TOKEN_123"
if %errorlevel% neq 0 (
    echo Ошибка скачивания!
    pause
    exit /b
)

echo Копирую базу в restore.db...
copy /Y current_base.db static\restore\restore.db >nul

echo Добавляю в Git...
git add static\restore\restore.db
git commit -m "Update database backup"

echo Пушу на Railway...
git push https://ohuettipidor-dev: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@github.com/ohuettipidor-dev/uuuu.git main --force

echo Готово! Railway перезапустится, база восстановится.
pause