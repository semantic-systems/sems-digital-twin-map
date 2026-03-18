// Manages live report dots on the Leaflet map.
// Data:    window._reportDotsData  (set by Dash clientside callback)
// Active:  window._activeReportId  (set by Dash clientside callback)
// State:   window._reportState     (dict {reportId: {hide, flag, flag_author, added}}, mirrored from user-state-snapshot store)
// Derived: window._seenIds         (array of report IDs where hide=true)
// Derived: window._flaggedAuthors  (array of unique author strings where flag=true)
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

    function makeIcon(count, isActive, hasNew) {
        var color = isActive ? '#1976d2' : '#e53935';
        var newBadgeLarge = hasNew
            ? '<span style="position:absolute;top:-7px;right:-7px;background:#ff9800;color:white;'
            +   'border-radius:50%;width:18px;height:18px;font-size:12px;font-weight:bold;'
            +   'display:flex;align-items:center;justify-content:center;'
            +   'border:2px solid white;line-height:1;pointer-events:none">!</span>'
            : '';
        var newBadgeSmall = hasNew
            ? '<span style="position:absolute;top:-5px;right:-5px;background:#ff9800;color:white;'
            +   'border-radius:50%;width:13px;height:13px;font-size:9px;font-weight:bold;'
            +   'display:flex;align-items:center;justify-content:center;'
            +   'border:2px solid white;line-height:1;pointer-events:none">!</span>'
            : '';
        if (count > 1) {
            return L.divIcon({
                html: '<div class="report-dot-cluster" style="background:' + color + ';position:relative">'
                    + '<span class="report-dot-count">' + count + '</span>'
                    + newBadgeLarge + '</div>',
                className: '',
                iconSize: [34, 34],
                iconAnchor: [17, 17],
            });
        }
        return L.divIcon({
            html: '<div class="report-dot" style="background:' + color + ';position:relative">'
                + newBadgeSmall + '</div>',
            className: '',
            iconSize: [20, 20],
            iconAnchor: [10, 10],
        });
    }

    // Returns whether a dot should show the NEW (!) badge.
    // Prefers window._reportState (updated by snapshot) over d.new (set at server render time).
    function isNewReport(d) {
        var stateEntry = (window._reportState || {})[d.report_id];
        if (stateEntry && stateEntry.new !== undefined) return !!stateEntry.new;
        return !!d.new;
    }

    // ─── Helpers ──────────────────────────────────────────────────────────────

    function escHtml(s) {
        return String(s || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function isSeen(reportId) {
        return !!((window._reportState || {})[reportId] || {}).hide;
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
                ? '<a href="' + escHtml(dot.url) + '" target="_blank" style="font-size:9pt;color:#1976d2;margin-right:auto;white-space:nowrap">' + _t('js_open', '↗ Open') + '</a>'
                : '<span style="margin-right:auto"></span>')
            +   '<button class="rdot-seen-btn" data-report-id="' + dot.report_id + '" style="' + btnBase + seenStyle + '">'
            +     (seen ? _t('js_unhide', 'Unhide') : _t('js_hide', 'Hide'))
            +   '</button>'
            +   (dot.author
                ? '<button class="rdot-flag-btn" data-author="' + escHtml(dot.author) + '" data-report-id="' + dot.report_id + '" style="' + btnBase + flagStyle + '">'
                +   (flagged ? _t('js_unflag', 'Unflag') : _t('js_flag', 'Flag'))
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
            var isNew = isNewReport(d);
            var newBadge = isNew
                ? '<span style="display:inline-block;background:#e53935;color:white;font-size:8px;font-weight:bold;border-radius:10px;padding:0 5px;margin-right:4px;vertical-align:middle">' + _t('js_new', 'NEW') + '</span>'
                : '';
            var preview = d.text ? escHtml(d.text.slice(0, 80)) + (d.text.length > 80 ? '…' : '') : '';
            return '<div class="rdot-cluster-item" data-idx="' + i + '" style="padding:5px 6px;cursor:pointer;border-radius:3px;border-bottom:1px solid #f0f0f0">'
                + '<div style="display:flex;align-items:center;gap:4px;margin-bottom:2px">'
                +   newBadge
                +   '<b style="font-size:9pt">' + escHtml(d.event_type) + '</b>'
                +   (d.author ? '<span style="color:#555;font-size:8pt">@' + escHtml(d.author) + '</span>' : '')
                +   '<span style="color:#aaa;font-size:8pt;margin-left:auto">' + escHtml(d.timestamp) + '</span>'
                + '</div>'
                + (preview ? '<div style="font-size:8pt;color:#555;line-height:1.4">' + preview + '</div>' : '')
                + '</div>';
        }).join('');

        var content = '<div style="font-size:10pt;min-width:220px"><b style="display:block;margin-bottom:6px">'
            + _t('js_reports_here', '{n} reports here').replace('{n}', dots.length) + '</b>' + items + '</div>';

        _popup = L.popup({ maxWidth: 320 })
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
        // Optimistically clear the NEW flag locally so the ! badge disappears immediately
        var state = window._reportState || {};
        if (!state[reportId]) state[reportId] = {};
        state[reportId].new = false;
        window._reportState = state;
        window._activeReportId = reportId;
        window.updateReportDots();
        syncToStore('active-report-id', reportId);
    }

    // ─── Flag toggle helper (map popup only — server callback handles sidebar) ──

    function _toggleAuthorFlagLocal(author) {
        // Optimistic local-only update for the map popup display.
        // The actual persistence is handled by the server-side toggle_author_flag callback.
        var state = window._reportState || {};

        var anyFlagged = Object.keys(state).some(function(id) {
            return (state[id].flag_author || state[id].author) === author && state[id].flag;
        });
        var newFlag = !anyFlagged;

        // Update all existing entries that belong to this author
        var updated = false;
        Object.keys(state).forEach(function(id) {
            var a = state[id].flag_author || state[id].author || '';
            if (a === author) {
                state[id].flag = newFlag;
                state[id].flag_author = author;
                state[id].author = author;
                updated = true;
            }
        });

        // No existing entry matched — create one for the current dot so the toggle takes effect
        if (!updated && _currentDot) {
            var rid = String(_currentDot.report_id);
            if (!state[rid]) state[rid] = { hide: false, flag: false, flag_author: '', author: '', added: true, new: false };
            state[rid].flag = newFlag;
            state[rid].flag_author = author;
            state[rid].author = author;
        }

        window._reportState = state;
        window._flaggedAuthors = Object.values(state)
            .filter(function(s) { return s.flag && (s.flag_author || s.author); })
            .map(function(s) { return s.flag_author || s.author; })
            .filter(function(v, i, a) { return a.indexOf(v) === i; });

        // Immediately sync sidebar flag buttons and li outlines without waiting for server
        var flagged = window._flaggedAuthors;
        document.querySelectorAll('[id*="flag-button"]').forEach(function(btn) {
            try {
                var idObj = JSON.parse(btn.id);
                var a = idObj.author || '';
                var isFlagged = !!a && flagged.indexOf(a) !== -1;
                btn.textContent      = isFlagged ? _t('unflag', 'Unflag') : _t('flag', 'Flag');
                btn.style.border     = isFlagged ? '1px solid #e65100' : '1px solid #ddd';
                btn.style.background = isFlagged ? '#fff3e0' : '#fafafa';
                btn.style.color      = isFlagged ? '#e65100' : '#888';
                btn.style.fontWeight = isFlagged ? 'bold' : 'normal';
                var li = btn.closest('li');
                if (li) li.style.outline = isFlagged ? '2px solid #e65100' : 'none';
            } catch(e) {}
        });

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

        // Seen button (map popup only — sidebar seen buttons are handled by Dash server callback)
        var seenBtn = e.target.closest('.rdot-seen-btn');
        if (seenBtn) {
            var reportId = parseInt(seenBtn.dataset.reportId);
            var state = window._reportState || {};
            var entry = state[reportId] || {hide: false, flag: false, added: false, flag_author: '', author: ''};
            var wasHidden = !!entry.hide;
            entry.hide = !wasHidden;
            state[reportId] = entry;
            window._reportState = state;

            // Re-derive seenIds
            window._seenIds = Object.keys(state).filter(function(id) {
                return state[id].hide;
            }).map(Number);

            // Update the in-memory dot
            var dotEntry = (window._reportDotsData || []).find(function(d) { return d.report_id === reportId; });
            if (dotEntry) dotEntry.seen = entry.hide;

            window.updateReportDots();

            if (entry.hide) {
                // Just hidden — dot will vanish, close the popup
                if (_popup) { _popup.remove(); _popup = null; _currentDot = null; }
            } else {
                // Just unhidden — refresh popup in place
                if (_currentDot && _popup) {
                    _popup.setContent(buildDotPopupContent(_currentDot));
                }
            }
            return;
        }

        // Flag button (map popup only — sidebar flag buttons are handled by Dash server callback)
        var flagBtn = e.target.closest('.rdot-flag-btn');
        if (flagBtn) {
            var author = flagBtn.dataset.author;
            if (!author) return;
            _toggleAuthorFlagLocal(author);
            syncToStore('popup-flag-request', { author: author, ts: Date.now() });
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
            var hasNew   = cluster.dots.some(function (d) { return isNewReport(d); });
            var marker = L.marker([cluster.lat, cluster.lon], {
                icon: makeIcon(cluster.dots.length, isActive, hasNew),
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
