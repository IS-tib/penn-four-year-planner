/**
 * Reading the prerequisite graph in the browser.
 *
 * The server owns validation and always will: it is the only place a rule can
 * be enforced. What the browser needs the graph for is different and purely
 * presentational. It needs to shade the courses related to whichever one you
 * are looking at, and it needs to mark which terms a course could go in while
 * your finger is still on it, because waiting for a round trip to find that out
 * would be useless.
 *
 * These functions are pure and take everything they need as arguments, so they
 * can be tested without a browser or a server.
 */

export const RELATION = {
  FOCUS: "focus",
  PREREQUISITE: "prerequisite",
  DEPENDENT: "dependent",
  EQUIVALENT: "equivalent",
};

/** Lookup tables built once per catalog load. */
export function buildCourseIndex(courses) {
  const byId = new Map();
  const byCode = new Map();
  for (const course of courses) {
    byId.set(course.id, course);
    byCode.set(course.code, course);
  }
  return { byId, byCode };
}

/**
 * Expand a course code to itself plus anything cross-listed with it.
 *
 * A prerequisite naming CIS 4500 is equally satisfied by CIS 5500. The server
 * does this expansion too; doing it here as well is what stops the drag hint
 * from disagreeing with the answer that comes back.
 */
export function expandCodes(codes, index) {
  const expanded = new Set();
  for (const code of codes) {
    expanded.add(code);
    const course = index.byCode.get(code);
    for (const twin of course?.equivalent_codes ?? []) expanded.add(twin);
  }
  return expanded;
}

/**
 * How `other` relates to the course currently in focus.
 *
 * Returns null when they are unrelated, which is the common case and the one
 * the interface leaves alone.
 */
export function relationFor(focus, other, index) {
  if (!focus || !other) return null;
  if (focus.id === other.id) return RELATION.FOCUS;

  if ((focus.equivalent_codes ?? []).includes(other.code)) return RELATION.EQUIVALENT;

  const required = expandCodes(
    (focus.prerequisite_groups ?? []).flatMap((group) => group.codes),
    index,
  );
  if (required.has(other.code)) return RELATION.PREREQUISITE;

  if ((focus.unlocks_codes ?? []).includes(other.code)) return RELATION.DEPENDENT;

  return null;
}

/**
 * Which of the eight terms this course could legally sit in.
 *
 * `placementsByCode` maps a course code to the term it currently occupies. The
 * course being asked about is ignored, because moving a course is not blocked
 * by where it already is.
 */
export function legalTermsFor(course, placementsByCode, termCount, index) {
  const legal = [];
  const groups = course?.prerequisite_groups ?? [];
  const minTerm = course?.min_term_index ?? 0;

  for (let term = 0; term < termCount; term += 1) {
    if (term < minTerm) {
      legal.push(false);
      continue;
    }
    const satisfied = groups.every((group) => {
      const latestAllowed = group.concurrent ? term : term - 1;
      for (const code of expandCodes(group.codes, index)) {
        if (code === course.code) continue;
        const placed = placementsByCode.get(code);
        if (placed !== undefined && placed <= latestAllowed) return true;
      }
      return false;
    });
    legal.push(satisfied);
  }
  return legal;
}

/** code to term index, for every course currently in the plan. */
export function placementsByCode(plan) {
  const map = new Map();
  for (const entry of plan?.placements ?? []) {
    map.set(entry.course.code, entry.term_index);
  }
  return map;
}

/** The codes a plan's error diagnostics blame, for highlighting in the grid. */
export function flaggedCodes(plan) {
  const codes = new Set();
  for (const item of plan?.diagnostics ?? []) {
    if (item.severity === "error" && item.course_code) codes.add(item.course_code);
  }
  return codes;
}
