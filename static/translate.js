// Универсальный переводчик BearGram (полный словарь интерфейса)
const translations = {
    // === Шапка и навигация ===
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

    // === Общие фразы ===
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
    "Всегда": "Always",
    "Войти": "Sign in",
    "Выйти из аккаунта": "Log out",
    "Забыли пароль?": "Forgot password?",
    "Восстановить пароль": "Reset password",
    "Создать аккаунт": "Create account",
    "Уже есть аккаунт?": "Already have an account?",
    "Пожалуйста, заполните все поля": "Please fill in all fields",
    "Неверный формат email": "Invalid email format",
    "Пароли не совпадают": "Passwords do not match",
    "Минимальная длина пароля": "Minimum password length",
    "Пользователь с таким email уже существует": "User with this email already exists",
    "Пользователь с таким именем уже существует": "User with this username already exists",
    "Неверный логин или пароль": "Invalid login or password",
    "Вы успешно вошли": "You have successfully logged in",
    "Вы успешно зарегистрировались": "You have successfully registered",
    "На ваш email отправлено письмо для подтверждения": "A confirmation email has been sent to your email",
    "Пожалуйста, подтвердите ваш email": "Please confirm your email",
    "Email подтверждён": "Email confirmed",
    "Email не подтверждён": "Email not confirmed",
    "Телефон подтверждён": "Phone confirmed",
    "Телефон не подтверждён": "Phone not confirmed",
    "Отправить код повторно": "Resend code",
    "Введите код из SMS": "Enter SMS code",
    "Неверный код": "Invalid code",
    "Слишком много попыток": "Too many attempts",
    "Попробуйте позже": "Try again later",
    "Аккаунт заблокирован": "Account is blocked",
    "Аккаунт удалён": "Account deleted",
    "Вы уверены, что хотите удалить аккаунт?": "Are you sure you want to delete your account?",
    "Это действие нельзя отменить": "This action cannot be undone",
    "Аккаунт успешно удалён": "Account successfully deleted",
    "Ошибка удаления аккаунта": "Account deletion error",
    "Страница не найдена": "Page not found",
    "Доступ запрещён": "Access denied",
    "Недостаточно прав": "Insufficient permissions",
    "Пожалуйста, авторизуйтесь": "Please log in",
    "Сессия истекла": "Session expired",
    "Пожалуйста, войдите снова": "Please log in again",
    "Слишком много запросов": "Too many requests",
    "Пожалуйста, подождите немного": "Please wait a moment",
    "Сервер временно недоступен": "Server temporarily unavailable",
    "Мы уже работаем над этим": "We are working on it",
    "Спасибо за понимание": "Thank you for your understanding",
    "С уважением, команда BearGram": "Sincerely, BearGram team",
    "Свяжитесь с нами": "Contact us",
    "FAQ": "FAQ",
    "Политика конфиденциальности": "Privacy policy",
    "Все права защищены": "All rights reserved",
    "Копирование запрещено": "Copying prohibited",
    "Сделано с любовью": "Made with love",
    "Доступно обновление": "Update available",
    "Установить": "Install",
    "Позже": "Later",
    "Сейчас": "Now",

    // === Профиль ===
    "Баланс кристалайзеров": "Crystal Balance",
    "Зарядить": "Top up",
    "Вывести": "Withdraw",
    "Баланс $GRRR": "$GRRR Balance",
    "Валюта хищников BearGram": "BearGram Predator Currency",
    "Управлять $GRRR": "Manage $GRRR",
    "Вывести $GRRR": "Withdraw $GRRR",
    "Ваш TON-адрес (UQ...)": "Your TON address (UQ...)",
    "Сумма": "Amount",
    "Минимальная сумма: 10 $GRRR. Комиссия сети ~0.1 TON.": "Minimum: 10 $GRRR. Network fee ~0.1 TON.",
    "Как вывести деньги? (простая инструкция)": "How to withdraw? (simple guide)",
    "1. Установи Tonkeeper": "1. Install Tonkeeper",
    "— официальный кошелёк TON. Запиши секретную фразу и сохрани в надёжном месте.": "— the official TON wallet. Save your secret phrase.",
    "2. Скопируй адрес": "2. Copy your address",
    "— в Tonkeeper нажми на адрес (начинается с UQ...), он скопируется. Это твой счёт.": "— tap on the address (starts with UQ...) to copy.",
    "3. Выведи из BearGram": "3. Withdraw from BearGram",
    "— вставь этот адрес в поле «TON-адрес», укажи сумму и нажми «Вывести». Отсканируй QR-код и подтверди перевод в Tonkeeper. GRRR придут за пару секунд.": "— paste the address, enter amount, scan QR and confirm in Tonkeeper.",
    "4. Обменяй на TON": "4. Swap to TON",
    "— в Tonkeeper или на сайте DeDust.io обменяй GRRR на TON.": "— exchange GRRR for TON in Tonkeeper or on DeDust.io.",
    "5. Получи деньги": "5. Get your money",
    "а) EUR/USD в Telegram-кошельке — обменяй TON на USDT или EUR прямо в Tonkeeper, затем переведи в @wallet и продай через P2P.": "a) EUR/USD in @wallet — swap TON to USDT or EUR and sell via P2P.",
    "б) Рубли через KuCoin — отправь TON на биржу KuCoin (Активы → Депозит → TON), зайди в раздел P2P, продай TON за RUB и получи рубли на карту.": "b) Rubles via KuCoin — deposit TON, sell for RUB in P2P.",
    "Если что-то непонятно — пиши в поддержку, поможем.": "If you have questions — contact support.",
    "Пригласить друзей": "Invite Friends",
    "Пригласи друзей из контактов и получи +25 💎 за каждого!": "Invite friends and get +25 💎 for each!",
    "Нет @username": "No @username",
    "Номер подтверждён": "Phone verified",
    "Подтвердите номер": "Verify phone",
    "Музыка": "Music",
    "Найти трек...": "Search track...",
    "Ссылка на mp3...": "MP3 link...",
    "Нет треков": "No tracks",
    "Ничего не найдено": "Nothing found",
    "Название трека:": "Track title:",
    "Без названия": "Untitled",
    "Ошибка": "Error",
    "Удалить трек?": "Delete track?",
    "Трек добавлен в твой плеер!": "Track added to your player!",
    "Ошибка при добавлении": "Error while adding",
    "Показать все": "Show all",
    "Аватар": "Avatar",
    "Загрузить аватар": "Upload Avatar",
    "Уникальный идентификатор": "Unique identifier",
    "Сохранить": "Save",
    "Приватность": "Privacy",
    "Закрытый профиль": "Private profile",
    "Уведомления": "Notifications",
    "Получать уведомления": "Receive notifications",
    "Подтверждение телефона": "Phone Verification",
    "Подтвердить": "Verify",
    "Код": "Code",
    "Анкета": "Dating Profile",
    "Опасная зона": "Danger Zone",
    "Удалить аккаунт": "Delete Account",
    "Вернуться в чат": "Back to Chat",

    // === Игры ===
    "Встроенные игры": "Built-in Games",
    "Игры сообщества": "Community Games",
    "Добавить": "Add",
    "Буст для всех игр": "Boost for all games",
    "Буст не активен": "Boost is inactive",
    "Скины": "Skins Workshop",
    "Фонд Золотой медведь": "Golden Bear Fund",
    "Автор лучшей игры месяца:": "Best game author of the month:",
    "Легенда": "Legend",
    "Мастер": "Master",
    "Талант": "Talent",
    "Популярность = запуски + время + бустеры + оценки": "Popularity = launches + time + boosters + ratings",
    "Пока нет игр. Будь первым!": "No games yet. Be the first!",
    "Демо": "Demo",

    // === GRRR ===
    "Твой баланс $GRRR:": "Your $GRRR balance:",
    "Валюта хищников": "Predator Currency",
    "Бесплатный Airdrop!": "Free Airdrop!",
    "Получи 100 $GRRR прямо сейчас!": "Get 100 $GRRR right now!",
    "Забрать 100 $GRRR": "Claim 100 $GRRR",
    "Хочешь обменять кристаллайзеры на $GRRR?": "Exchange Crystals for $GRRR?",
    "Открыть обменник": "Open Exchange",
    "Курс: 1 💎 = 0.95 $GRRR · Комиссия 5%": "Rate: 1 💎 = 0.95 $GRRR · Fee 5%",
    "Майни $GRRR и другие криптовалюты!": "Mine $GRRR and other cryptos!",
    "Открыть майнинг": "Open Mining",
    "$GRRR + Verus Coin + Monero": "$GRRR + Verus Coin + Monero",
    "Купи ноду — поддержи независимую сеть и получай до 50% годовых в $GRRR": "Buy a Node — support the network and earn up to 50% APR in $GRRR",
    "Купить Ноду": "Buy Node",
    "Сегодня доступно к выводу:": "Available for withdrawal today:",
    "из": "out of",
    "GRRR/день": "GRRR/day",
    "Комиссия: 10% · Сегодня можно вывести:": "Fee: 10% · Today you can withdraw:",
    "Отправить заявку на вывод": "Submit Withdrawal Request",
    "После отправки вы получите QR-код для подтверждения в Tonkeeper.": "After submission, scan the QR code in Tonkeeper and confirm the transfer.",

    // === Майнинг и ноды ===
    "Майнинг & Ноды": "Mining & Nodes",
    "Всего намайнено": "Total mined:",
    "Майнеров онлайн": "Miners online:",
    "Нод в сети": "Nodes in network:",
    "Заблокировано в сети": "Locked in network:",
    "Майнинг $GRRR": "Mining $GRRR",
    "Запустить майнинг $GRRR": "Start Mining $GRRR",
    "Остановить майнинг": "Stop Mining",
    "Мои Ноды": "My Nodes",
    "Активна": "Active",
    "Забрать": "Claim Reward",
    "Что такое BEAR Node?": "What is BEAR Node?",
    "Пассивный доход до 50% годовых": "Passive income up to 50% APR",
    "Майнинг других криптовалют": "Mining other cryptos",
    "О майнинге и нодах": "About mining and nodes"
};

// Функция перевода
function translatePage(lang) {
    if (lang === 'ru') {
        location.reload();
        return;
    }

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

    document.querySelectorAll('[placeholder]').forEach(el => {
        const placeholder = el.getAttribute('placeholder');
        if (placeholder && translations[placeholder]) {
            el.setAttribute('placeholder', translations[placeholder]);
        }
    });

    document.querySelectorAll('option').forEach(option => {
        const text = option.textContent.trim();
        if (text && translations[text]) {
            option.textContent = translations[text];
        }
    });

    const langBtn = document.getElementById('langToggleBtn');
    if (langBtn) {
        langBtn.textContent = lang === 'en' ? '🌐 Переключить на Русский' : '🌐 Switch to English';
    }
}

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
    const langBtn = document.getElementById('langToggleBtn');
    if (langBtn) {
        langBtn.textContent = savedLang === 'en' ? '🌐 Переключить на Русский' : '🌐 Switch to English';
    }
})();
