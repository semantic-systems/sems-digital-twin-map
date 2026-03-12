// Manages live report dots on the Leaflet map.
// Data: window._reportDotsData  (set by Dash clientside callback)
// Active: window._activeReportId (set by Dash clientside callback)
// Seen:   window._seenIds         (array of report IDs, mirrored from user-seen store)
// Flagged: window._flaggedAuthors (array of author strings, mirrored from user-flagged store)
(function () {

    var CLUSTER_RADIUS = 28; // pixels — dots closer than this collapse into one

    var _layer = null;
    var _popup = null;
    var _currentDot = null;    // last opened single-dot, for popup refresh after seen/flag toggle
    var _currentLatlng = null;

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

    // ─── Helpers ──────────────────────────────────────────────────────────────

    function escHtml(s) {
        return String(s || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function isSeen(reportId) {
        return (window._seenIds || []).indexOf(reportId) !== -1;
    }

    function isFlagged(author) {
        return !!author && (window._flaggedAuthors || []).indexOf(author) !== -1;
    }

    // ─── Popup content builder ────────────────────────────────────────────────

    function buildDotPopupContent(dot) {
        var relevanceColor = { high: '#cc0000', medium: '#ff6666', low: '#ffcccc', none: '#ccc' };
        var rColor = relevanceColor[dot.relevance] || '#ccc';
        var seen    = isSeen(dot.report_id);
        var flagged = isFlagged(dot.author);

        var seenStyle = seen
            ? 'border:1px solid #a5d6a7;background:#e8f5e9;color:#2e7d32;font-weight:bold'
            : 'border:1px solid #ddd;background:#fafafa;color:#888';
        var flagStyle = flagged
            ? 'border:1px solid #e65100;background:#fff3e0;color:#e65100;font-weight:bold'
            : 'border:1px solid #ddd;background:#fafafa;color:#888';

        var btnBase = 'font-size:10px;padding:2px 7px;cursor:pointer;border-radius:4px;line-height:1.4;';

        return '<div style="font-size:10pt;max-width:280px">'
            + '<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">'
            +   '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;flex-shrink:0;background:' + rColor + '"></span>'
            +   '<b>' + escHtml(dot.event_type) + '</b>'
            +   '<span style="color:#888;font-size:9pt;margin-left:auto">' + escHtml(dot.timestamp) + '</span>'
            + '</div>'
            + (dot.location_name
                ? '<div style="font-size:9pt;font-weight:600;color:#1976d2;margin-bottom:2px">📍 ' + escHtml(dot.location_name) + '</div>'
                : '')
            + (dot.location_display
                ? '<div style="font-size:8pt;color:#888;margin-bottom:4px">' + escHtml(dot.location_display) + '</div>'
                : '')
            + (dot.author
                ? '<div style="color:#555;font-size:9pt;margin-bottom:4px">@' + escHtml(dot.author) + ' · ' + escHtml(dot.platform) + '</div>'
                : '')
            + '<div style="font-size:9pt;line-height:1.4;max-height:100px;overflow:hidden;color:#333;margin-bottom:6px;border-top:1px solid #eee;padding-top:4px">'
            +   escHtml(dot.text)
            + '</div>'
            // ── action bar ──
            + '<div style="display:flex;gap:6px;align-items:center">'
            +   (dot.url
                ? '<a href="' + escHtml(dot.url) + '" target="_blank" style="font-size:9pt;color:#1976d2;margin-right:auto;white-space:nowrap">↗ Open</a>'
                : '<span style="margin-right:auto"></span>')
            +   '<button class="rdot-seen-btn" data-report-id="' + dot.report_id + '" style="' + btnBase + seenStyle + '">'
            +     (seen ? 'Mark as unseen' : 'Mark as seen')
            +   '</button>'
            +   (dot.author
                ? '<button class="rdot-flag-btn" data-author="' + escHtml(dot.author) + '" data-report-id="' + dot.report_id + '" style="' + btnBase + flagStyle + '">'
                +   (flagged ? 'Unflag' : 'Flag')
                + '</button>'
                : '')
            + '</div>'
            + '</div>';
    }

    // ─── Popup ────────────────────────────────────────────────────────────────

    function showDotPopup(dot, latlng) {
        if (!window._leafletMap) return;
        if (_popup) { _popup.remove(); _popup = null; }

        _currentDot    = dot;
        _currentLatlng = latlng;

        _popup = L.popup({ maxWidth: 300, autoPan: true })
            .setLatLng(latlng)
            .setContent(buildDotPopupContent(dot))
            .openOn(window._leafletMap);
    }

    // ─── Cluster popup (multiple dots at same spot) ───────────────────────────

    function showClusterPopup(dots, latlng) {
        if (!window._leafletMap) return;
        if (_popup) { _popup.remove(); _popup = null; }

        _currentDot    = null; // cluster, not a single dot
        _currentLatlng = latlng;

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

        _popup._clusterDots = dots;
        _popup._clusterLatLng = latlng;
    }

    // ─── Dash store sync ──────────────────────────────────────────────────────

    function syncToStore(storeId, value) {
        if (window.dash_clientside && window.dash_clientside.set_props) {
            window.dash_clientside.set_props(storeId, { data: value });
        }
    }

    // ─── Active report helper ─────────────────────────────────────────────────

    function setActiveReport(reportId) {
        window._activeReportId = reportId;
        window.updateReportDots();
        syncToStore('active-report-id', reportId);
    }

    // ─── Flag toggle helper ───────────────────────────────────────────────────

    function _toggleAuthorFlag(author) {
        var flagged = (window._flaggedAuthors || []).slice();
        var fidx = flagged.indexOf(author);
        if (fidx !== -1) flagged.splice(fidx, 1);
        else             flagged.push(author);
        window._flaggedAuthors = flagged;

        var isFlagged = flagged.indexOf(author) !== -1;

        // Update all sidebar flag buttons for this author immediately
        document.querySelectorAll('.sidebar-flag-btn').forEach(function(btn) {
            try {
                var bid = JSON.parse(btn.id);
                if ((bid.author || '') !== author) return;
                btn.textContent      = isFlagged ? 'Unflag' : 'Flag';
                btn.style.border     = isFlagged ? '1px solid #e65100' : '1px solid #ddd';
                btn.style.background = isFlagged ? '#fff3e0' : '#fafafa';
                btn.style.color      = isFlagged ? '#e65100' : '#888';
                btn.style.fontWeight = isFlagged ? 'bold' : 'normal';
                // Mark the whole report entry with a red outline
                var li = btn.closest('li');
                if (li) li.style.outline = isFlagged ? '2px solid #e65100' : 'none';
            } catch(e) {}
        });

        syncToStore('user-flagged', flagged);

        // Refresh map popup if open
        if (_currentDot && _popup) {
            _popup.setContent(buildDotPopupContent(_currentDot));
        }
        if (window.updateReportDots) window.updateReportDots();
    }

    // ─── Event delegation ─────────────────────────────────────────────────────

    document.addEventListener('click', function (e) {

        // Cluster item → open single-dot popup
        var clusterItem = e.target.closest('.rdot-cluster-item');
        if (clusterItem && _popup && _popup._clusterDots) {
            var dot = _popup._clusterDots[parseInt(clusterItem.dataset.idx)];
            if (!dot) return;
            setActiveReport(dot.report_id);
            showDotPopup(dot, _popup._clusterLatLng);
            return;
        }

        // Seen button
        var seenBtn = e.target.closest('.rdot-seen-btn');
        if (seenBtn) {
            var reportId = parseInt(seenBtn.dataset.reportId);
            var seenIds = (window._seenIds || []).slice();
            var idx = seenIds.indexOf(reportId);
            if (idx !== -1) seenIds.splice(idx, 1);
            else            seenIds.push(reportId);
            window._seenIds = seenIds;

            // Update the in-memory dot so it disappears / reappears immediately
            var dotEntry = (window._reportDotsData || []).find(function (d) { return d.report_id === reportId; });
            if (dotEntry) dotEntry.seen = (idx === -1); // true if we just added it

            syncToStore('user-seen', seenIds);
            window.updateReportDots();

            if (idx === -1) {
                // Just marked as seen — dot will vanish, close the popup
                if (_popup) { _popup.remove(); _popup = null; _currentDot = null; }
            } else {
                // Just unmarked — refresh popup in place
                if (_currentDot && _popup) {
                    _popup.setContent(buildDotPopupContent(_currentDot));
                }
            }
            return;
        }

        // Flag button (map popup)
        var flagBtn = e.target.closest('.rdot-flag-btn');
        if (flagBtn) {
            var author = flagBtn.dataset.author;
            if (!author) return;
            _toggleAuthorFlag(author);
            return;
        }

        // Flag button (sidebar)
        var sidebarFlagBtn = e.target.closest('.sidebar-flag-btn');
        if (sidebarFlagBtn) {
            var sideFlagAuthor = '';
            try {
                var btnId = JSON.parse(sidebarFlagBtn.id);
                sideFlagAuthor = btnId.author || '';
            } catch(e2) {}
            if (!sideFlagAuthor) return;
            _toggleAuthorFlag(sideFlagAuthor);
            return;
        }
    });

    // ─── Main render ──────────────────────────────────────────────────────────

    window.updateReportDots = function () {
        var allDots = window._reportDotsData || [];
        var activeId = window._activeReportId || null;

        // Close popup when there is no active report
        if (!activeId && _popup) {
            _popup.remove();
            _popup = null;
            _currentDot = null;
        }

        // Show unseen dots always; show seen dots only when they are the active report
        var dots = allDots.filter(function (d) {
            return !d.seen || d.report_id === activeId;
        });
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
