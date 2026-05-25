function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

async function subscribeToPush() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
    
    const registration = await navigator.serviceWorker.register('/static/sw.js');
    let subscription = await registration.pushManager.getSubscription();
    
    if (!subscription) {
        const response = await fetch('/api/push/vapid_public_key');
        const vapidPublicKey = await response.text();
        
        subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
        });
        
        await fetch('/api/push/subscribe', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(subscription)
        });
    }
}

async function requestNotificationPermission() {
    if (!('Notification' in window)) return;
    const permission = await Notification.requestPermission();
    if (permission === 'granted') {
        await subscribeToPush();
        updateNotificationUI(true);
    }
}

function updateNotificationUI(granted) {
    const btn = document.getElementById('notificationsBtn');
    if (btn) {
        btn.textContent = granted ? '🔔' : '🔕';
        btn.style.opacity = granted ? '1' : '0.5';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (Notification.permission === 'granted') {
        subscribeToPush();
        updateNotificationUI(true);
    }
});