import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, downloadCsv } from "../api.js";
import { useAuth } from "../auth.jsx";
import { legalTermsFor, placementsByCode, relationFor } from "../graph.js";
import { Catalog } from "../components/Catalog.jsx";
import { CourseDetail } from "../components/CourseDetail.jsx";
import { CoursePicker } from "../components/CoursePicker.jsx";
import { Diagnostics } from "../components/Diagnostics.jsx";
import { PlanChrome } from "../components/PlanChrome.jsx";
import { ShareDialog } from "../components/ShareDialog.jsx";
import { TermGrid } from "../components/TermGrid.jsx";
import { Toasts } from "../components/Toasts.jsx";
import { useToasts, usePlan } from "../usePlan.js";

export function Planner() {
  const { planId } = useParams();
  const { token } = useAuth();
  const { toasts, push } = useToasts();
  const state = usePlan(Number(planId), { toast: push });
  const {
    plan, coursesById, courses, index, placedIds, flagged,
    loading, working, error, mutate, runBulk, undo, redo, canUndo, canRedo,
  } = state;

  const [limits, setLimits] = useState({ min: 4, max: 5.5 });
  const [selectedCourseId, setSelectedCourseId] = useState(null);
  const [focusedCourseId, setFocusedCourseId] = useState(null);
  const [draggingId, setDraggingId] = useState(null);
  const [leavingId, setLeavingId] = useState(null);
  const [picker, setPicker] = useState(null);
  const [sharing, setSharing] = useState(false);

  useEffect(() => {
    api
      .limits()
      .then((body) => setLimits({ min: body.min_term_credits, max: body.max_term_credits }))
      .catch(() => {});
  }, []);

  const focusedCourse = focusedCourseId ? coursesById.get(focusedCourseId) : null;
  const relationOf = useCallback(
    (course) => relationFor(focusedCourse, course, index),
    [focusedCourse, index],
  );

  // While a course is being dragged, work out which terms could legally take
  // it. This is only a hint for the cursor; the server still validates.
  const legality = useMemo(() => {
    if (draggingId === null || !plan) return null;
    const course = coursesById.get(draggingId);
    if (!course) return null;
    return legalTermsFor(course, placementsByCode(plan), plan.terms.length, index);
  }, [draggingId, plan, coursesById, index]);

  const termLabels = useMemo(() => (plan?.terms ?? []).map((t) => t.label), [plan]);
  const relevantIds = useMemo(
    () => (plan ? new Set(plan.relevant_course_ids) : null),
    [plan],
  );

  const placeCourse = useCallback(
    (courseId, termIndex) => {
      if (courseId === null || courseId === undefined) return;
      if (placedIds.has(courseId)) {
        const existing = plan.placements.find((entry) => entry.course_id === courseId);
        if (existing?.term_index === termIndex) return;
        mutate({ type: "move", courseId, termIndex }, () =>
          api.moveCourse(token, plan.id, courseId, termIndex),
        );
      } else {
        mutate({ type: "place", courseId, termIndex }, () =>
          api.placeCourse(token, plan.id, courseId, termIndex),
        );
      }
      setSelectedCourseId(null);
    },
    [mutate, placedIds, plan, token],
  );

  const removeCourse = useCallback(
    (courseId) => {
      // Let the exit animation play before the row actually leaves the list.
      setLeavingId(courseId);
      window.setTimeout(() => {
        setLeavingId(null);
        mutate({ type: "remove", courseId }, () => api.removeCourse(token, plan.id, courseId));
      }, 160);
    },
    [mutate, token, plan],
  );

  const focusByCode = useCallback(
    (code) => {
      const course = index.byCode.get(code);
      if (!course) return;
      setFocusedCourseId(course.id);
      window.requestAnimationFrame(() => {
        const node = document.querySelector(
          `.term .course[data-course-code="${CSS.escape(code)}"]`,
        );
        if (!node) return;
        node.scrollIntoView({ behavior: "smooth", block: "center" });
        node.classList.remove("flash");
        // Reading offsetWidth forces a reflow, which is what lets the same
        // animation replay when the same course is selected twice.
        void node.offsetWidth;
        node.classList.add("flash");
      });
    },
    [index],
  );

  useEffect(() => {
    function onKeyDown(event) {
      const target = event.target;
      const typing =
        target instanceof HTMLElement &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if (typing) return;

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) redo();
        else undo();
      } else if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "y") {
        event.preventDefault();
        redo();
      } else if (event.key === "Escape") {
        setSelectedCourseId(null);
        setFocusedCourseId(null);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [undo, redo]);

  function handleDragStart(event, courseId, fromTerm) {
    event.dataTransfer.setData("application/x-course", JSON.stringify({ courseId, fromTerm }));
    event.dataTransfer.effectAllowed = "move";
    setDraggingId(courseId);
    setSelectedCourseId(null);
  }

  function handleDrop(courseId, fromTerm, termIndex) {
    setDraggingId(null);
    if (fromTerm === termIndex) return;
    placeCourse(courseId, termIndex);
  }

  async function handlePickerChoice(row) {
    const current = picker;
    setPicker(null);
    if (!current) return;
    if (current.mode === "swap") {
      await mutate(
        { type: "swap", courseId: current.slot.id, replacementId: row.course_id },
        () => api.swapCourse(token, plan.id, current.slot.id, row.course_id),
      );
    } else {
      await mutate({ type: "place", courseId: row.course_id, termIndex: current.termIndex }, () =>
        api.placeCourse(token, plan.id, row.course_id, current.termIndex),
      );
    }
    if (row.would_overload) {
      push(`${row.code} puts that term over the ${limits.max} CU load limit.`);
    }
  }

  if (loading) {
    return (
      <PlanChrome plan={null} planId={planId} title="Loading">
        <div className="busy">
          <div>
            <div className="spinner" />
            Loading your plan
          </div>
        </div>
      </PlanChrome>
    );
  }

  if (error || !plan) {
    return (
      <PlanChrome plan={null} planId={planId} title="Not available">
        <div className="page page-narrow">
          <div className="empty-state">
            <h2>That plan is not available</h2>
            <p>{error ?? "It may have been deleted, or it belongs to another account."}</p>
          </div>
        </div>
      </PlanChrome>
    );
  }

  return (
    <PlanChrome
      plan={plan}
      planId={planId}
      onRename={async (name) => {
        try {
          state.setPlan(await api.renamePlan(token, plan.id, name));
        } catch (failure) {
          push(failure.message, "error");
        }
      }}
      actions={
        <>
          <div className="btn-group">
            <button className="btn btn-sm" type="button" onClick={undo}
              disabled={working || !canUndo} title="Undo (Ctrl+Z)" aria-label="Undo">
              Undo
            </button>
            <button className="btn btn-sm" type="button" onClick={redo}
              disabled={working || !canRedo} title="Redo (Ctrl+Shift+Z)" aria-label="Redo">
              Redo
            </button>
          </div>
          <button className="btn btn-sm" type="button" disabled={working}
            onClick={() =>
              runBulk(
                () => api.autofill(token, plan.id),
                "Filled in the rest of the degree around what you had already placed.",
              )
            }>
            Autofill
          </button>
          <button className="btn btn-sm" type="button" onClick={() => setSharing(true)}
            data-active={Boolean(plan.share_token)}>
            Share
          </button>
          <button className="btn btn-sm" type="button"
            onClick={() =>
              downloadCsv(token, plan.id, `${plan.name.replace(/\s+/g, "-")}.csv`).catch((f) =>
                push(f.message, "error"),
              )
            }>
            Export
          </button>
        </>
      }
    >
      <main className="planner">
        <Catalog
          courses={courses}
          placedIds={placedIds}
          relevantIds={relevantIds}
          selectedId={selectedCourseId}
          draggingId={draggingId}
          relationOf={relationOf}
          onSelect={(courseId) => {
            setFocusedCourseId(courseId);
            setSelectedCourseId((current) => (current === courseId ? null : courseId));
          }}
          onDragStart={handleDragStart}
          onDragEnd={() => setDraggingId(null)}
        />

        <TermGrid
          terms={plan.terms}
          coursesById={coursesById}
          flaggedCodes={flagged}
          limits={limits}
          armed={selectedCourseId !== null}
          legality={legality}
          draggingId={draggingId}
          leavingId={leavingId}
          focusedId={focusedCourseId}
          relationOf={relationOf}
          onDrop={handleDrop}
          onSelectTerm={(termIndex) => placeCourse(selectedCourseId, termIndex)}
          onRemove={removeCourse}
          onResolve={(course, termIndex) => setPicker({ mode: "swap", termIndex, slot: course })}
          onAdd={(termIndex) => setPicker({ mode: "add", termIndex })}
          onFocus={(courseId) =>
            setFocusedCourseId((current) => (current === courseId ? null : courseId))
          }
          onDragStart={handleDragStart}
          onDragEnd={() => setDraggingId(null)}
        />

        <div className="rail rail-right">
          {focusedCourse ? (
            <CourseDetail
              course={focusedCourse}
              plan={plan}
              termLabels={termLabels}
              onDismiss={() => setFocusedCourseId(null)}
              onJumpTo={focusByCode}
            />
          ) : null}
          <Diagnostics diagnostics={plan.diagnostics} onSelectCourse={focusByCode} />
          <AuditSnapshot plan={plan} />
        </div>
      </main>

      {picker ? (
        <CoursePicker
          planId={plan.id}
          termIndex={picker.termIndex}
          termLabel={termLabels[picker.termIndex]}
          mode={picker.mode}
          slot={picker.slot}
          onChoose={handlePickerChoice}
          onClose={() => setPicker(null)}
        />
      ) : null}

      {sharing ? (
        <ShareDialog
          shareToken={plan.share_token}
          busy={working}
          onCreate={async () => {
            try {
              const body = await api.share(token, plan.id);
              state.setPlan((current) => ({ ...current, share_token: body.token }));
            } catch (failure) {
              push(failure.message, "error");
            }
          }}
          onRevoke={async () => {
            try {
              await api.unshare(token, plan.id);
              state.setPlan((current) => ({ ...current, share_token: null }));
              push("The share link no longer works.");
            } catch (failure) {
              push(failure.message, "error");
            }
          }}
          onClose={() => setSharing(false)}
        />
      ) : null}

      <Toasts toasts={toasts} />
    </PlanChrome>
  );
}

function AuditSnapshot({ plan }) {
  const { audit } = plan;
  const percent = audit.requirement_count
    ? (audit.satisfied_count / audit.requirement_count) * 100
    : 0;
  const extra = Math.round((audit.credits_planned - audit.credits_matched) * 100) / 100;

  return (
    <section className="panel" aria-label="Degree progress">
      <div className="panel-head">
        <h2>Degree</h2>
        <span className="count">{plan.program.degree}</span>
      </div>
      <div className="audit-summary">
        <div className="audit-headline">
          <strong>
            {audit.satisfied_count}/{audit.requirement_count}
          </strong>
          <span className="small muted">requirements filled</span>
        </div>
        <div className="meter" role="img" aria-label={`${Math.round(percent)} percent complete`}>
          <span style={{ width: `${percent}%` }} data-done={audit.complete} />
        </div>
        <p className="small muted">
          {audit.credits_matched} of {plan.required_credits} course units counted.
          {extra > 0
            ? ` A further ${extra} CU are prerequisites the requirement table does not itself list.`
            : ""}
        </p>
        <Link className="btn btn-sm" to={`/plans/${plan.id}/audit`}>
          See the full audit
        </Link>
      </div>
    </section>
  );
}
