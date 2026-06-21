// /static/lang.js — Автопереводчик BearGram (исправленный)
(function() {
    const translationCache = {};

    async function translateText(text, targetLang) {
        if (!text || text.trim() === '') return text;
        if (targetLang === 'ru') return text;
        
        const cacheKey = `${text}_${targetLang}`;
        if (translationCache[cacheKey]) return translationCache[cacheKey];
        
        try {
            // Используем HTTPS и другой endpoint
            const response = await fetch(
                `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${targetLang}&dt=t&q=${encodeURIComponent(text)}`
            );
            const data = await response.json();
            let translatedText = '';
            if (data && data[0]) {
                data[0].forEach(item => { 
                    if (item && item[0]) translatedText += item[0]; 
                });
            }
            translationCache[cacheKey] = translatedText || text;
            return translationCache[cacheKey];
        } catch (error) {
            console.error('Translation error:', error);
            return text;
        }
    }

    async function translatePage(targetLang) {
        if (targetLang === 'ru') return;
        
        // Переводим только видимые текстовые узлы в body
        const walker = document.createTreeWalker(
            document.body, 
            NodeFilter.SHOW_TEXT, 
            {
                acceptNode: function(node) {
                    // Пропускаем всё что не нужно
                    const tag = node.parentElement.tagName;
                    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT' || 
                        tag === 'SELECT' || tag === 'OPTION' || tag === 'TEXTAREA' ||
                        tag === 'CODE' || tag === 'PRE') {
                        return NodeFilter.FILTER_REJECT;
                    }
                    // Пропускаем пустые и короткие узлы
                    const text = node.textContent.trim();
                    if (!text || text.length < 2) return NodeFilter.FILTER_REJECT;
                    // Пропускаем узлы внутри скрытых элементов
                    if (node.parentElement.offsetParent === null && 
                        node.parentElement.tagName !== 'BODY') {
                        return NodeFilter.FILTER_REJECT;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );
        
        const textNodes = [];
        while (walker.nextNode()) {
            textNodes.push(walker.currentNode);
        }
        
        // Переводим не больше 50 узлов за раз (чтобы не перегружать)
        const batchSize = 30;
        for (let i = 0; i < textNodes.length; i += batchSize) {
            const batch = textNodes.slice(i, i + batchSize);
            await Promise.all(batch.map(async (node) => {
                const originalText = node.textContent;
                if (node.parentElement.tagName === 'INPUT') {
                    if (node.parentElement.placeholder && node.parentElement.placeholder.trim()) {
                        node.parentElement.placeholder = await translateText(
                            node.parentElement.placeholder, targetLang
                        );
                    }
                } else {
                    const translated = await translateText(originalText, targetLang);
                    if (translated && translated !== originalText) {
                        node.textContent = translated;
                    }
                }
            }));
        }
    }

    // Запускаем перевод при загрузке страницы
    const savedLang = localStorage.getItem('selectedLanguage');
    if (savedLang && savedLang !== 'ru') {
        // Ждём полной загрузки страницы
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => translatePage(savedLang));
        } else {
            translatePage(savedLang);
        }
    }
})();
