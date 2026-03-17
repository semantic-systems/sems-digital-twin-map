// Track shift key for filter chip "solo" mode (shift+click = show only this type)
window._shiftPressed = false;
document.addEventListener('keydown', function(e) { if (e.key === 'Shift') window._shiftPressed = true; });
document.addEventListener('keyup',   function(e) { if (e.key === 'Shift') window._shiftPressed = false; });
// Also clear on window blur (e.g. alt+tab while shift held)
window.addEventListener('blur', function() { window._shiftPressed = false; });
