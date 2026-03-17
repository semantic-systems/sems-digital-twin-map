// Manages a Leaflet.heat heatmap layer over all report dot locations.
// Controlled via window.setHeatmap(enabled).
(function () {

    var _layer = null;

    function buildPoints() {
        var dots = window._reportDotsData || [];
        return dots.map(function (d) { return [d.lat, d.lon]; });
    }

    window.setHeatmap = function (enabled) {
        if (!window._leafletMap) {
            // Map not ready yet — retry shortly
            setTimeout(function () { window.setHeatmap(enabled); }, 300);
            return;
        }

        if (enabled) {
            var pts = buildPoints();
            if (_layer) {
                try { _layer.setLatLngs(pts); } catch (e) { _layer = null; }
            }
            if (!_layer) {
                _layer = L.heatLayer(pts, {
                    radius: 80,
                    blur: 50,
                    maxZoom: 17,
                    gradient: { 0.3: '#2196f3', 0.55: '#4caf50', 0.75: '#ffeb3b', 1.0: '#f44336' },
                });
            }
            try { _layer.addTo(window._leafletMap); } catch (e) {}
        } else {
            if (_layer) {
                try { _layer.remove(); } catch (e) {}
            }
        }
    };

})();
