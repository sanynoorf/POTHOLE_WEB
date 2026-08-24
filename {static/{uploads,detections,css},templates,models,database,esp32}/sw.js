const CACHE='roadwatch-v1';
self.addEventListener('install',e=>{self.skipWaiting();});
self.addEventListener('activate',e=>{self.clients.claim();});
self.addEventListener('fetch',e=>{
  if(e.request.url.includes('/api/')||e.request.url.includes('/upload')) return;
  e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));
});
