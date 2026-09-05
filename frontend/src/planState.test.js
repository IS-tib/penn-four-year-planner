import { describe, expect, it } from "vitest";

import {
  applyLocally,
  emptyHistory,
  pushHistory,
  sameSnapshot,
  snapshotOf,
  stepBack,
  stepForward,
} from "./planState.js";

const CIS1200 = { id: 1, code: "CIS 1200", credits: 1 };
const CIS1600 = { id: 2, code: "CIS 1600", credits: 1 };
const PHYS0150 = { id: 3, code: "PHYS 0150", credits: 1.5 };
const TECH1 = { id: 4, code: "TECH-1", credits: 1 };
const CIS5450 = { id: 5, code: "CIS 5450", credits: 1 };

const coursesById = new Map(
  [CIS1200, CIS1600, PHYS0150, TECH1, CIS5450].map((course) => [course.id, course]),
);

function planWith(placements) {
  return {
    id: 1,
    name: "Test",
    terms: [0, 1, 2].map((index) => ({
      index,
      label: `Term ${index}`,
      credits: 0,
      course_ids: [],
    })),
    placements,
    total_planned_credits: 0,
    diagnostics: [],
  };
}

const placed = (course, term) => ({ course_id: course.id, term_index: term, course });

describe("applyLocally", () => {
  it("places a course and updates that term's total", () => {
    const next = applyLocally(planWith([]), coursesById, {
      type: "place",
      courseId: CIS1200.id,
      termIndex: 1,
    });
    expect(next.placements).toHaveLength(1);
    expect(next.terms[1].credits).toBe(1);
    expect(next.terms[1].course_ids).toEqual([CIS1200.id]);
    expect(next.total_planned_credits).toBe(1);
  });

  it("moves a course between terms without changing the total", () => {
    const next = applyLocally(planWith([placed(CIS1200, 0)]), coursesById, {
      type: "move",
      courseId: CIS1200.id,
      termIndex: 2,
    });
    expect(next.terms[0].credits).toBe(0);
    expect(next.terms[2].credits).toBe(1);
    expect(next.total_planned_credits).toBe(1);
  });

  it("removes a course", () => {
    const next = applyLocally(planWith([placed(CIS1200, 0)]), coursesById, {
      type: "remove",
      courseId: CIS1200.id,
    });
    expect(next.placements).toEqual([]);
    expect(next.terms[0].credits).toBe(0);
  });

  it("swaps a course in place, keeping the term", () => {
    const next = applyLocally(planWith([placed(TECH1, 2)]), coursesById, {
      type: "swap",
      courseId: TECH1.id,
      replacementId: CIS5450.id,
    });
    expect(next.placements).toEqual([
      { course_id: CIS5450.id, term_index: 2, course: CIS5450 },
    ]);
  });

  it("keeps half-unit arithmetic exact", () => {
    let next = applyLocally(planWith([]), coursesById, {
      type: "place",
      courseId: PHYS0150.id,
      termIndex: 0,
    });
    next = applyLocally(next, coursesById, {
      type: "place",
      courseId: CIS1200.id,
      termIndex: 0,
    });
    expect(next.terms[0].credits).toBe(2.5);
  });

  it("sorts the courses inside a term by code", () => {
    let next = applyLocally(planWith([]), coursesById, {
      type: "place",
      courseId: PHYS0150.id,
      termIndex: 0,
    });
    next = applyLocally(next, coursesById, {
      type: "place",
      courseId: CIS1600.id,
      termIndex: 0,
    });
    expect(next.terms[0].course_ids).toEqual([CIS1600.id, PHYS0150.id]);
  });

  it("ignores a course that is not in the catalog", () => {
    const plan = planWith([]);
    expect(applyLocally(plan, coursesById, { type: "place", courseId: 999, termIndex: 0 }))
      .toBe(plan);
  });

  it("leaves a null plan alone", () => {
    expect(applyLocally(null, coursesById, { type: "remove", courseId: 1 })).toBeNull();
  });
});

describe("snapshots", () => {
  it("reduces a plan to course ids and terms", () => {
    expect(snapshotOf(planWith([placed(CIS1200, 0), placed(CIS1600, 2)]))).toEqual([
      { course_id: 1, term_index: 0 },
      { course_id: 2, term_index: 2 },
    ]);
  });

  it("compares snapshots regardless of order", () => {
    const a = [{ course_id: 1, term_index: 0 }, { course_id: 2, term_index: 1 }];
    const b = [{ course_id: 2, term_index: 1 }, { course_id: 1, term_index: 0 }];
    expect(sameSnapshot(a, b)).toBe(true);
  });

  it("notices a different term", () => {
    const a = [{ course_id: 1, term_index: 0 }];
    const b = [{ course_id: 1, term_index: 1 }];
    expect(sameSnapshot(a, b)).toBe(false);
  });
});

describe("history", () => {
  const first = [{ course_id: 1, term_index: 0 }];
  const second = [{ course_id: 1, term_index: 1 }];
  const third = [{ course_id: 1, term_index: 2 }];

  it("undo returns the previous state and makes it redoable", () => {
    let history = pushHistory(emptyHistory, first);
    const back = stepBack(history, second);
    expect(back.target).toEqual(first);
    expect(back.history.future).toEqual([second]);

    const forward = stepForward(back.history, first);
    expect(forward.target).toEqual(second);
  });

  it("has nothing to undo on a fresh history", () => {
    expect(stepBack(emptyHistory, first)).toBeNull();
    expect(stepForward(emptyHistory, first)).toBeNull();
  });

  it("a new edit discards the redo branch", () => {
    let history = pushHistory(emptyHistory, first);
    const back = stepBack(history, second);
    expect(back.history.future).toHaveLength(1);

    const afterEdit = pushHistory(back.history, third);
    expect(afterEdit.future).toEqual([]);
  });

  it("keeps the history bounded", () => {
    let history = emptyHistory;
    for (let index = 0; index < 60; index += 1) {
      history = pushHistory(history, [{ course_id: index, term_index: 0 }]);
    }
    expect(history.past).toHaveLength(40);
    // The oldest entries are the ones dropped.
    expect(history.past[0]).toEqual([{ course_id: 20, term_index: 0 }]);
  });
});
