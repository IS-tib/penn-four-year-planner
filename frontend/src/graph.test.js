import { describe, expect, it } from "vitest";

import {
  RELATION,
  buildCourseIndex,
  expandCodes,
  legalTermsFor,
  relationFor,
} from "./graph.js";

function course(id, code, options = {}) {
  return {
    id,
    code,
    title: code,
    credits: 1,
    category: "CIS Core",
    min_term_index: 0,
    prerequisite_groups: [],
    unlocks_codes: [],
    equivalent_codes: [],
    ...options,
  };
}

const CIS1200 = course(1, "CIS 1200", { unlocks_codes: ["CIS 1210", "CIS 2400"] });
const CIS1600 = course(2, "CIS 1600", { unlocks_codes: ["CIS 1210"] });
const CIS1210 = course(3, "CIS 1210", {
  prerequisite_groups: [
    { codes: ["CIS 1200"], concurrent: false },
    { codes: ["CIS 1600"], concurrent: false },
  ],
});
const MATH1410 = course(4, "MATH 1410");
const MATH1610 = course(5, "MATH 1610");
const MATH2400 = course(6, "MATH 2400", {
  prerequisite_groups: [{ codes: ["MATH 1410", "MATH 1610"], concurrent: false }],
});
const MATH1400 = course(7, "MATH 1400");
const PHYS0150 = course(8, "PHYS 0150", {
  credits: 1.5,
  prerequisite_groups: [{ codes: ["MATH 1400"], concurrent: true }],
});
const CIS4480 = course(9, "CIS 4480", { equivalent_codes: ["CIS 5480"] });
const CIS5480 = course(10, "CIS 5480", { equivalent_codes: ["CIS 4480"] });
const NEEDS4480 = course(11, "CIS 9999", {
  prerequisite_groups: [{ codes: ["CIS 4480"], concurrent: false }],
});
const SENIOR = course(12, "CIS 4000", { min_term_index: 6 });

const index = buildCourseIndex([
  CIS1200, CIS1600, CIS1210, MATH1410, MATH1610, MATH2400,
  MATH1400, PHYS0150, CIS4480, CIS5480, NEEDS4480, SENIOR,
]);

describe("expandCodes", () => {
  it("adds cross-listed numbers", () => {
    expect([...expandCodes(["CIS 4480"], index)].sort()).toEqual(["CIS 4480", "CIS 5480"]);
  });

  it("leaves a course with no twin alone", () => {
    expect([...expandCodes(["CIS 1200"], index)]).toEqual(["CIS 1200"]);
  });

  it("ignores a code that is not in the catalog", () => {
    expect([...expandCodes(["NOPE 0000"], index)]).toEqual(["NOPE 0000"]);
  });
});

describe("relationFor", () => {
  it("identifies the focused course itself", () => {
    expect(relationFor(CIS1210, CIS1210, index)).toBe(RELATION.FOCUS);
  });

  it("identifies a prerequisite of the focused course", () => {
    expect(relationFor(CIS1210, CIS1200, index)).toBe(RELATION.PREREQUISITE);
    expect(relationFor(CIS1210, CIS1600, index)).toBe(RELATION.PREREQUISITE);
  });

  it("identifies a course that depends on the focused one", () => {
    expect(relationFor(CIS1200, CIS1210, index)).toBe(RELATION.DEPENDENT);
  });

  it("identifies a cross-listed number", () => {
    expect(relationFor(CIS4480, CIS5480, index)).toBe(RELATION.EQUIVALENT);
  });

  it("counts every member of an or-group as a prerequisite", () => {
    expect(relationFor(MATH2400, MATH1410, index)).toBe(RELATION.PREREQUISITE);
    expect(relationFor(MATH2400, MATH1610, index)).toBe(RELATION.PREREQUISITE);
  });

  it("treats a cross-listed twin of a prerequisite as a prerequisite", () => {
    expect(relationFor(NEEDS4480, CIS5480, index)).toBe(RELATION.PREREQUISITE);
  });

  it("returns null for unrelated courses", () => {
    expect(relationFor(CIS1200, MATH1410, index)).toBeNull();
  });

  it("returns null when nothing is focused", () => {
    expect(relationFor(null, CIS1200, index)).toBeNull();
  });
});

describe("legalTermsFor", () => {
  it("allows anything anywhere when there are no prerequisites", () => {
    expect(legalTermsFor(CIS1200, new Map(), 4, index)).toEqual([true, true, true, true]);
  });

  it("blocks every term while a prerequisite is unplanned", () => {
    expect(legalTermsFor(CIS1210, new Map([["CIS 1200", 0]]), 4, index)).toEqual([
      false, false, false, false,
    ]);
  });

  it("opens the terms after the last prerequisite", () => {
    const placed = new Map([
      ["CIS 1200", 0],
      ["CIS 1600", 2],
    ]);
    expect(legalTermsFor(CIS1210, placed, 5, index)).toEqual([
      false, false, false, true, true,
    ]);
  });

  it("is satisfied by either side of an or-group", () => {
    expect(legalTermsFor(MATH2400, new Map([["MATH 1610", 1]]), 4, index)).toEqual([
      false, false, true, true,
    ]);
  });

  it("lets a concurrent prerequisite share its term", () => {
    expect(legalTermsFor(PHYS0150, new Map([["MATH 1400", 1]]), 4, index)).toEqual([
      false, true, true, true,
    ]);
  });

  it("accepts a cross-listed twin as the prerequisite", () => {
    expect(legalTermsFor(NEEDS4480, new Map([["CIS 5480", 0]]), 3, index)).toEqual([
      false, true, true,
    ]);
  });

  it("respects a class-standing minimum", () => {
    expect(legalTermsFor(SENIOR, new Map(), 8, index)).toEqual([
      false, false, false, false, false, false, true, true,
    ]);
  });

  it("does not let a course block its own move", () => {
    // CIS 1210 is currently in term 3. Asking where it may go must not treat
    // its own placement as satisfying anything.
    const placed = new Map([
      ["CIS 1200", 0],
      ["CIS 1600", 0],
      ["CIS 1210", 3],
    ]);
    expect(legalTermsFor(CIS1210, placed, 4, index)).toEqual([false, true, true, true]);
  });
});
