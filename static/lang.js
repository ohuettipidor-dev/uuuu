// /static/lang.js
function googleTranslateElementInit() {
    new google.translate.TranslateElement({
        pageLanguage: 'ru',
        includedLanguages: 'en,ru,es,de,fr,zh-CN,ar,pt,ja,ko,tr,it,pl,uk,hi',
        layout: google.translate.TranslateElement.InlineLayout.HORIZONTAL,
        autoDisplay: false
    }, 'google_translate_element');
}

// Загружаем Google Translate скрипт
(function() {
    var script = document.createElement('script');
    script.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
    document.head.appendChild(script);
})();

// Ждём загрузки и применяем язык
setInterval(function() {
    var lang = localStorage.getItem('selectedLanguage');
    if (lang && lang !== 'ru') {
        var select = document.querySelector('.goog-te-combo');
        if (select) {
            select.value = lang;
            select.dispatchEvent(new Event('change'));
        }
    }
}, 500);
