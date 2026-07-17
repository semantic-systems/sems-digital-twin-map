// Constants used by the onboarding tour that must not depend on any store or
// hook modules (to avoid circular import dependencies with useEffectiveFacetTotals).
// Defined here so they can be safely imported from hooks like useEffectiveFacetTotals.

export const EXAMPLE_IDENTIFIER = 'tour-example';

// CSS selector for the example card, scoped by its stable identifier rather
// than its (only known at fetch time) numeric id.
export const EXAMPLE_REPORT_SELECTOR = `[data-report-identifier="${EXAMPLE_IDENTIFIER}"]`;

/** Tight bounds around its first location (Hamburg), for the tour's "center" demo step. */
export const EXAMPLE_CENTER_BOUNDS: [[number, number], [number, number]] = [
  [53.5438 - 0.01, 9.9857 - 0.01],
  [53.5438 + 0.01, 9.9857 + 0.01],
];
