self.addEventListener('push', event => {
    const data = event.data?.json() || {title: 'BearGram', body: 'Новое уведомление'};
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/static/avatars/default.png',
            badge: '/static/avatars/default.png',
            data: data.url || '/chat'
        })
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    const url = event.notification.data || '/chat';
    event.waitUntil(
        clients.openWindow(url)
    );
});