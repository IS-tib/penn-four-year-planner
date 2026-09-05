import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api.js";
import { buildCourseIndex, flaggedCodes, relationFor } from "../graph.js";
import { Diagnostics } from "../components/Diagnostics.jsx";
import { TermGrid } from "../components/TermGrid.jsx";
import { useTheme } from "../theme.js";

/**
 * A plan opened from a share link.
 *
 * No account, no token, no writes. It reuses the same grid as the editor with
 * everything interactive switched off, so a shared plan looks like the real
 * thing rather than a degraded export.
 */
export function Shared() {
  const { token: shareToken } = useParams();
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState(null);
  const [focusedCode, setFocusedCode] = useState(null);
  useTheme();

  useEffect(() => {
    api.sharedPlan(shareToken).then(setPlan).catch((f) => setError(f.message));
  }, [shareToken]);

  const coursesById = useMemo(() => {
    const map = new Map();
    plan?.placements.forEach((entry) => map.set(entry.course_id, entry.course));
    return map;
  }, [plan]);

  const index = useMemo(() => buildCourseIndex([...coursesById.values()]), [coursesById]);
  const focused = focusedCode ? index.byCode.get(focusedCode) : null;

  if (error) {
    return (
      <div className="busy">
        <div className="empty-state" style={{ maxWidth: "32rem" }}>
          <h2>Link not available</h2>
          <p>{error}</p>
          <Link className="btn btn-primary" to="/">
            Go to the planner
          </Link>
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
    <div className="main">
      <header className="topbar">
        <h1>{plan.name}</h1>
        <span className="chip" data-tone="navy">
          {plan.program.name} {plan.program.degree}
        </span>
        <span className="small muted">shared by {plan.owner_name}</span>
        <div className="spacer" />
        <span className="read-only-badge">Read only</span>
        <button className="btn btn-sm" type="button" onClick={() => window.print()}>
          Print
        </button>
        <Link className="btn btn-sm btn-primary" to="/">
          Make your own
        </Link>
      </header>

      <main className="planner" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(15rem, 19rem)" }}>
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
            setFocusedCode((current) => (current === course?.code ? null : course?.code ?? null));
          }}
          onDrop={() => {}}
          onSelectTerm={() => {}}
          onRemove={() => {}}
          onResolve={() => {}}
          onAdd={() => {}}
          onDragEnd={() => {}}
        />

        <div className="rail rail-right">
          <Diagnostics diagnostics={plan.diagnostics} />
          <section className="panel" aria-label="Degree progress">
            <div className="panel-head">
              <h2>Degree</h2>
              <span className="count">{plan.program.degree}</span>
            </div>
            <div className="audit-summary">
              <div className="audit-headline">
                <strong>
                  {plan.audit.satisfied_count}/{plan.audit.requirement_count}
                </strong>
                <span className="small muted">requirements filled</span>
              </div>
              <div className="meter">
                <span
                  style={{
                    width: `${
                      plan.audit.requirement_count
                        ? (plan.audit.satisfied_count / plan.audit.requirement_count) * 100
                        : 0
                    }%`,
                  }}
                  data-done={plan.audit.complete}
                />
              </div>
              <p className="small muted">
                {plan.audit.credits_matched} of {plan.required_credits} course units counted.
              </p>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
