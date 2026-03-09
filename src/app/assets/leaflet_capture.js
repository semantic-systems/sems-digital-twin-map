// Captures the Leaflet map instance and fully manages off-screen arrow indicators.
// Arrow DOM is owned entirely by this file — Dash never renders into #offscreen-indicators.
(function () {

    function latLonToPixel(lat, lon, centerLat, centerLon, zoom, W, H) {
        var scale = Math.pow(2, zoom) * 256;
        var tileX = (lon + 180) / 360 * scale;
        var lat_rad = lat * Math.PI / 180;
        var tileY = (1 - Math.log(Math.tan(lat_rad) + 1 / Math.cos(lat_rad)) / Math.PI) / 2 * scale;
        var cLat_rad = centerLat * Math.PI / 180;
        var centerTileX = (centerLon + 180) / 360 * scale;
        var centerTileY = (1 - Math.log(Math.tan(cLat_rad) + 1 / Math.cos(cLat_rad)) / Math.PI) / 2 * scale;
        return {x: tileX - centerTileX + W / 2, y: tileY - centerTileY + H / 2};
    }

    window.repositionArrows = function () {
        var lmap = window._leafletMap;
        var locations = window._offscreenLocations;
        var indicatorsEl = document.getElementById('offscreen-indicators');
        if (!indicatorsEl) return;

        if (!lmap || !locations || !locations.length) {
            indicatorsEl.innerHTML = '';
            return;
        }

        var mapEl = document.getElementById('map');
        if (!mapEl) return;

        var W = mapEl.offsetWidth, H = mapEl.offsetHeight;
        var rect = mapEl.getBoundingClientRect();
        var center, zoom;
        try {
            center = lmap.getCenter();
            zoom = lmap.getZoom();
        } catch (e) {
            return; // map panes not ready (mid-render), skip this tick
        }
        var centerLat = center.lat, centerLon = center.lng;
        var PAD = 28;

        // Index existing arrows by data-idx
        var existing = {};
        indicatorsEl.querySelectorAll('.offscreen-arrow').forEach(function (el) {
            existing[el.dataset.idx] = el;
        });

        var toKeep = {};

        locations.forEach(function (loc, i) {
            var px = latLonToPixel(loc.lat, loc.lon, centerLat, centerLon, zoom, W, H);
            var x = px.x, y = px.y;

            if (x >= PAD && x <= W - PAD && y >= PAD && y <= H - PAD) return; // on-screen

            var dx = x - W / 2, dy = y - H / 2;
            var sx = dx !== 0 ? (W / 2 - PAD) / Math.abs(dx) : Infinity;
            var sy = dy !== 0 ? (H / 2 - PAD) / Math.abs(dy) : Infinity;
            var s = Math.min(sx, sy);
            var ex = rect.left + W / 2 + dx * s;
            var ey = rect.top + H / 2 + dy * s;
            var angle = Math.atan2(dy, dx) * 180 / Math.PI;

            var el = existing[String(i)];
            if (!el) {
                el = document.createElement('div');
                el.className = 'offscreen-arrow';
                el.dataset.idx = String(i);
                indicatorsEl.appendChild(el);
            }
            el.style.left = ex + 'px';
            el.style.top = ey + 'px';
            el.style.transform = 'translate(-50%, -50%) rotate(' + angle + 'deg)';
            el.style.pointerEvents = 'auto';
            toKeep[String(i)] = true;
        });

        // Remove arrows whose pins are now on-screen
        Object.keys(existing).forEach(function (idx) {
            if (!toKeep[idx]) existing[idx].remove();
        });
    };

    // Click handler: fly to pin via captured Leaflet instance
    document.addEventListener('click', function (e) {
        var el = e.target.closest('.offscreen-arrow');
        if (!el) return;
        var idx = parseInt(el.dataset.idx);
        var locs = window._offscreenLocations;
        if (!locs || idx >= locs.length) return;
        var loc = locs[idx];
        if (window._leafletMap) {
            window._leafletMap.flyTo([loc.lat, loc.lon], 14, {duration: 0.8});
        }
    });

    function attachMoveListener() {
        if (!window._leafletMap || window._moveListenerAdded) return;
        window._moveListenerAdded = true;
        window._leafletMap.on('move', window.repositionArrows);
        window._leafletMap.on('zoom', window.repositionArrows);
    }

    // Strategy 1: patch L.Map.prototype.setView — fires after panes are ready
    function patch() {
        if (window.L && window.L.Map && !window._lmapPatched) {
            window._lmapPatched = true;
            var orig = window.L.Map.prototype.setView;
            window.L.Map.prototype.setView = function () {
                var result = orig.apply(this, arguments);
                if (!window._leafletMap) {
                    window._leafletMap = this;
                    attachMoveListener();
                }
                return result;
            };
        } else if (!window._lmapPatched) {
            setTimeout(patch, 50);
        }
    }

    // Strategy 2: React fiber traversal fallback
    function findViaFiber() {
        if (window._leafletMap) { attachMoveListener(); return; }
        var el = document.getElementById('map');
        if (!el) { setTimeout(findViaFiber, 500); return; }
        var key = Object.keys(el).find(function (k) {
            return k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance');
        });
        if (!key) { setTimeout(findViaFiber, 500); return; }
        var node = el[key];
        var seen = 0;
        while (node && seen++ < 500) {
            try {
                var ms = node.memoizedState;
                while (ms) {
                    var v = ms.memoizedState;
                    if (v && typeof v.flyTo === 'function') { window._leafletMap = v; attachMoveListener(); return; }
                    if (v && v.map && typeof v.map.flyTo === 'function') { window._leafletMap = v.map; attachMoveListener(); return; }
                    ms = ms.next;
                }
            } catch (e) {}
            node = node.child || node.sibling;
        }
        setTimeout(findViaFiber, 500);
    }

    patch();
    setTimeout(findViaFiber, 1000);
})();
