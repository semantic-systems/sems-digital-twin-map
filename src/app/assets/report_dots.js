// Manages live report dots on the Leaflet map.
// Data: window._reportDotsData  (set by Dash clientside callback)
// Active: window._activeReportId (set by Dash clientside callback)
(function () {

    var CLUSTER_RADIUS = 28; // pixels — dots closer than this collapse into one

    var _layer = null;
    var _popup = null;

    // ─── Layer bootstrap ──────────────────────────────────────────────────────

    function ensureLayer() {
        if (_layer || !window._leafletMap) return;
        _layer = L.layerGroup().addTo(window._leafletMap);
        window._leafletMap.on('zoomend moveend', window.updateReportDots);
    }

    // ─── Clustering ───────────────────────────────────────────────────────────

    function computeClusters(dots) {
        if (!window._leafletMap || !dots.length) return [];

        var points;
        try {
            points = dots.map(function (d) {
                var p = window._leafletMap.latLngToContainerPoint([d.lat, d.lon]);
                return { x: p.x, y: p.y, dot: d };
            });
        } catch (e) {
            return []; // map panes not ready (mid-render), skip this tick
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
                    cluster.cx = cluster.members.reduce(function (s, p) { return s + p.x; }, 0) / cluster.members.length;
                    cluster.cy = cluster.members.reduce(function (s, p) { return s + p.y; }, 0) / cluster.members.length;
                }
            }
            var memberDots = cluster.members.map(function (m) { return m.dot; });
            var avgLat = memberDots.reduce(function (s, d) { return s + d.lat; }, 0) / memberDots.length;
            var avgLon = memberDots.reduce(function (s, d) { return s + d.lon; }, 0) / memberDots.length;
            clusters.push({ lat: avgLat, lon: avgLon, dots: memberDots });
        }
        return clusters;
    }

    // ─── Icon factory ─────────────────────────────────────────────────────────

    function makeIcon(count, isActive) {
        var color = isActive ? '#1976d2' : '#e53935';
        if (count > 1) {
            return L.divIcon({
                html: '<div class="report-dot-cluster" style="background:' + color + '">'
                    + '<span class="report-dot-count">' + count + '</span></div>',
                className: '',
                iconSize: [26, 26],
                iconAnchor: [13, 13],
            });
        }
        return L.divIcon({
            html: '<div class="report-dot" style="background:' + color + '"></div>',
            className: '',
            iconSize: [14, 14],
            iconAnchor: [7, 7],
        });
    }

    // ─── Popup ────────────────────────────────────────────────────────────────

    function showDotPopup(dot, latlng) {
        if (!window._leafletMap) return;
        if (_popup) { _popup.remove(); _popup = null; }

        var relevanceColor = { high: '#cc0000', medium: '#ff6666', low: '#ffcccc', none: '#ccc' };
        var rColor = relevanceColor[dot.relevance] || '#ccc';

        var content = '<div style="font-size:10pt;max-width:280px">'
            + '<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">'
            + '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;flex-shrink:0;background:' + rColor + '"></span>'
            + '<b>' + escHtml(dot.event_type) + '</b>'
            + '<span style="color:#888;font-size:9pt;margin-left:auto">' + escHtml(dot.timestamp) + '</span>'
            + '</div>'
            + (dot.location_name ? '<div style="font-size:9pt;font-weight:600;color:#1976d2;margin-bottom:2px">📍 ' + escHtml(dot.location_name) + '</div>' : '')
            + (dot.location_display ? '<div style="font-size:8pt;color:#888;margin-bottom:4px">' + escHtml(dot.location_display) + '</div>' : '')
            + (dot.author ? '<div style="color:#555;font-size:9pt;margin-bottom:4px">@' + escHtml(dot.author) + ' · ' + escHtml(dot.platform) + '</div>' : '')
            + '<div style="font-size:9pt;line-height:1.4;max-height:100px;overflow:hidden;color:#333;margin-bottom:6px;border-top:1px solid #eee;padding-top:4px">'
            + escHtml(dot.text) + '</div>'
            + (dot.url ? '<a href="' + escHtml(dot.url) + '" target="_blank" style="font-size:9pt;color:#1976d2">Open post ↗</a>' : '')
            + '</div>';

        _popup = L.popup({ maxWidth: 280, autoPan: true })
            .setLatLng(latlng)
            .setContent(content)
            .openOn(window._leafletMap);
    }

    function escHtml(s) {
        return String(s || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // ─── Cluster popup (multiple dots at same spot) ───────────────────────────

    function showClusterPopup(dots, latlng) {
        if (!window._leafletMap) return;
        if (_popup) { _popup.remove(); _popup = null; }

        var items = dots.map(function (d, i) {
            return '<div class="rdot-cluster-item" data-idx="' + i + '" style="padding:4px 6px;cursor:pointer;border-radius:3px;font-size:9pt">'
                + '<b>' + escHtml(d.event_type) + '</b>'
                + (d.author ? ' · @' + escHtml(d.author) : '')
                + ' <span style="color:#888">' + escHtml(d.timestamp) + '</span>'
                + '</div>';
        }).join('');

        var content = '<div style="font-size:10pt"><b style="display:block;margin-bottom:4px">'
            + dots.length + ' reports here</b>' + items + '</div>';

        _popup = L.popup({ maxWidth: 280 })
            .setLatLng(latlng)
            .setContent(content)
            .openOn(window._leafletMap);

        // store for click delegation
        _popup._clusterDots = dots;
        _popup._clusterLatLng = latlng;
    }

    // ─── Active report helper ─────────────────────────────────────────────────

    function setActiveReport(reportId) {
        window._activeReportId = reportId;
        window.updateReportDots();
        // Sync back to Dash store so the sidebar highlight clientside callback fires
        if (window.dash_clientside && window.dash_clientside.set_props) {
            window.dash_clientside.set_props('active-report-id', { data: reportId });
        }
    }

    // cluster item click inside popup
    document.addEventListener('click', function (e) {
        var item = e.target.closest('.rdot-cluster-item');
        if (!item || !_popup || !_popup._clusterDots) return;
        var dot = _popup._clusterDots[parseInt(item.dataset.idx)];
        if (!dot) return;
        setActiveReport(dot.report_id);
        showDotPopup(dot, _popup._clusterLatLng);
    });

    // ─── Main render ──────────────────────────────────────────────────────────

    window.updateReportDots = function () {
        var dots = window._reportDotsData || [];
        var activeId = window._activeReportId || null;
        ensureLayer();
        if (!_layer) return;
        _layer.clearLayers();

        var clusters = computeClusters(dots);
        clusters.forEach(function (cluster) {
            var isActive = cluster.dots.some(function (d) { return d.report_id === activeId; });
            var marker = L.marker([cluster.lat, cluster.lon], {
                icon: makeIcon(cluster.dots.length, isActive),
                zIndexOffset: isActive ? 1000 : 0,
            });

            marker.on('click', function (e) {
                L.DomEvent.stopPropagation(e);
                if (cluster.dots.length === 1) {
                    setActiveReport(cluster.dots[0].report_id);
                    showDotPopup(cluster.dots[0], marker.getLatLng());
                } else {
                    showClusterPopup(cluster.dots, marker.getLatLng());
                }
            });

            marker.addTo(_layer);
        });
    };

    // ─── Bootstrap ────────────────────────────────────────────────────────────

    function tryInit() {
        if (window._leafletMap) {
            ensureLayer();
            window.updateReportDots();
        } else {
            setTimeout(tryInit, 300);
        }
    }
    setTimeout(tryInit, 1200);

})();
