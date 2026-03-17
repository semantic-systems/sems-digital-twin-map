"""
Internationalisation helpers.
Usage:  from app.i18n import t
        t('de', 'hide')  →  'Ausblenden'
"""

TRANSLATIONS: dict[str, dict[str, str]] = {
    'de': {
        # --- filter bar ---
        'location':      'Standort',
        'relevance':     'Relevanz',
        'rel_high':      'Hoch',
        'rel_medium':    'Mittel',
        'rel_low':       'Niedrig',
        'rel_none':      'Keine',
        'platform':      'Plattform',
        'view':          'Ansicht',
        'type':          'Typ',
        'layers':        'Ebenen',
        'show_hidden':   'Ausgeblendete anzeigen',
        'show_flagged':  'Markiert',
        'show_unflagged':'Nicht markiert',
        # --- event types (keys = DE value stored in DB) ---
        'et_Irrelevant':                    'Irrelevant',
        'et_Menschen betroffen':            'Menschen betroffen',
        'et_Warnungen & Hinweise':          'Warnungen & Hinweise',
        'et_Evakuierungen & Umsiedlungen':  'Evakuierungen & Umsiedlungen',
        'et_Spenden & Freiwillige':         'Spenden & Freiwillige',
        'et_Infrastruktur-Schäden':         'Infrastruktur-Schäden',
        'et_Verletzte & Tote':              'Verletzte & Tote',
        'et_Vermisste & Gefundene':         'Vermisste & Gefundene',
        'et_Bedarfe & Anfragen':            'Bedarfe & Anfragen',
        'et_Einsatzmaßnahmen':              'Einsatzmaßnahmen',
        'et_Mitgefühl & Unterstützung':     'Mitgefühl & Unterstützung',
        'et_Sonstiges':                     'Sonstiges',
        # --- location filter options ---
        'loc_all':       'Alle',
        'loc_located':   '📍 Verortet',
        'loc_pending':   '◎ Ausstehend',
        'loc_none':      '∅ Keine',
        # --- sidebar header ---
        'reports':       'Berichte',
        'auto_update':   'Autom. Aktualisierung',
        'reset_demo':    '↺ Demo zurücksetzen',
        # --- new-posts banner ---
        'new_posts_0':      '↑ 0 neue Beiträge',
        'new_posts_one':    '↑ {n} neuer Beitrag',
        'new_posts_many':   '↑ {n} neue Beiträge',
        # --- report list ---
        'new_badge':     'NEU',
        'no_reports':    'Keine Berichte verfügbar.',
        'open':          'Öffnen',
        'open_title':    'Originalbeitrag öffnen',
        'center':        'Zentrieren',
        'center_title':  'Karte auf diesen Bericht zentrieren',
        'hide':          'Ausblenden',
        'unhide':        'Einblenden',
        'flag':          'Markieren',
        'unflag':        'Entmarkieren',
        'flag_title':    'Autor markieren',
        'unflag_title':  'Markierung aufheben',
        'no_author_title': 'Kein Autor zum Markieren',
        'geo_icon':          '📍',
        'geo_title':         'Georeferenziert',
        'pending_icon':      '◎ ',
        'pending_title':     'Standorte ausstehend',
        'no_loc_icon':       '· ',
        'no_loc_title':      'Keine Standorte',
        'georeference_title':'Standort auf der Karte georeferenzieren',
        'reassign_title':    'Standort auf der Karte neu zuweisen',
        'remove_location':   'Standort entfernen',
        'add_location':      '📍 Hinzufügen',
        'add_location_title':'Standort auf der Karte setzen',
        'restore_locations': '↩ Wiederherstellen',
        'restore_title':     'Ursprünglich erkannte Standorte wiederherstellen',
        # --- username modal ---
        'welcome':           'Willkommen',
        'username_prompt':   'Geben Sie Ihren Benutzernamen ein, um Ihren Sitzungsstatus browserübergreifend zu speichern.',
        'username_ph':       'Benutzernamen eingeben…',
        'continue':          'Weiter',
        'err_empty':         'Bitte Benutzernamen eingeben.',
        'err_too_long':      'Benutzername darf maximal 64 Zeichen lang sein.',
        # --- location pick overlay ---
        'pick_prompt':       '📍 Auf die Karte klicken, um einen Standort zu setzen',
        'cancel':            'Abbrechen',
        'or':                'oder',
        'search_osm_ph':     'OpenStreetMap durchsuchen…',
        'no_results':        'Keine Ergebnisse gefunden.',
        # --- JS popup (report_dots.js via window._langStrings) ---
        'js_open':         '↗ Öffnen',
        'js_hide':         'Ausblenden',
        'js_unhide':       'Einblenden',
        'js_flag':         'Markieren',
        'js_unflag':       'Entmarkieren',
        'js_new':          'NEU',
        'js_reports_here': '{n} Berichte hier',
    },
    'en': {
        # --- filter bar ---
        'location':      'Location',
        'relevance':     'Relevance',
        'rel_high':      'High',
        'rel_medium':    'Medium',
        'rel_low':       'Low',
        'rel_none':      'None',
        'platform':      'Platform',
        'view':          'View',
        'type':          'Type',
        'layers':        'Layers',
        'show_hidden':   'Show hidden',
        'show_flagged':  'Flagged',
        'show_unflagged':'Unflagged',
        # --- event types (keys = DE value stored in DB) ---
        'et_Irrelevant':                    'Irrelevant',
        'et_Menschen betroffen':            'People affected',
        'et_Warnungen & Hinweise':          'Warnings & Notices',
        'et_Evakuierungen & Umsiedlungen':  'Evacuations & Relocations',
        'et_Spenden & Freiwillige':         'Donations & Volunteers',
        'et_Infrastruktur-Schäden':         'Infrastructure Damage',
        'et_Verletzte & Tote':              'Injured & Fatalities',
        'et_Vermisste & Gefundene':         'Missing & Found',
        'et_Bedarfe & Anfragen':            'Needs & Requests',
        'et_Einsatzmaßnahmen':              'Response Measures',
        'et_Mitgefühl & Unterstützung':     'Sympathy & Support',
        'et_Sonstiges':                     'Other',
        # --- location filter options ---
        'loc_all':       'All',
        'loc_located':   '📍 Located',
        'loc_pending':   '◎ Pending',
        'loc_none':      '∅ None',
        # --- sidebar header ---
        'reports':       'Reports',
        'auto_update':   'Auto-update',
        'reset_demo':    '↺ Reset Demo',
        # --- new-posts banner ---
        'new_posts_0':      '↑ 0 new posts',
        'new_posts_one':    '↑ {n} new post',
        'new_posts_many':   '↑ {n} new posts',
        # --- report list ---
        'new_badge':     'NEW',
        'no_reports':    'No reports available.',
        'open':          'Open',
        'open_title':    'Open original post',
        'center':        'Center',
        'center_title':  'Center map on this report',
        'hide':          'Hide',
        'unhide':        'Unhide',
        'flag':          'Flag',
        'unflag':        'Unflag',
        'flag_title':    'Flag author',
        'unflag_title':  'Unflag author',
        'no_author_title': 'No author to flag',
        'geo_icon':          '📍',
        'geo_title':         'Georeferenced',
        'pending_icon':      '◎ ',
        'pending_title':     'Locations pending georeferencing',
        'no_loc_icon':       '· ',
        'no_loc_title':      'No locations',
        'georeference_title':'Click to georeference this location on the map',
        'reassign_title':    'Click to reassign location on the map',
        'remove_location':   'Remove location',
        'add_location':      '📍 Add',
        'add_location_title':'Click to place a location on the map',
        'restore_locations': '↩ Restore',
        'restore_title':     'Restore originally detected locations',
        # --- username modal ---
        'welcome':           'Welcome',
        'username_prompt':   'Enter your username to track your session state across browser refreshes.',
        'username_ph':       'Enter username…',
        'continue':          'Continue',
        'err_empty':         'Please enter a username.',
        'err_too_long':      'Username must be 64 characters or fewer.',
        # --- location pick overlay ---
        'pick_prompt':       '📍 Click on the map to place a location',
        'cancel':            'Cancel',
        'or':                'or',
        'search_osm_ph':     'Search OpenStreetMap…',
        'no_results':        'No results found.',
        # --- JS popup ---
        'js_open':         '↗ Open',
        'js_hide':         'Hide',
        'js_unhide':       'Unhide',
        'js_flag':         'Flag',
        'js_unflag':       'Unflag',
        'js_new':          'NEW',
        'js_reports_here': '{n} reports here',
    },
}

# Layer name translations: {en_name: {lang: translated_name}}
# Keys are the English names stored in the DB (from api_config.json "layer" fields).
LAYER_NAMES: dict[str, dict[str, str]] = {
    'Schools':              {'de': 'Schulen'},
    'Nursing Homes':        {'de': 'Pflegeeinrichtungen'},
    'Hospitals':            {'de': 'Krankenhäuser'},
    'Emergency Shelters':   {'de': 'Notunterkünfte'},
    'Fire Departments':     {'de': 'Feuerwehrstandorte'},
    'Main Dike':            {'de': 'Hauptdeichlinie'},
    'Water Rescue Points':  {'de': 'Wasserrettungspunkte'},
    'Flooding Areas':       {'de': 'Überschwemmungsgebiete'},
    'Train Stations':       {'de': 'Bahnhaltestellen'},
    'Bus Stops':            {'de': 'Bushaltestellen'},
    'Ferry Stops':          {'de': 'Fährhaltestellen'},
    'Events':               {'de': 'Ereignisse'},
    'Predictions':          {'de': 'Vorhersagen'},
}


def layer_name(lang: str, en_name: str) -> str:
    """Return translated layer name. DB stores English names; translate to DE when lang='de'."""
    if lang == 'en' or lang not in ('de',):
        return en_name
    return LAYER_NAMES.get(en_name, {}).get(lang, en_name)

DEFAULT_LANG = 'de'


def t(lang: str, key: str, **kwargs) -> str:
    """Return translated string for *key* in *lang*, falling back to DEFAULT_LANG then the key itself."""
    val = (
        TRANSLATIONS.get(lang, {}).get(key)
        or TRANSLATIONS[DEFAULT_LANG].get(key)
        or key
    )
    return val.format(**kwargs) if kwargs else val


def new_posts_label(lang: str, count: int) -> str:
    if count == 0:
        return t(lang, 'new_posts_0')
    return t(lang, 'new_posts_one' if count == 1 else 'new_posts_many', n=count)
