// Sets window._langStrings so report_dots.js can access translated strings.
// Populated by the Dash clientside callback in map.py (Input: 'lang' store).
window._langStrings = window._langStrings || {};
window._t = function(key, fallback) {
    return window._langStrings[key] || fallback || key;
};
