import Shepherd from 'shepherd.js';
import { offset } from '@floating-ui/dom';
import { t, getLang } from '../i18n';
import { TOUR_CONTENT } from '../content/tourContent';
import { useReportStore } from '../store/useReportStore';
import { useMapStore } from '../store/useMapStore';
import { useUserStore } from '../store/useUserStore';
import { useTourStore } from '../store/useTourStore';
import { hideReport } from '../api/reports';
import { EXAMPLE_CENTER_BOUNDS } from './constants';
import { EXAMPLE_IDENTIFIER, loadExampleReport } from './exampleReport';

const SEEN_KEY = 'sems_tour_seen';

function isExampleStep(attachTo: string | undefined): boolean {
  return !!attachTo && attachTo.includes(EXAMPLE_IDENTIFIER);
}

export function hasSeenTour(): boolean {
  return localStorage.getItem(SEEN_KEY) === '1';
}

function markTourSeen(): void {
  localStorage.setItem(SEEN_KEY, '1');
}

/**
 * Builds and starts a fresh tour. Safe to call repeatedly (e.g. "replay" from
 * the help modal). Fetches the real, DB-backed example report first (see
 * exampleReport.ts) — every button on it is a genuine, working report action,
 * not a simulation, so there's nothing to special-case in ReportEntry/MapView.
 */
export async function startTour(): Promise<void> {
  // Guard against overlapping tours (e.g. a rapid second "Take a tour" click,
  // or React StrictMode double-invoking the auto-start effect in dev) — two
  // Shepherd tours running at once stack their DOM elements and each only
  // advances on its own clicks, which looks like the buttons are broken.
  if (Shepherd.activeTour) {
    Shepherd.activeTour.complete();
  }

  const username = useUserStore.getState().username;
  if (!username) return;

  let exampleReportId: number | null = null;
  try {
    const report = await loadExampleReport();
    exampleReportId = report.id;
    useReportStore.getState().addExampleReport(report);
    useTourStore.getState().setActiveExampleReportId(report.id);
  } catch (e) {
    console.error('Failed to load the tour example report:', e);
    // Fall through and run the tour anyway — the example steps simply won't
    // find their target and Shepherd will skip nothing automatically, but the
    // rest of the tour (map/sidebar/search/filters/help) still works fine.
  }

  const steps = TOUR_CONTENT[getLang()];

  const tour = new Shepherd.Tour({
    useModalOverlay: true,
    exitOnEsc: true,
    keyboardNavigation: true,
    defaultStepOptions: {
      classes: 'sems-tour-step',
      cancelIcon: { enabled: true },
      arrow: true,
      scrollTo: { behavior: 'smooth', block: 'center' },
      // Shepherd's own default middleware chain (flip + shift, no offset) places
      // the popover flush against the target — fine for a whole region like the
      // map, but it visually overlaps a small target like a single map dot.
      floatingUIOptions: { middleware: [offset(14)] },
    },
  });

  // Whatever report was selected before the tour took over the map — restored
  // once the example block ends, so the tour doesn't clobber the user's own
  // selection. `undefined` means "not captured yet" (distinct from a real `null`).
  let previousActiveReportId: number | null | undefined;

  // Restores whatever was selected before the example took over (or clears
  // selection if nothing was) — used when leaving the example block, so the
  // report itself can stay in the list (see removeExample) without staying
  // highlighted through the rest of the tour.
  const deselectExample = () => {
    if (exampleReportId === null) return;
    // Only restore if the example is still the active selection — if the user
    // clicked away to a real report mid-tour, leave their choice alone.
    if (useReportStore.getState().activeReportId === exampleReportId) {
      useReportStore.getState().setActiveReportId(previousActiveReportId ?? null);
    }
  };

  // Actually removes the example report — only on a real tour exit (complete/
  // cancel), not on leaving the example block. It stays in the list for the
  // rest of the tour (search/filter steps included) exactly like a real
  // report would; nothing about finishing the example explanation should make
  // it disappear.
  const removeExample = () => {
    if (exampleReportId === null) return;
    deselectExample();
    useReportStore.getState().removeExampleReport(exampleReportId);
    useTourStore.getState().setActiveExampleReportId(null);
  };

  // Clicking "Hide" on the example report is a real hide (see exampleReport.ts)
  // — the card genuinely disappears from the list (show-hidden defaults off),
  // which would strand whichever step is still trying to point at it. Un-hide
  // it automatically: shortly after the click, and unconditionally by the time
  // any later step in the example block is shown, so the tour is never stuck
  // pointing at a target that's gone.
  let hideResetTimer: number | null = null;
  const forceUnhideExample = () => {
    if (exampleReportId === null) return;
    const report = useReportStore.getState().reports.find((r) => r.id === exampleReportId);
    if (!report?.user_state.hide) return;
    useReportStore.getState().optimisticHide(exampleReportId, false);
    hideReport(exampleReportId, false).catch(() => {});
  };
  const unsubscribeHideWatch = useReportStore.subscribe((state) => {
    if (exampleReportId === null) return;
    const hidden = state.reports.find((r) => r.id === exampleReportId)?.user_state.hide;
    if (!hidden) return;
    if (hideResetTimer !== null) window.clearTimeout(hideResetTimer);
    hideResetTimer = window.setTimeout(forceUnhideExample, 1200);
  });

  // Mark as seen, and remove the example report, on any exit path (finished,
  // skipped via ✕, or Esc) so a tour cancelled mid-example doesn't leave a
  // stray report in the list, and so the tour never auto-starts again.
  const onExit = () => {
    markTourSeen();
    removeExample();
    unsubscribeHideWatch();
    if (hideResetTimer !== null) window.clearTimeout(hideResetTimer);
    useTourStore.getState().setDotStepActive(false);
  };
  tour.on('complete', onExit);
  tour.on('cancel', onExit);

  // The example block is always exactly 4 consecutive steps (see tourContent.ts):
  // dot → report card → report actions → set/fix location.
  const firstExampleIdx = steps.findIndex((s) => isExampleStep(s.attachTo));
  const lastExampleIdx = steps.reduce((last, s, i) => (isExampleStep(s.attachTo) ? i : last), -1);
  const dotStepIdx = firstExampleIdx; // demonstrate real "Center" + the offscreen arrow immediately
  const reportStepIdx = firstExampleIdx + 1; // select + highlight it, like a real click
  const actionsStepIdx = firstExampleIdx + 2; // map needs to be freely clickable here too (see below)
  // The map needs to be genuinely interactable — not just visible — on both of
  // these steps: "actions" explains Center/the arrow and invites clicking them
  // for real, "location" needs real map clicks to place a pin. Recomputed on
  // every step's `show` (not toggled per hide/show pair) so it's correct
  // regardless of navigation direction — Shepherd's `hide` handler has no way
  // to tell forward from backward, so tracking transitions there is fragile.
  const noOverlaySteps = new Set([actionsStepIdx, lastExampleIdx]);

  steps.forEach((step, i) => {
    const isFirst = i === 0;
    const isLast = i === steps.length - 1;
    const buttons = [
      ...(isFirst ? [] : [{ text: t('tour_back'), action: tour.back, secondary: true }]),
      {
        text: isLast ? t('tour_done') : t('tour_next'),
        action: isLast ? tour.complete : tour.next,
      },
    ];

    const when: { show?: () => void; hide?: () => void } = {};

    // Overlay visibility is decided fresh on every step's `show` (not toggled
    // per hide/show pair) so it's correct regardless of navigation direction
    // — Shepherd's `hide` handler has no way to tell forward from backward,
    // so tracking "was it on before" there is fragile. "actions" and
    // "location" both need the map genuinely clickable (not just visible):
    // "actions" invites actually clicking Center/the arrow it just
    // demonstrated, "location" needs real map clicks to place a pin. This
    // also sidesteps a Shepherd limitation where `extraHighlights` clips
    // every highlighted element's cutout against the *primary* target's
    // scroll-container bounds, not just its own — since these steps' targets
    // live inside the sidebar's scrollable list, trying to also cut out the
    // map that way left a grey, un-cut-out band across its top.
    when.show = () => {
      if (noOverlaySteps.has(i)) tour.modal?.hide();
      else tour.modal?.show();
    };

    if (isExampleStep(step.attachTo)) {
      const exampleShow = when.show;
      when.show = () => {
        exampleShow();
        if (exampleReportId === null) return;
        forceUnhideExample();
        if (i === dotStepIdx) {
          // Real "Center" behavior, demonstrated immediately: fit tightly to the
          // first location. The second location (Berlin) falls outside the
          // view, which is exactly what triggers the real offscreen-arrow
          // indicator once the report is selected on the next step.
          useMapStore.getState().requestFitBounds(EXAMPLE_CENTER_BOUNDS);
          useTourStore.getState().setDotStepActive(true);
        }
        if (i >= reportStepIdx) {
          if (previousActiveReportId === undefined) {
            const current = useReportStore.getState().activeReportId;
            previousActiveReportId = current === exampleReportId ? null : current;
          }
          const select = () => useReportStore.getState().setActiveReportId(exampleReportId);
          if (i === reportStepIdx) {
            // If the user clicked the dot on the previous step, its Leaflet
            // popup is still closing right now (see the dot step's `hide`
            // below) — that close fires an async 'popupclose' event whose own
            // handler deselects the report (Leaflet, not us). Selecting here
            // synchronously would just lose that race. A tick is enough to
            // land after it.
            window.setTimeout(select, 50);
          } else {
            select();
          }
        }
      };
      if (i === dotStepIdx) {
        // The tour invites clicking the dot ("Click a dot to see its
        // details"), which opens a real Leaflet popup. Nothing else ever
        // closes it — advancing (or going back) past this step would
        // otherwise leave it orphaned over the map, competing with whatever
        // the next step is trying to highlight.
        when.hide = () => {
          useTourStore.getState().setDotStepActive(false);
          useMapStore.getState().requestClosePopup();
        };
      }
      if (i === lastExampleIdx) {
        when.hide = deselectExample;
      }
    }

    tour.addStep({
      title: step.title,
      text: step.text,
      attachTo: step.attachTo ? { element: step.attachTo, on: step.on ?? 'bottom' } : undefined,
      when: Object.keys(when).length ? when : undefined,
      buttons,
    });
  });

  tour.start();
}

// Module-scoped (not component-scoped) so it survives React StrictMode's
// mount→unmount→mount dev cycle and still only schedules the auto-start once.
let autoStartScheduled = false;

/** Auto-starts the tour once per browser, if the anchor elements are already on screen. */
export function maybeAutoStartTour(): void {
  if (hasSeenTour() || autoStartScheduled) return;
  autoStartScheduled = true;
  // Give the initial render (map, sidebar, filter bar) a moment to settle so
  // the tour's attachTo selectors resolve to real, positioned elements.
  window.setTimeout(() => {
    if (hasSeenTour()) return;
    void startTour();
  }, 800);
}
