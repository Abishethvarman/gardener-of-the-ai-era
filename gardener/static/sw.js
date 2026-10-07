// Keeps the app shell and the most recent plans available with no signal.
const CACHE = "gardener-v2";
const SHELL = ["/", "/icon.svg", "/manifest.webmanifest"];

// Let the page know it is looking at a saved copy, so it can say so.
function tagAsSaved(res) {
  const headers = new Headers(res.headers);
  headers.set("X-Gardener-Saved", "1");
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers });
}

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Plans: try the network (fresh date, fresh brief), fall back to the last copy.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok && url.pathname !== "/api/health") {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req).then((hit) => (hit ? tagAsSaved(hit) : Response.error())))
    );
    return;
  }

  // Everything else: show the cached shell instantly, refresh it in the background.
  event.respondWith(
    caches.match(req).then((hit) => {
      const refresh = fetch(req)
        .then((res) => {
          if (res.ok) caches.open(CACHE).then((c) => c.put(req, res.clone()));
          return res;
        })
        .catch(() => hit);
      return hit || refresh;
    })
  );
});
