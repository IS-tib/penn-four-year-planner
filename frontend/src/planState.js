/**
 * Local plan state: optimistic edits and the undo history.
 *
 * The server is the authority on what a plan means. These helpers exist so the
 * interface can show the result of a drag before the server has answered, and
 * so undo can be a single request instead of a replayed pile of inverses.
 */

/** The minimal shape the restore endpoint accepts. */
export function snapshotOf(plan) {
  return (plan?.placements ?? []).map((entry) => ({
    course_id: entry.course_id,
    term_index: entry.term_index,
  }));
}

export function sameSnapshot(left, right) {
  if (left.length !== right.length) return false;
  const key = (item) => `${item.course_id}:${item.term_index}`;
  const a = new Set(left.map(key));
  return right.every((item) => a.has(key(item)));
}

/**
 * Apply a placement change to the plan straight away.
 *
 * Diagnostics are deliberately not recomputed here. Working out whether a plan
 * is valid is the server's job, and a second implementation in the browser
 * would be a second thing to keep correct. What this does recompute is the
 * arithmetic the eye checks immediately: which term a card sits in and what
 * each term now totals.
 */
export function applyLocally(plan, coursesById, change) {
  if (!plan) return plan;

  let placements = plan.placements;
  if (change.type === "place") {
    const course = coursesById.get(change.courseId);
    if (!course) return plan;
    placements = [
      ...placements,
      { course_id: course.id, term_index: change.termIndex, course },
    ];
  } else if (change.type === "move") {
    placements = placements.map((entry) =>
      entry.course_id === change.courseId
        ? { ...entry, term_index: change.termIndex }
        : entry,
    );
  } else if (change.type === "remove") {
    placements = placements.filter((entry) => entry.course_id !== change.courseId);
  } else if (change.type === "swap") {
    const replacement = coursesById.get(change.replacementId);
    if (!replacement) return plan;
    placements = placements.map((entry) =>
      entry.course_id === change.courseId
        ? { course_id: replacement.id, term_index: entry.term_index, course: replacement }
        : entry,
    );
  } else {
    return plan;
  }

  const terms = plan.terms.map((term) => {
    const inTerm = placements.filter((entry) => entry.term_index === term.index);
    const credits = inTerm.reduce((total, entry) => total + entry.course.credits, 0);
    return {
      ...term,
      credits: round(credits),
      course_ids: inTerm
        .map((entry) => entry.course_id)
        .sort((a, b) => codeOf(placements, a).localeCompare(codeOf(placements, b))),
    };
  });

  return {
    ...plan,
    placements,
    terms,
    total_planned_credits: round(
      placements.reduce((total, entry) => total + entry.course.credits, 0),
    ),
  };
}

function codeOf(placements, courseId) {
  return placements.find((entry) => entry.course_id === courseId)?.course.code ?? "";
}

function round(value) {
  return Math.round(value * 100) / 100;
}

const HISTORY_LIMIT = 40;

export const emptyHistory = { past: [], future: [] };

/** Record a state the user can get back to, discarding any redo branch. */
export function pushHistory(history, snapshot) {
  const past = [...history.past, snapshot].slice(-HISTORY_LIMIT);
  return { past, future: [] };
}

/**
 * Step back one state. Returns the snapshot to restore and the new history, or
 * null when there is nothing to undo.
 */
export function stepBack(history, current) {
  if (history.past.length === 0) return null;
  const past = history.past.slice(0, -1);
  const target = history.past[history.past.length - 1];
  return {
    target,
    history: { past, future: [current, ...history.future].slice(0, HISTORY_LIMIT) },
  };
}

export function stepForward(history, current) {
  if (history.future.length === 0) return null;
  const [target, ...future] = history.future;
  return {
    target,
    history: { past: [...history.past, current].slice(-HISTORY_LIMIT), future },
  };
}
