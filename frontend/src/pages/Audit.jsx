import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";

import { PlanChrome } from "../components/PlanChrome.jsx";
import { Toasts } from "../components/Toasts.jsx";
import { useToasts, usePlan } from "../usePlan.js";

/**
 * The degree audit, shown as the catalog's own table with ticks against it.
 *
 * The numbers here come from a matching, not a sum, so a course appears under
 * exactly one requirement. Seeing which one is the point: a student who cannot
 * tell what a course is paying for cannot tell what is still missing.
 */
export function Audit() {
  const { planId } = useParams();
  const { toasts, push } = useToasts();
  const { plan, coursesById, loading, error } = usePlan(Number(planId), { toast: push });

  const unassigned = useMemo(() => {
    if (!plan) return [];
    return plan.audit.unassigned_course_ids
      .map((id) => coursesById.get(id))
      .filter(Boolean);
  }, [plan, coursesById]);

  if (loading || !plan) {
    return (
      <PlanChrome plan={null} planId={planId} title="Degree audit">
        <div className="busy">
          {error ? <p>{error}</p> : (
            <div>
              <div className="spinner" />
              Loading the audit
            </div>
          )}
        </div>
      </PlanChrome>
    );
  }

  const { audit, program } = plan;
  const percent = audit.requirement_count
    ? (audit.satisfied_count / audit.requirement_count) * 100
    : 0;
  const extra = Math.round((audit.credits_planned - audit.credits_matched) * 100) / 100;

  return (
    <PlanChrome plan={plan} planId={planId} title="Degree audit">
      <div className="page page-narrow stack" style={{ gap: "1.2rem" }}>
        <div className="page-head" style={{ marginBottom: 0 }}>
          <span className="eyebrow">{program.school}</span>
          <h1>
            {program.name} {program.degree}
          </h1>
          <p>{program.notes}</p>
        </div>

        <section className="stat-row">
          <div className="stat" data-tone={audit.complete ? "ok" : undefined}>
            <b>
              {audit.satisfied_count}/{audit.requirement_count}
            </b>
            <span>requirements filled</span>
          </div>
          <div className="stat">
            <b>{audit.credits_matched}</b>
            <span>counted course units</span>
          </div>
          <div className="stat">
            <b>{plan.required_credits}</b>
            <span>the degree needs</span>
          </div>
          <div className="stat" data-tone={extra > 0 ? "warn" : undefined}>
            <b>{extra}</b>
            <span>extra prerequisite units</span>
          </div>
        </section>

        <div className="meter" role="img" aria-label={`${Math.round(percent)} percent complete`}>
          <span style={{ width: `${percent}%` }} data-done={audit.complete} />
        </div>

        {extra > 0 ? (
          <p className="small muted">
            The requirement table does not list every course you have to take. Chains
            like CIS 3200 needing CIS 2620 add units that no single row asks for, which
            is why a finished plan can exceed the printed total.
          </p>
        ) : null}

        <section className="panel">
          <div className="panel-head">
            <h2>Requirements</h2>
            <span className="count">
              <a href={program.source_url} target="_blank" rel="noreferrer">
                catalog source
              </a>
            </span>
          </div>

          {audit.groups.map((group) => (
            <details className="req-group" key={group.position} open>
              <summary>
                <span className="caret" aria-hidden="true">
                  &#9654;
                </span>
                <span
                  className="chip"
                  data-tone={group.satisfied ? "ok" : undefined}
                  aria-hidden="true"
                >
                  {group.requirements.filter((r) => r.satisfied).length}/
                  {group.requirements.length}
                </span>
                {group.name}
                <span className="spacer" />
                <span className="small muted tabular">{group.credits} CU</span>
              </summary>

              <div className="req-list">
                {group.notes ? <p className="detail-empty">{group.notes}</p> : null}
                {group.requirements.map((requirement) => (
                  <div className="req" key={requirement.id} data-satisfied={requirement.satisfied}>
                    <span className="tick" aria-hidden="true">
                      &#10003;
                    </span>
                    <span className="label">
                      <span>{requirement.label}</span>
                      {/* Most rows are named for one course, and printing
                          "CIS 1100" under "CIS 1100" is noise. The line only
                          earns its place where it says something the label does
                          not: which of several options was spent here. */}
                      {matchedLine(requirement, coursesById)}
                      {requirement.notes ? (
                        <span className="detail-empty">{requirement.notes}</span>
                      ) : null}
                    </span>
                    <span className="filled tabular">
                      {requirement.slots > 1
                        ? `${requirement.filled_slots}/${requirement.slots}`
                        : `${requirement.credits} CU`}
                    </span>
                  </div>
                ))}
              </div>
            </details>
          ))}
        </section>

        {unassigned.length > 0 ? (
          <section className="panel" style={{ padding: "1rem 1.1rem" }}>
            <h2 style={{ fontSize: "1rem", marginBottom: "0.4rem" }}>
              Counting toward nothing
            </h2>
            <p className="small muted" style={{ marginBottom: "0.6rem" }}>
              These are in the plan but no requirement of this degree accepts them.
              Often that is fine, because they are prerequisites for something that
              does count.
            </p>
            <div className="course-cloud">
              {unassigned.map((course) => (
                <span className="code-chip" key={course.id}>
                  {course.code}
                </span>
              ))}
            </div>
          </section>
        ) : null}

        <p className="small muted">
          A planning aid, not an official degree audit.{" "}
          <Link to={`/programs/${program.code}`}>See the full requirement list</Link>.
        </p>
      </div>

      <Toasts toasts={toasts} />
    </PlanChrome>
  );
}

function matchedLine(requirement, coursesById) {
  const codes = requirement.matched_course_ids.map((id) => coursesById.get(id)?.code ?? "?");
  if (codes.length === 0) return <span className="matched muted">nothing yet</span>;
  const joined = codes.join(", ");
  if (joined === requirement.label) return null;
  return <span className="matched">{joined}</span>;
}
