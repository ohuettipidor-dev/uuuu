// /static/lang.js — Автопереводчик BearGram
(function() {
    const translationCache = {};

    async function translateText(text, targetLang) {
        if (!text || text.trim() === '') return text;
        if (targetLang === 'ru') return text;
        
        const cacheKey = `${text}_${targetLang}`;
        if (translationCache[cacheKey]) return translationCache[cacheKey];
        
        try {
            const response = await fetch(
                `https://translate.googleapis.com/translate_a/single?client=gtx&sl=ru&tl=${targetLang}&dt=t&q=${encodeURIComponent(text)}`
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
            return text;
        }
    }

    async function translatePage(targetLang) {
        if (targetLang === 'ru') return;
        
        // Переводим все текстовые узлы
        const walker = document.createTreeWalker(
            document.body, 
            NodeFilter.SHOW_TEXT, 
            null, 
            false
        );
        
        const textNodes = [];
        while (walker.nextNode()) {
            const node = walker.currentNode;
            const tag = node.parentElement.tagName;
            
            // Пропускаем скрипты, стили, селекты
            if (tag === 'SCRIPT' || tag === 'STYLE' || 
                tag === 'SELECT' || tag === 'OPTION' || 
                tag === 'TEXTAREA') continue;
                
            const text = node.textContent.trim();
            if (text && text.length > 1) {
                textNodes.push(node);
            }
        }

        // Переводим узлы
        for (const node of textNodes) {
            if (node.parentElement.tagName === 'INPUT') {
                if (node.parentElement.placeholder) {
                    node.parentElement.placeholder = await translateText(
                        node.parentElement.placeholder, targetLang
                    );
                }
            } else {
                const translated = await translateText(node.textContent, targetLang);
                if (translated && translated !== node.textContent) {
                    node.textContent = translated;
                }
            }
        }
    }

    // Запускаем перевод при загрузке
    const savedLang = localStorage.getItem('selectedLanguage');
    if (savedLang && savedLang !== 'ru') {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => translatePage(savedLang));
        } else {
            translatePage(savedLang);
        }
    }
})();
