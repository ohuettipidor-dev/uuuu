const CACHE_NAME = 'messenger-v1';
const urlsToCache = [
  '/',
  '/static/style.css',       // если у вас есть отдельный CSS, иначе можно убрать
  '/static/manifest.json',
  // при необходимости добавьте другие статические файлы
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});

// Поддержка push-уведомлений (опционально)
self.addEventListener('push', event => {
  const data = event.data.json();
  const options = {
    body: data.body,
    icon: data.icon || '/static/uploads/avatars/default.png',
    badge: data.badge || '/static/uploads/avatars/default.png'
  };
  event.waitUntil(self.registration.showNotification(data.title, options));
});