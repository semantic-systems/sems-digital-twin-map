// Manages live event dots on the Leaflet map.
// All marker creation, clustering, popup, and highlight logic lives here.
// Data arrives via window._eventsData (set by Dash clientside callback).
(function () {

    var CLUSTER_RADIUS = 30; // pixels – dots closer than this are merged

    var _eventLayer = null;   // L.LayerGroup holding all event markers
    var _popup = null;        // single reusable Leaflet popup

    // ─── Layer bootstrap ──────────────────────────────────────────────────────

    function ensureLayer() {
        if (_eventLayer) return;
        if (!window._leafletMap) return;
        _eventLayer = L.layerGroup().addTo(window._leafletMap);
        window._leafletMap.on('zoomend moveend', window.updateEventDots);
    }

    // ─── Clustering ───────────────────────────────────────────────────────────

    function computeClusters(events) {
        if (!window._leafletMap || !events.length) return [];

        var points;
        try {
            points = events.map(function (e) {
                var p = window._leafletMap.latLngToContainerPoint([e.lat, e.lon]);
                return { x: p.x, y: p.y, event: e };
            });
        } catch (e) {
            return [];
        }

        var assigned = new Array(points.length).fill(false);
        var clusters = [];

        for (var i = 0; i < points.length; i++) {
            if (assigned[i]) continue;
            var cluster = { members: [points[i]], cx: points[i].x, cy: points[i].y };
            assigned[i] = true;
            for (var j = i + 1; j < points.length; j++) {
                if (assigned[j]) continue;
                var dx = points[j].x - cluster.cx, dy = points[j].y - cluster.cy;
                if (Math.sqrt(dx * dx + dy * dy) <= CLUSTER_RADIUS) {
                    cluster.members.push(points[j]);
                    assigned[j] = true;
                    // recompute centroid
                    cluster.cx = cluster.members.reduce(function (s, p) { return s + p.x; }, 0) / cluster.members.length;
                    cluster.cy = cluster.members.reduce(function (s, p) { return s + p.y; }, 0) / cluster.members.length;
                }
            }
            var evs = cluster.members.map(function (m) { return m.event; });
            clusters.push({
                lat: evs.reduce(function (s, e) { return s + e.lat; }, 0) / evs.length,
                lon: evs.reduce(function (s, e) { return s + e.lon; }, 0) / evs.length,
                events: evs,
            });
        }

        return clusters;
    }

    // ─── Icon factory ─────────────────────────────────────────────────────────

    function makeIcon(count, isActive) {
        var color = isActive ? '#1976d2' : '#e53935';
        if (count > 1) {
            return L.divIcon({
                html: '<div class="event-dot-cluster" style="background:' + color + '">'
                    + '<span class="event-dot-count">' + count + '</span></div>',
                className: '',
                iconSize: [28, 28],
                iconAnchor: [14, 14],
            });
        }
        return L.divIcon({
            html: '<div class="event-dot" style="background:' + color + '"></div>',
            className: '',
            iconSize: [16, 16],
            iconAnchor: [8, 8],
        });
    }

    // ─── Popup ────────────────────────────────────────────────────────────────

    function showEventPopup(event, latlng) {
        if (!window._leafletMap) return;
        if (_popup) _popup.remove();
        _popup = L.popup({ maxWidth: 260 })
            .setLatLng(latlng)
            .setContent(
                '<div style="font-size:10pt">'
                + '<b>' + (event.event_type || 'Event') + '</b><br>'
                + (event.time ? '<span style="color:#666">' + event.time + '</span><br>' : '')
                + '<span style="color:#888;font-size:9pt">Hash: ' + event.hash + '</span><br>'
                + '<button class="event-seen-btn" data-hash="' + event.hash + '" '
                + 'style="margin-top:6px;padding:3px 8px;font-size:9pt;cursor:pointer;'
                + 'border:1px solid #bbb;border-radius:4px;background:#f5f5f5">'
                + 'Mark as seen</button>'
                + '</div>'
            )
            .openOn(window._leafletMap);
    }

    // ─── Cluster selection menu ───────────────────────────────────────────────

    function showClusterMenu(events, mouseEvent) {
        var menu = document.getElementById('event-cluster-menu');
        if (!menu) return;

        var items = events.map(function (e, i) {
            return '<div class="event-cluster-item" data-idx="' + i + '">'
                + (e.event_type || 'Event') + (e.time ? ' · ' + e.time : '')
                + '</div>';
        }).join('');

        menu.innerHTML = '<b style="display:block;margin-bottom:6px">Select event</b>' + items;
        menu.style.display = 'block';
        menu.style.left = mouseEvent.clientX + 'px';
        menu.style.top = mouseEvent.clientY + 'px';

        // store events list for click delegation
        menu._clusterEvents = events;
    }

    function hideClusterMenu() {
        var menu = document.getElementById('event-cluster-menu');
        if (menu) menu.style.display = 'none';
    }

    // "Mark as seen" button in popup
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.event-seen-btn');
        if (!btn) return;
        var hash = btn.dataset.hash;
        if (!hash) return;
        // Write hash to Dash store → triggers server callback to mark DB rows seen
        if (window.dash_clientside && window.dash_clientside.set_props) {
            window.dash_clientside.set_props('event-mark-seen', { data: hash });
        }
        // Optimistically remove from local data and re-render immediately
        window._eventsData = (window._eventsData || []).filter(function (e) {
            return e.hash !== hash;
        });
        if (_popup) { _popup.remove(); _popup = null; }
        window._activeEventHash = null;
        window.updateEventDots();
    });

    // Cluster menu item click
    document.addEventListener('click', function (e) {
        var item = e.target.closest('.event-cluster-item');
        if (item) {
            var menu = document.getElementById('event-cluster-menu');
            var events = menu && menu._clusterEvents;
            if (!events) return;
            var idx = parseInt(item.dataset.idx);
            var ev = events[idx];
            window._activeEventHash = ev.hash;
            window.updateEventDots();
            showEventPopup(ev, [ev.lat, ev.lon]);
            hideClusterMenu();
            return;
        }
        // Click outside menu → close it
        if (!e.target.closest('#event-cluster-menu')) {
            hideClusterMenu();
        }
    });

    // ─── Main render function ─────────────────────────────────────────────────

    window.updateEventDots = function () {
        var events = window._eventsData || [];
        var activeHash = window._activeEventHash || null;
        ensureLayer();
        console.log('[events] updateEventDots: events=', events.length, '_leafletMap=', !!window._leafletMap, '_eventLayer=', !!_eventLayer);
        if (!_eventLayer) return;
        _eventLayer.clearLayers();

        var clusters = computeClusters(events);
        console.log('[events] clusters:', clusters.length);

        clusters.forEach(function (cluster) {
            var isActive = cluster.events.some(function (e) {
                return e.hash === activeHash;
            });
            var marker = L.marker([cluster.lat, cluster.lon], {
                icon: makeIcon(cluster.events.length, isActive),
                zIndexOffset: isActive ? 1000 : 0,
            });

            marker.on('click', function (e) {
                L.DomEvent.stopPropagation(e);
                hideClusterMenu();
                if (cluster.events.length === 1) {
                    window._activeEventHash = cluster.events[0].hash;
                    window.updateEventDots();
                    showEventPopup(cluster.events[0], marker.getLatLng());
                } else {
                    window._activeEventHash = null;
                    showClusterMenu(cluster.events, e.originalEvent);
                }
            });

            marker.addTo(_eventLayer);
        });
    };

    // ─── Bootstrap: wait for _leafletMap then do initial render ──────────────

    function tryInit() {
        if (window._leafletMap) {
            ensureLayer();
            window.updateEventDots();
        } else {
            setTimeout(tryInit, 300);
        }
    }
    setTimeout(tryInit, 1200);

})();
