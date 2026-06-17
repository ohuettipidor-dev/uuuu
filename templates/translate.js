// Универсальный переводчик BearGram
const translations = {
    "Финансы": "Finance",
    "Магазин": "Shop",
    "Майнинг": "Mining",
    "Банк": "Bank",
    "Тема: Светлая": "Theme: Light",
    "Тема: Тёмная": "Theme: Dark",
    "Поиск пользователей...": "Search users...",
    "Пригласить друзей из контактов": "Invite friends from contacts",
    "Создать группу": "Create group",
    "Закрыть поиск": "Close search",
    "Знакомства": "Dating",
    "Игры": "Games",
    "Голосовые": "Voice",
    "Каналы": "Channels",
    "Написать": "Write",
    "Профиль": "Profile",
    "Выйти": "Logout",
    "Premium": "Premium",
    "Wallet": "Wallet",
    "Обменник": "Exchange",
    "Ноды": "Nodes",
    "Стейкинг": "Staking",
    "Чат": "Chat",
    "Лента": "Feed",
    "Друзья": "Friends",
    "Пригласить": "Invite",
    "Ссылка": "Link",
    "QR-код": "QR code",
    "Бонусы": "Bonuses",
    "Выбрать из контактов": "Select from contacts",
    "Загрузить": "Upload",
    "Копировать ссылку": "Copy link",
    "Поделиться": "Share",
    "Загрузка...": "Loading...",
    "Не найдены": "Not found",
    "Ошибка": "Error",
    "Повторить": "Retry",
    "Донат": "Donate",
    "Комментарий": "Comment",
    "Просмотры": "Views",
    "Нравится": "Like",
    "Ответить": "Reply",
    "Отправить": "Send",
    "Отмена": "Cancel",
    "Создать": "Create",
    "Удалить": "Delete",
    "Сохранить": "Save",
    "Изменить": "Edit",
    "Назад": "Back",
    "Далее": "Next",
    "Готово": "Done",
    "Да": "Yes",
    "Нет": "No",
    "Открыть": "Open",
    "Закрыть": "Close",
    "Поиск": "Search",
    "Скачать": "Download",
    "Добро пожаловать": "Welcome",
    "Привет": "Hello",
    "Пока": "Bye",
    "Спасибо": "Thank you",
    "Пожалуйста": "Please",
    "Извините": "Sorry",
    "Вход": "Login",
    "Регистрация": "Register",
    "Пароль": "Password",
    "Email": "Email",
    "Телефон": "Phone",
    "Имя пользователя": "Username",
    "Город": "City",
    "Страна": "Country",
    "О себе": "About me",
    "Интересы": "Interests",
    "Пол": "Gender",
    "Мужской": "Male",
    "Женский": "Female",
    "Не указан": "Not specified",
    "Всех": "All",
    "Мужчин": "Men",
    "Женщин": "Women",
    "Сохранить изменения": "Save changes",
    "Настройки": "Settings",
    "Поддержка": "Support",
    "Помощь": "Help",
    "О проекте": "About",
    "Конфиденциальность": "Privacy",
    "Условия использования": "Terms of use",
    "Версия": "Version",
    "Обновить": "Update",
    "Сегодня": "Today",
    "Вчера": "Yesterday",
    "Завтра": "Tomorrow",
    "Неделя": "Week",
    "Месяц": "Month",
    "Год": "Year",
    "Никогда": "Never",
    "Всегда": "Always"
};

function translatePage(lang) {
    if (lang === 'ru') {
        // Просто перезагружаем страницу, чтобы сбросить перевод
        location.reload();
        return;
    }

    // Переводим все текстовые узлы
    const walker = document.createTreeWalker(
        document.body,
        NodeFilter.SHOW_TEXT,
        null,
        false
    );

    let node;
    while (node = walker.nextNode()) {
        const text = node.textContent.trim();
        if (text && translations[text]) {
            node.textContent = translations[text];
        }
    }

    // Переводим placeholder'ы
    document.querySelectorAll('[placeholder]').forEach(el => {
        const placeholder = el.getAttribute('placeholder');
        if (placeholder && translations[placeholder]) {
            el.setAttribute('placeholder', translations[placeholder]);
        }
    });

    // Переводим значения option в select
    document.querySelectorAll('option').forEach(option => {
        const text = option.textContent.trim();
        if (text && translations[text]) {
            option.textContent = translations[text];
        }
    });

    // Обновляем текст кнопки
    const langBtn = document.getElementById('langToggleBtn');
    if (langBtn) {
        langBtn.textContent = lang === 'en' ? '🌐 Переключить на Русский' : '🌐 Switch to English';
    }
}

// Функция переключения языка
function switchLanguage() {
    const currentLang = localStorage.getItem('lang') || 'ru';
    const newLang = currentLang === 'ru' ? 'en' : 'ru';
    localStorage.setItem('lang', newLang);
    translatePage(newLang);
}

// При загрузке страницы
(function() {
    const savedLang = localStorage.getItem('lang') || 'ru';
    if (savedLang === 'en') {
        translatePage('en');
    }
    // Обновляем текст кнопки
    const langBtn = document.getElementById('langToggleBtn');
    if (langBtn) {
        langBtn.textContent = savedLang === 'en' ? '🌐 Переключить на Русский' : '🌐 Switch to English';
    }
})();
