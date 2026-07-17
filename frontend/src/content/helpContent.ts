// Source content for the in-app manual (HelpModal). Kept separate from the
// short UI-chrome strings in i18n/*.json because this is prose, not labels.
// Mirrors docs/user-manual-de.md / docs/user-manual-en.md — if you change the
// structure here, update those files too.

export type HelpBlock =
  | { type: 'p'; text: string }
  | { type: 'steps'; items: string[] }
  | { type: 'list'; items: string[] }
  | { type: 'table'; rows: [string, string][] };

export interface HelpSection {
  icon: string;
  title: string;
  blocks: HelpBlock[];
}

export const HELP_CONTENT: Record<'de' | 'en', HelpSection[]> = {
  de: [
    {
      icon: '🗺️',
      title: 'Was ist die Lagekarte?',
      blocks: [
        {
          type: 'p',
          text: 'Die Lagekarte sammelt Meldungen aus sozialen Medien und RSS-Feeds zu einem Ereignis und zeigt sie auf einer Karte an, eingefärbt nach Relevanz. Links sehen Sie dieselben Meldungen als Liste.',
        },
      ],
    },
    {
      icon: '🚀',
      title: 'Erste Schritte',
      blocks: [
        {
          type: 'steps',
          items: [
            'Beim ersten Öffnen: Benutzernamen eingeben und „Weiter" klicken. Damit merkt sich die App, welche Meldungen Sie schon gesehen, ausgeblendet oder markiert haben – auch wenn Sie später wiederkommen.',
            'Karte (rechts) und Berichtsliste (links) füllen sich automatisch mit aktuellen Meldungen.',
            'Ein Klick auf eine Meldung in der Liste oder auf der Karte zeigt die Details.',
          ],
        },
      ],
    },
    {
      icon: '📍',
      title: 'Die Karte lesen',
      blocks: [
        {
          type: 'list',
          items: [
            'Farbige Punkte = Orte mit Meldungen. Farbe zeigt die Relevanz: Rot = Hoch, Orange = Mittel, Gelb = Niedrig, Grau = Keine.',
            'Eine Zahl auf einem Punkt bedeutet: mehrere Meldungen an diesem Ort. Anklicken öffnet eine Liste zur Auswahl.',
            'Ein weißes „!" auf einem Punkt bedeutet: mindestens eine noch nicht gesehene Meldung ist dabei.',
            'Klick auf einen Punkt öffnet die Details direkt auf der Karte: Text, Autor, Zeit sowie Buttons zum Öffnen, Zentrieren, Ausblenden und Markieren.',
            'Nach Auswahl einer Meldung erscheint oft eine blaue Fläche – das ist der tatsächliche Ort (z. B. ein Stadtteil), nicht nur ein Punkt.',
            'Liegt die ausgewählte Meldung außerhalb des sichtbaren Kartenausschnitts, zeigt ein orangener Pfeil am Kartenrand die Richtung. Anklicken zentriert die Karte dorthin.',
          ],
        },
      ],
    },
    {
      icon: '📋',
      title: 'Mit Berichten arbeiten',
      blocks: [
        {
          type: 'list',
          items: [
            'Die Liste links zeigt alle Meldungen, neueste zuerst. Die rote Zahl oben zählt ungesehene Meldungen.',
            'Ein Bericht anklicken markiert ihn automatisch als gesehen und wählt ihn aus (auf der Karte blau hervorgehoben). Die Karte bewegt sich dabei nicht von selbst dorthin – dafür gibt es den Button „Zentrieren".',
            '„Ausblenden" / „Einblenden": blendet eine einzelne Meldung aus der Liste aus, z. B. wenn sie irrelevant ist – sie wird nicht gelöscht.',
            '„Markieren" / „Entmarkieren": kennzeichnet alle Meldungen desselben Autors als auffällig, z. B. bei Verdacht auf Falschmeldungen. Nur möglich, wenn ein Autor bekannt ist.',
            '„📍 Hinzufügen" setzt oder korrigiert den Ort einer Meldung: entweder direkt auf der Karte klicken, oder über das Suchfeld einen Ort finden.',
            'Bereits gesetzte Orte lassen sich einzeln anpassen: Klick auf den Namen eines Ort-Tags ordnet ihn auf der Karte neu zu, Klick auf „✕" entfernt ihn. Nach einer Ortsänderung erscheint ein „↩ Wiederherstellen"-Button – er stellt die ursprünglich erkannten Orte wieder her.',
            'Die Leiste „↑ N neue Beiträge" oben in der Liste erscheint, wenn neue Meldungen eingetroffen sind. Anklicken blendet sie ein – oder „Autom. Aktualisierung" (oben rechts in der Liste) aktivieren, damit neue Meldungen automatisch übernommen werden.',
            'Der Button „Nur neue" unter dem Suchfeld schränkt die Liste auf noch nicht gesehene Meldungen ein.',
          ],
        },
      ],
    },
    {
      icon: '🔍',
      title: 'Filtern',
      blocks: [
        {
          type: 'list',
          items: [
            'Oben in der Filterleiste: Standort (verortet / ausstehend / keine), Relevanz, Zeitraum (1 Std., 6 Std., 1 Tag, 3 Tage, oder eigener Zeitraum), Typ (Themen-Chips wie „Verletzte & Tote" oder „Warnungen & Hinweise"), Ansicht (ausgeblendete Meldungen anzeigen sowie Markiert/Nicht markiert umschalten – „Nicht markiert" abwählen zeigt nur Meldungen markierter Autoren), Plattform und – falls vorhanden – Ebenen (z. B. Krankenhäuser, Schulen).',
            'Um die Karte auf ein Gebiet einzuschränken: „✏ Bereich" anklicken, Punkte auf der Karte setzen und die Fläche schließen. Nur Meldungen innerhalb der Fläche werden angezeigt. Schnellauswahl-Buttons: HH (Hamburg), DE (Deutschland), EU (Europa), Welt (alles anzeigen).',
            'Das Suchfeld in der Berichtsliste durchsucht den Text der Meldungen.',
          ],
        },
      ],
    },
    {
      icon: '📖',
      title: 'Kurzreferenz',
      blocks: [
        {
          type: 'table',
          rows: [
            ['📍 Verortet', 'Der Ort dieser Meldung ist bekannt und auf der Karte eingezeichnet.'],
            ['◎ Ausstehend', 'Ein möglicher Ort wurde erkannt, ist aber noch nicht bestätigt.'],
            ['∅ / · Keine', 'Kein Ort bekannt.'],
            ['Rot / Orange / Gelb / Grau', 'Relevanz: Hoch / Mittel / Niedrig / Keine.'],
            ['NEU', 'Neue, noch nicht gesehene Meldung.'],
            ['📌 Angeheftet', 'Über die Karte ausgewählte Meldung, die gerade nicht in der geladenen Liste steht.'],
          ],
        },
      ],
    },
    {
      icon: '❓',
      title: 'Häufige Fragen',
      blocks: [
        {
          type: 'list',
          items: [
            '„Ich sehe plötzlich keine Meldungen mehr" → Prüfen Sie die Filter oben, besonders Zeitraum und Kartenbereich – vermutlich ist einer davon zu eng eingestellt.',
            '„Meine gesehenen/markierten Meldungen sind weg" → Verwenden Sie denselben Benutzernamen wie beim letzten Mal; er verknüpft Ihren Status geräteübergreifend.',
            '„Wie ändere ich die Sprache?" → Hängen Sie ?lang=de oder ?lang=en an die Adresse in der Adressleiste an.',
            '„Was bedeutet Markieren genau?" → Es kennzeichnet den Autor, nicht nur den einen Beitrag – alle seine Meldungen erhalten einen orangenen Rand.',
          ],
        },
      ],
    },
  ],
  en: [
    {
      icon: '🗺️',
      title: 'What is this map?',
      blocks: [
        {
          type: 'p',
          text: 'The situational map collects reports about an event from social media and RSS feeds and shows them on a map, colored by relevance. The list on the left shows the same reports.',
        },
      ],
    },
    {
      icon: '🚀',
      title: 'Getting started',
      blocks: [
        {
          type: 'steps',
          items: [
            'The first time you open the app: enter a username and click "Continue". This lets the app remember which reports you\'ve seen, hidden, or flagged, even if you come back later.',
            'The map (right) and the report list (left) fill in automatically with current reports.',
            'Click a report in the list or on the map to see its details.',
          ],
        },
      ],
    },
    {
      icon: '📍',
      title: 'Reading the map',
      blocks: [
        {
          type: 'list',
          items: [
            'Colored dots = locations with reports. Color shows relevance: red = high, orange = medium, yellow = low, grey = none.',
            'A number on a dot means several reports share that location. Clicking it opens a list to choose from.',
            'A white "!" on a dot means at least one report there hasn\'t been seen yet.',
            'Clicking a dot opens its details right on the map: text, author, time, and buttons to open, center, hide, and flag.',
            'After you select a report, a blue shape often appears — that is the actual place (e.g. a district), not just a point.',
            'If the selected report is outside the visible map area, an orange arrow at the edge points toward it. Click it to center the map there.',
          ],
        },
      ],
    },
    {
      icon: '📋',
      title: 'Working with reports',
      blocks: [
        {
          type: 'list',
          items: [
            'The list on the left shows all reports, newest first. The red number at the top counts unseen reports.',
            'Clicking a report automatically marks it as seen and selects it (highlighted in blue on the map). The map doesn’t move there on its own – use the "Center" button for that.',
            '"Hide" / "Unhide": removes a single report from the list, e.g. if it\'s irrelevant — it is not deleted.',
            '"Flag" / "Unflag": marks every report from the same author as suspicious, e.g. if you suspect misinformation. Only available when an author is known.',
            '"📍 Add" sets or corrects a report\'s location: either click directly on the map, or find a place using the search box.',
            'Locations already set can be adjusted individually: click a location tag\'s name to re-pick it on the map, or click its "✕" to remove it. After you\'ve changed a report\'s locations, an "↩ Restore" button appears — it brings back the originally detected location(s).',
            'The "↑ N new posts" bar at the top of the list appears when new reports have arrived. Click it to bring them in — or turn on "Auto-update" (top-right of the list) so new reports merge in automatically.',
            'The "Only new" button below the search box narrows the list to reports you haven\'t seen yet.',
          ],
        },
      ],
    },
    {
      icon: '🔍',
      title: 'Filtering',
      blocks: [
        {
          type: 'list',
          items: [
            'At the top: Location (located / pending / none), Relevance, Time (1h, 6h, 1 day, 3 days, or a custom range), Type (topic chips like "Injured & Fatalities" or "Warnings & Notices"), View (show hidden reports, and toggle flagged/unflagged — uncheck "Unflagged" to see only reports from flagged authors), Platform, and — if available — Layers (e.g. hospitals, schools).',
            'To restrict the map to an area: click "✏ Area", place points on the map, and close the shape. Only reports inside it will show. Quick-select buttons: HH (Hamburg), DE (Germany), EU (Europe), World (show everything).',
            'The search box in the report list searches the text of the reports.',
          ],
        },
      ],
    },
    {
      icon: '📖',
      title: 'Quick reference',
      blocks: [
        {
          type: 'table',
          rows: [
            ['📍 Located', "This report's location is known and drawn on the map."],
            ['◎ Pending', 'A possible location was detected but not yet confirmed.'],
            ['∅ / · None', 'No location known.'],
            ['Red / Orange / Yellow / Grey', 'Relevance: High / Medium / Low / None.'],
            ['NEW', "New report that hasn't been seen yet."],
            ['📌 Pinned', "A report selected from the map that isn't currently in the loaded list."],
          ],
        },
      ],
    },
    {
      icon: '❓',
      title: 'Frequently asked questions',
      blocks: [
        {
          type: 'list',
          items: [
            '"I suddenly see no reports" → Check the filters at the top, especially the time range and the map area — one of them is probably set too narrow.',
            '"My seen/flagged reports are gone" → Use the same username as last time; it links your status across devices.',
            '"How do I change the language?" → Add ?lang=de or ?lang=en to the address in the browser\'s address bar.',
            '"What exactly does flagging do?" → It marks the author, not just that one post — every report from them gets an orange outline.',
          ],
        },
      ],
    },
  ],
};
