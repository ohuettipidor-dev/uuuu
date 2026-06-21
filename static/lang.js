// /static/lang.js — Управление языком без баннера
(function() {
    // Удаляем куку Google Translate
    function clearGoogleCookie() {
        document.cookie = 'googtrans=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
        document.cookie = 'googtrans=; Path=/; Max-Age=0;';
    }

    // Применяем сохранённый язык
    function applyLanguage(lang) {
        clearGoogleCookie();
        if (!lang || lang === 'ru') {
            // Если русский — удаляем куку и ничего не переводим
            return;
        }
        // Устанавливаем куку для Google Translate
        document.cookie = 'googtrans=/ru/' + lang + '; Path=/; SameSite=Lax';
        // Перезагружаем страницу, чтобы Google Translate подхватил
        location.reload();
    }

    // Вызывается при загрузке страницы: проверяем, надо ли переключить
    var savedLang = localStorage.getItem('selectedLanguage');
    var currentCookie = document.cookie.match(/googtrans=\/ru\/([^;]+)/);
    var currentLang = currentCookie ? currentCookie[1] : null;

    // Если сохранённый язык не совпадает с текущей кукой — применяем
    if (savedLang && savedLang !== 'ru' && currentLang !== savedLang) {
        applyLanguage(savedLang);
    } else if (!savedLang && currentLang) {
        // Если нет сохранённого языка, но кука есть — убираем её (возвращаем русский)
        applyLanguage('ru');
    }
})();
