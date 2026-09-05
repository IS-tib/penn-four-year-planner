import { useEffect, useMemo, useState } from "react";

import { api } from "../api.js";
import { buildCourseIndex, flaggedCodes, relationFor } from "../graph.js";
import { Diagnostics } from "./Diagnostics.jsx";
import { ProgressPanel } from "./ProgressPanel.jsx";
import { TermGrid } from "./TermGrid.jsx";

/**
 * A plan opened from a share link.
 *
 * No account, no token, no writes. It reuses the same grid component as the
 * editor with everything interactive switched off, so a shared plan looks
 * exactly like the real thing rather than like a degraded export.
 */
export function SharedPlan({ shareToken }) {
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState(null);
  const [focusedCode, setFocusedCode] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .sharedPlan(shareToken)
      .then((found) => {
        if (!cancelled) setPlan(found);
      })
      .catch((failure) => {
        if (!cancelled) setError(failure.message);
      });
    return () => {
      cancelled = true;
    };
  }, [shareToken]);

  const coursesById = useMemo(() => {
    const map = new Map();
    plan?.placements.forEach((entry) => map.set(entry.course_id, entry.course));
    return map;
  }, [plan]);

  const index = useMemo(
    () => buildCourseIndex([...coursesById.values()]),
    [coursesById],
  );
  const focused = focusedCode ? index.byCode.get(focusedCode) : null;

  if (error) {
    return (
      <div className="busy">
        <div style={{ textAlign: "center", maxWidth: "28rem" }}>
          <h1 style={{ marginBottom: "0.5rem" }}>Link not available</h1>
          <p>{error}</p>
          <p>
            <a className="btn" href={window.location.pathname}>
              Go to the planner
            </a>
          </p>
        </div>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="busy">
        <div>
          <div className="spinner" />
          Loading a shared plan
        </div>
      </div>
    );
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <strong>{plan.name}</strong>
          <span>shared by {plan.owner_name}</span>
        </div>
        <div className="topbar-spacer" />
        <div className="topbar-actions">
          <span className="read-only-badge">Read only</span>
          <button type="button" className="btn" onClick={() => window.print()}>
            Print
          </button>
          <a className="btn btn-primary" href={window.location.pathname}>
            Make your own
          </a>
        </div>
      </header>

      <main className="layout layout-shared">
        <TermGrid
          terms={plan.terms}
          coursesById={coursesById}
          flaggedCodes={flaggedCodes(plan)}
          limits={{ min: 4, max: 5.5 }}
          armed={false}
          readOnly
          focusedId={focused?.id ?? null}
          relationOf={(course) => relationFor(focused, course, index)}
          onFocus={(courseId) => {
            const course = coursesById.get(courseId);
            setFocusedCode((current) =>
              current === course?.code ? null : course?.code ?? null,
            );
          }}
          onDrop={() => {}}
          onSelectTerm={() => {}}
          onRemove={() => {}}
          onResolve={() => {}}
          onAdd={() => {}}
          onDragEnd={() => {}}
        />

        <div className="rail-right" style={{ display: "grid", gap: "1rem", alignContent: "start" }}>
          <Diagnostics diagnostics={plan.diagnostics} />
          <ProgressPanel
            progress={plan.progress}
            planned={plan.total_planned_credits}
            tracked={plan.degree_total_credits}
            published={plan.published_degree_credits}
          />
        </div>
      </main>
    </div>
  );
}
