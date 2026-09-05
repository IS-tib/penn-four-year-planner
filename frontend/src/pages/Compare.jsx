import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { PlanChrome } from "../components/PlanChrome.jsx";
import { Toasts } from "../components/Toasts.jsx";
import { useToasts, usePlan } from "../usePlan.js";

/**
 * What switching majors would cost.
 *
 * This is the question a degree planner can answer and a semester scheduler
 * cannot, and it only works because requirements are data: the same plan is
 * re-audited against a different program's rules, and what falls out is the
 * set of courses that stop counting.
 */
export function Compare() {
  const { planId } = useParams();
  const { token } = useAuth();
  const { toasts, push } = useToasts();
  const { plan, loading } = usePlan(Number(planId), { toast: push });

  const [programs, setPrograms] = useState([]);
  const [target, setTarget] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.programs().then(setPrograms).catch((f) => push(f.message, "error"));
  }, [push]);

  useEffect(() => {
    if (!plan || !target) return;
    let cancelled = false;
    setBusy(true);
    api
      .switchTo(token, plan.id, target)
      .then((body) => {
        if (!cancelled) setResult(body);
      })
      .catch((failure) => {
        if (!cancelled) push(failure.message, "error");
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [plan, target, token, push]);

  const others = useMemo(
    () => programs.filter((program) => program.code !== plan?.program.code),
    [programs, plan],
  );

  if (loading || !plan) {
    return (
      <PlanChrome plan={null} planId={planId} title="Switch major">
        <div className="busy">
          <div>
            <div className="spinner" />
            Loading your plan
          </div>
        </div>
      </PlanChrome>
    );
  }

  return (
    <PlanChrome plan={plan} planId={planId} title="Switch major">
      <div className="page page-narrow stack" style={{ gap: "1.2rem" }}>
        <div className="page-head" style={{ marginBottom: 0 }}>
          <span className="eyebrow">What if</span>
          <h1>Switch out of {plan.program.name}</h1>
          <p>
            Your plan gets re-checked against another degree's requirements. Whatever
            still counts carries over, whatever does not becomes dead weight, and the
            gap tells you how far behind you would be.
          </p>
        </div>

        <section className="stack" style={{ gap: "0.6rem" }}>
          <span className="eyebrow">Switch to</span>
          <div className="grid-cards">
            {others.map((program) => (
              <button
                key={program.code}
                type="button"
                className="program-card"
                data-selected={target === program.code}
                onClick={() => setTarget(program.code)}
              >
                <span className="top">
                  <h3>{program.name}</h3>
                  <span className="degree">{program.degree}</span>
                </span>
                <span className="meta">{program.school}</span>
              </button>
            ))}
          </div>
        </section>

        {busy ? (
          <div className="busy" style={{ minHeight: "8rem" }}>
            <div>
              <div className="spinner" />
              Re-checking your plan
            </div>
          </div>
        ) : null}

        {result && !busy ? (
          <>
            <section className="verdict">
              <span className="eyebrow" style={{ color: "#9db2dc" }}>
                {result.program.name} {result.program.degree}
              </span>
              <h2>{result.verdict}</h2>
              <p>
                The estimate is a lower bound. Course-load capacity and prerequisite
                chain length limit progress independently, so the answer is whichever
                binds harder. Offerings and advisor approval are outside what the
                catalog prints.
              </p>
            </section>

            <section className="stat-row">
              <div className="stat" data-tone="ok">
                <b>{result.carried_credits}</b>
                <span>course units carry over</span>
              </div>
              <div className="stat" data-tone={result.wasted_credits > 0 ? "err" : undefined}>
                <b>{result.wasted_credits}</b>
                <span>stop counting</span>
              </div>
              <div className="stat">
                <b>{result.remaining_credits}</b>
                <span>still to take</span>
              </div>
              <div className="stat" data-tone={result.min_extra_terms > 0 ? "warn" : "ok"}>
                <b>{result.min_extra_terms}</b>
                <span>extra semesters, at least</span>
              </div>
            </section>

            <section className="compare-grid">
              <div className="panel" style={{ padding: "1rem 1.1rem" }}>
                <h3 style={{ marginBottom: "0.15rem" }}>Carries over</h3>
                <p className="small muted" style={{ marginBottom: "0.6rem" }}>
                  {result.carried_over.length} courses still count toward the new degree.
                </p>
                <div className="course-cloud">
                  {result.carried_over.map((course) => (
                    <span className="code-chip" data-tone="ok" key={course.id}>
                      {course.code}
                    </span>
                  ))}
                  {result.carried_over.length === 0 ? (
                    <span className="detail-empty">Nothing in this plan counts yet.</span>
                  ) : null}
                </div>
              </div>

              <div className="panel" style={{ padding: "1rem 1.1rem" }}>
                <h3 style={{ marginBottom: "0.15rem" }}>Stops counting</h3>
                <p className="small muted" style={{ marginBottom: "0.6rem" }}>
                  {result.wasted.length} courses no requirement of this degree accepts.
                </p>
                <div className="course-cloud">
                  {result.wasted.map((course) => (
                    <span className="code-chip" data-tone="err" key={course.id}>
                      {course.code}
                    </span>
                  ))}
                  {result.wasted.length === 0 ? (
                    <span className="detail-empty">Nothing would be wasted.</span>
                  ) : null}
                </div>
              </div>
            </section>

            <section className="panel" style={{ padding: "1rem 1.1rem" }}>
              <h3 style={{ marginBottom: "0.5rem" }}>How the estimate is built</h3>
              <div className="stat-row">
                <div className="stat">
                  <b>{result.free_capacity}</b>
                  <span>spare course units in your terms</span>
                </div>
                <div className="stat">
                  <b>{result.extra_terms_from_load}</b>
                  <span>extra terms from load</span>
                </div>
                <div className="stat">
                  <b>{result.longest_remaining_chain}</b>
                  <span>longest chain still ahead</span>
                </div>
                <div className="stat">
                  <b>{result.extra_terms_from_chain}</b>
                  <span>extra terms from chains</span>
                </div>
              </div>
              <p className="small muted" style={{ marginTop: "0.7rem" }}>
                A chain of five courses takes five terms no matter how light the load,
                and spare capacity cannot shorten it. Equally, a short chain does not
                create room under the credit cap. The reported figure is the larger.
              </p>
            </section>

            <section className="panel">
              <div className="panel-head">
                <h2>What would still be outstanding</h2>
                <span className="count">{result.outstanding} requirements</span>
              </div>
              {/* Grouped rather than one flat list of thirty rows: printing the
                  same heading against every row is how you turn a requirement
                  table into wallpaper. */}
              {result.audit.groups
                .map((group) => ({
                  group,
                  missing: group.requirements.filter((r) => !r.satisfied),
                }))
                .filter(({ missing }) => missing.length > 0)
                .map(({ group, missing }) => (
                  <details className="req-group" key={group.position} open>
                    <summary>
                      <span className="caret" aria-hidden="true">
                        &#9654;
                      </span>
                      <span className="chip">{missing.length}</span>
                      {group.name}
                      <span className="spacer" />
                      <span className="small muted tabular">still missing</span>
                    </summary>
                    <div className="req-list">
                      {missing.map((requirement) => (
                        <div className="req" key={requirement.id} data-satisfied="false">
                          <span className="tick" aria-hidden="true">
                            &#10003;
                          </span>
                          <span className="label">
                            <span>{requirement.label}</span>
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
          </>
        ) : null}

        {!target ? (
          <div className="empty-state">
            <h2>Pick a degree above</h2>
            <p>
              Nothing changes in your plan. This only asks what would happen, so you can
              compare as many as you like.
            </p>
          </div>
        ) : null}
      </div>

      <Toasts toasts={toasts} />
    </PlanChrome>
  );
}
