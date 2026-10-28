// Caches the simulator, its models and pack audio so a session runs with no network.
const CACHE = "doosri-v1";
const SHELL = ["/classroom.html", "/style.css", "/js/engine.js", "/js/device.js", "/vendor/vosk.js"];

self.addEventListener("install", e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));

const cacheFirst = url =>
  url.pathname.startsWith("/models/") || url.pathname.startsWith("/vendor/") ||
  url.pathname.includes("/audio/") || url.hostname === "cdn.jsdelivr.net";

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (cacheFirst(url)) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok || res.type === "opaque") { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    })));
    return;
  }
  // Everything else: network first, cached copy when offline.
  e.respondWith(fetch(req).then(res => {
    if (res.ok && url.origin === location.origin && !url.pathname.startsWith("/api/")) {
      const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy));
    }
    return res;
  }).catch(() => caches.match(req, {ignoreSearch: url.pathname.endsWith(".html")})));
});
