// /static/lang.js
(function() {
    const cache = {};
    
    async function t(text, lang) {
        if (!text || !text.trim() || lang === 'ru') return text;
        const key = text + lang;
        if (cache[key]) return cache[key];
        try {
            const r = await fetch('https://translate.googleapis.com/translate_a/single?client=gtx&sl=ru&tl=' + lang + '&dt=t&q=' + encodeURIComponent(text));
            const d = await r.json();
            let res = '';
            if (d && d[0]) d[0].forEach(function(i) { if (i && i[0]) res += i[0]; });
            cache[key] = res || text;
            return cache[key];
        } catch(e) {
            return text;
        }
    }
    
    async function translateAll(lang) {
        if (lang === 'ru') return;
        var all = document.querySelectorAll('h1, h2, h3, h4, h5, h6, p, span, a, button, div, small, label, option');
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            if (el.children.length > 0) continue;
            if (el.tagName === 'INPUT') {
                if (el.placeholder) el.placeholder = await t(el.placeholder, lang);
                if (el.value && el.type === 'submit') el.value = await t(el.value, lang);
            } else if (el.tagName === 'BUTTON') {
                el.textContent = await t(el.textContent, lang);
            } else {
                var txt = el.textContent.trim();
                if (txt.length > 0 && txt.length < 500) {
                    el.textContent = await t(txt, lang);
                }
            }
        }
    }
    
    var lang = localStorage.getItem('selectedLanguage');
    if (lang && lang !== 'ru') {
        setTimeout(function() { translateAll(lang); }, 2000);
    }
})();
