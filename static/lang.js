// /static/lang.js — Управление языком без баннера
(function() {
    // Удаляем куку Google Translate
    function clearGoogleCookie() {
        document.cookie = 'googtrans=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
        document.cookie = 'googtrans=; Path=/; Max-Age=0;';
    }

    // Устанавливаем куку для нужного языка
    function setGoogleLang(lang) {
        clearGoogleCookie();
        if (lang && lang !== 'ru') {
            document.cookie = 'googtrans=/ru/' + lang + '; Path=/; SameSite=Lax';
        } else {
            // для русского ставим /ru/ru или просто удаляем – оба варианта отключают перевод
            document.cookie = 'googtrans=/ru/ru; Path=/; SameSite=Lax';
        }
    }

    // Применяем язык при загрузке страницы
    var savedLang = localStorage.getItem('selectedLanguage');
    // Если сохранён русский или ничего нет — убеждаемся, что кука сброшена
    if (!savedLang || savedLang === 'ru') {
        clearGoogleCookie();
        // на всякий случай подстраховываемся: если виджет уже загрузился, сбрасываем его
        setTimeout(function() {
            var frame = document.querySelector('.goog-te-banner-frame');
            if (frame) {
                // скрываем баннер (уже скрыт CSS, но перестрахуем)
                frame.style.display = 'none';
            }
        }, 1000);
    } else {
        // Нерусский язык: устанавливаем куку, если она ещё не совпадает
        var match = document.cookie.match(/googtrans=\/ru\/([^;]+)/);
        if (!match || match[1] !== savedLang) {
            setGoogleLang(savedLang);
            location.reload(); // перезагружаем, чтобы Google Translate применил куку
        }
    }
})();
