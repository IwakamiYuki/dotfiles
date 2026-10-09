// 「アプリとして追加」の条件（fetch ハンドラを持つ Service Worker）を満たすためだけのもの。
// 何も溜めない: 画面や API の応答は認証済みの内容なので、端末には残さず、すべてネットワークへそのまま渡す。
// （Service Worker は https か localhost などの「安全なコンテキスト」でしか動かない。http の LAN では登録されず、無害）
"use strict";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
