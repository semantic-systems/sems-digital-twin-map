// Source content for the interactive onboarding tour (see ../tour/tour.ts).
// Kept separate from the prose in helpContent.ts because these are short,
// single-element callouts, not manual sections.

import { EXAMPLE_REPORT_SELECTOR } from '../tour/constants';

export interface TourStepContent {
  title: string;
  text: string;
  /** CSS selector of the element to highlight; omit to center the step on screen. */
  attachTo?: string;
  on?: 'top' | 'bottom' | 'left' | 'right';
}

export const TOUR_CONTENT: Record<'de' | 'en', TourStepContent[]> = {
  de: [
    {
      title: '👋 Willkommen',
      text: 'Diese kurze Tour zeigt Ihnen die wichtigsten Funktionen der Lagekarte in unter einer Minute.',
    },
    {
      title: '🗺️ Die Karte',
      text: 'Rechts sehen Sie die Karte. Jeder farbige Punkt markiert einen Ort mit Meldungen.',
      attachTo: '[data-app-region="map"]',
      on: 'left',
    },
    {
      title: '📍 Ein Punkt auf der Karte',
      text: 'Damit Sie ihn gut sehen, ist die Karte automatisch dorthin gesprungen. Die Farbe zeigt die Relevanz: Rot = Hoch, Orange = Mittel, Gelb = Niedrig. Eine Zahl bedeutet: mehrere Meldungen an diesem Ort. Ein weißes „!" bedeutet: noch nicht gesehen. Klicken Sie einen Punkt für die Details.',
      attachTo: '[data-tour="tour-example-dot"]',
      on: 'right',
    },
    {
      title: '📋 Ein Beispielbericht',
      text: 'So sieht ein Bericht in der Liste aus: Autor, Plattform, Relevanz und Zeitpunkt auf einen Blick. Ein Klick markiert ihn als gesehen und hebt ihn auf der Karte hervor.',
      attachTo: EXAMPLE_REPORT_SELECTOR,
      on: 'right',
    },
    {
      title: '🛠️ Aktionen am Bericht',
      text: '„Öffnen" zeigt den Originalbeitrag. „Ausblenden" entfernt den Bericht aus der Liste, ohne ihn zu löschen. „Markieren" kennzeichnet den Autor als auffällig. „Zentrieren" zoomt die Karte so, dass alle Orte dieses Berichts auf einmal sichtbar sind. Gerade eben ist die Karte automatisch nur zu Hamburg gesprungen; der zweite Ort (Berlin) liegt außerhalb des sichtbaren Bereichs – der orangene Pfeil am Kartenrand zeigt die Richtung dorthin. Probieren Sie „Zentrieren" jetzt selbst aus, um beide Orte gleichzeitig zu sehen – die Karte reagiert wirklich.',
      attachTo: `${EXAMPLE_REPORT_SELECTOR} [data-tour="report-actions"]`,
      on: 'right',
    },
    {
      title: '📌 Ort setzen oder korrigieren',
      text: '„Hinzufügen" setzt oder korrigiert den Ort einer Meldung: entweder direkt auf der Karte klicken oder über die Suche einen Ort finden. Probieren Sie es aus — die Karte reagiert wirklich.',
      attachTo: `${EXAMPLE_REPORT_SELECTOR} [data-tour="report-add-location"]`,
      on: 'right',
    },
    {
      title: '🔎 Suchen & Filtern nach neu',
      text: 'Mit der Suche finden Sie Meldungen nach Stichwort. „Nur neue" blendet bereits gesehene Meldungen aus.',
      attachTo: '[data-tour="search-box"]',
      on: 'right',
    },
    {
      title: '🔄 Automatische Aktualisierung',
      text: '„Autom. Aktualisierung" ist standardmäßig aktiviert: Neue Meldungen werden automatisch in die Liste übernommen. Schalten Sie sie aus, wenn Sie lieber selbst entscheiden möchten, wann neue Beiträge erscheinen — dafür gibt es dann die Leiste „↑ N neue Beiträge".',
      attachTo: '[data-tour="auto-update-toggle"]',
      on: 'right',
    },
    {
      title: '🧭 Filterleiste',
      text: 'Hier schränken Sie die Anzeige ein: nach Standort, Relevanz, Zeitraum, Typ, Plattform und – falls vorhanden – Ebenen.',
      attachTo: '[data-app-region="filterbar"]',
      on: 'bottom',
    },
    {
      title: '❓ Noch Fragen?',
      text: 'Diese Tour und die vollständige Anleitung finden Sie jederzeit über diesen Button wieder.',
      attachTo: '[data-tour="help-button"]',
      on: 'bottom',
    },
  ],
  en: [
    {
      title: '👋 Welcome',
      text: 'This short tour shows you the main features of the situational map in under a minute.',
    },
    {
      title: '🗺️ The map',
      text: 'On the right is the map. Every colored dot marks a location with reports.',
      attachTo: '[data-app-region="map"]',
      on: 'left',
    },
    {
      title: '📍 A dot on the map',
      text: 'The map has automatically jumped there so you can see it clearly. Color shows relevance: red = high, orange = medium, yellow = low. A number means several reports share that location. A white "!" means at least one report there hasn\'t been seen yet. Click a dot to see its details.',
      attachTo: '[data-tour="tour-example-dot"]',
      on: 'right',
    },
    {
      title: '📋 An example report',
      text: 'This is what a report looks like in the list: author, platform, relevance and time at a glance. Clicking one marks it as seen and highlights it on the map.',
      attachTo: EXAMPLE_REPORT_SELECTOR,
      on: 'right',
    },
    {
      title: '🛠️ Report actions',
      text: '"Open" shows the original post. "Hide" removes it from the list without deleting it. "Flag" marks the author as suspicious. "Center" zooms the map so every location of this report is visible at once. Just now the map automatically jumped to Hamburg only; the second location (Berlin) is outside the visible area — the orange arrow at the map edge points toward it. Try "Center" yourself now to see both locations at the same time — the map really responds.',
      attachTo: `${EXAMPLE_REPORT_SELECTOR} [data-tour="report-actions"]`,
      on: 'right',
    },
    {
      title: '📌 Set or fix a location',
      text: '"Add" sets or corrects a report\'s location: either click directly on the map, or find a place using the search box. Try it — the map really responds.',
      attachTo: `${EXAMPLE_REPORT_SELECTOR} [data-tour="report-add-location"]`,
      on: 'right',
    },
    {
      title: '🔎 Search & filter to new',
      text: 'Use the search box to find reports by keyword. "Only new" hides reports you\'ve already seen.',
      attachTo: '[data-tour="search-box"]',
      on: 'right',
    },
    {
      title: '🔄 Auto-update',
      text: '"Auto-update" is on by default: new reports merge into the list automatically. Turn it off if you\'d rather decide yourself when new posts appear — that\'s what the "↑ N new posts" bar is for.',
      attachTo: '[data-tour="auto-update-toggle"]',
      on: 'right',
    },
    {
      title: '🧭 Filter bar',
      text: 'Narrow down what you see: by location, relevance, time range, type, platform, and — if available — layers.',
      attachTo: '[data-app-region="filterbar"]',
      on: 'bottom',
    },
    {
      title: '❓ Still have questions?',
      text: 'You can find this tour and the full manual again anytime via this button.',
      attachTo: '[data-tour="help-button"]',
      on: 'bottom',
    },
  ],
};
