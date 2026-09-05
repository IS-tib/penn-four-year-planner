import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, downloadCsv } from "./api.js";
import { useAuth } from "./auth.jsx";
import {
  buildCourseIndex,
  flaggedCodes as flaggedCodesOf,
  legalTermsFor,
  placementsByCode,
  relationFor,
} from "./graph.js";
import {
  applyLocally,
  emptyHistory,
  pushHistory,
  snapshotOf,
  stepBack,
  stepForward,
} from "./planState.js";
import { AuthScreen } from "./components/AuthScreen.jsx";
import { Catalog } from "./components/Catalog.jsx";
import { CourseDetail } from "./components/CourseDetail.jsx";
import { CoursePicker } from "./components/CoursePicker.jsx";
import { Diagnostics } from "./components/Diagnostics.jsx";
import { ProgressPanel } from "./components/ProgressPanel.jsx";
import { ShareDialog } from "./components/ShareDialog.jsx";
import { SharedPlan } from "./components/SharedPlan.jsx";
import { TermGrid } from "./components/TermGrid.jsx";
import { Toasts } from "./components/Toasts.jsx";

const THEME_KEY = "penn-planner.theme";

function readTheme() {
  try {
    return window.localStorage.getItem(THEME_KEY) ?? "light";
  } catch {
    return "light";
  }
}

function useToasts() {
  const [toasts, setToasts] = useState([]);
  const counter = useRef(0);

  const push = useCallback((message, tone = "info") => {
    const id = (counter.current += 1);
    setToasts((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 4200);
  }, []);

  return { toasts, push };
}

function Planner() {
  const { token, user, signOut } = useAuth();
  const { toasts, push } = useToasts();

  const [plans, setPlans] = useState([]);
  const [planId, setPlanId] = useState(null);
  const [plan, setPlan] = useState(null);
  const [courses, setCourses] = useState([]);
  const [limits, setLimits] = useState({ min: 4, max: 5.5 });
  const [selectedCourseId, setSelectedCourseId] = useState(null);
  const [focusedCourseId, setFocusedCourseId] = useState(null);
  const [draggingId, setDraggingId] = useState(null);
  const [leavingId, setLeavingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [theme, setTheme] = useState(readTheme);
  const [history, setHistory] = useState(emptyHistory);
  const [picker, setPicker] = useState(null);
  const [sharing, setSharing] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* not fatal */
    }
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [catalog, planList, requirements] = await Promise.all([
          api.courses(token),
          api.plans(token),
          api.requirements(),
        ]);
        if (cancelled) return;
        setCourses(catalog);
        setPlans(planList);
        setLimits({
          min: requirements.min_term_credits,
          max: requirements.max_term_credits,
        });
        const first = planList[0];
        if (first) {
          const detail = await api.plan(token, first.id);
          if (cancelled) return;
          setPlanId(first.id);
          setPlan(detail);
        }
      } catch (error) {
        if (!cancelled) push(error.message, "error");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [token, push]);

  const coursesById = useMemo(() => {
    const map = new Map(courses.map((course) => [course.id, course]));
    // A plan can hold a course the current catalog filter did not return, so
    // fold in whatever the plan itself carries.
    plan?.placements.forEach((entry) => map.set(entry.course_id, entry.course));
    return map;
  }, [courses, plan]);

  const index = useMemo(() => buildCourseIndex([...coursesById.values()]), [coursesById]);
  const focusedCourse = focusedCourseId ? coursesById.get(focusedCourseId) : null;

  const relationOf = useCallback(
    (course) => relationFor(focusedCourse, course, index),
    [focusedCourse, index],
  );

  const placedIds = useMemo(
    () => new Set(plan?.placements.map((entry) => entry.course_id) ?? []),
    [plan],
  );

  const flaggedCodes = useMemo(() => flaggedCodesOf(plan), [plan]);

  // While a course is being dragged, work out which terms could legally take
  // it. This is only a hint for the cursor; the server still validates.
  const legality = useMemo(() => {
    if (draggingId === null || !plan) return null;
    const course = coursesById.get(draggingId);
    if (!course) return null;
    return legalTermsFor(course, placementsByCode(plan), plan.terms.length, index);
  }, [draggingId, plan, coursesById, index]);

  const termLabels = useMemo(
    () => (plan?.terms ?? []).map((term) => term.label),
    [plan],
  );

  /**
   * Run a plan mutation optimistically.
   *
   * The local change lands first so a drag feels instant, the server's answer
   * replaces it, and a failure restores the state from before. History is only
   * recorded once the server has agreed, so undo can never step back to a state
   * that was never real.
   */
  const mutate = useCallback(
    async (change, call) => {
      const snapshot = plan;
      const before = snapshotOf(plan);
      setPlan((current) => applyLocally(current, coursesById, change));
      setWorking(true);
      try {
        const fresh = await call();
        setPlan(fresh);
        setHistory((current) => pushHistory(current, before));
        return fresh;
      } catch (error) {
        setPlan(snapshot);
        push(error.message, "error");
        return null;
      } finally {
        setWorking(false);
      }
    },
    [plan, coursesById, push],
  );

  /** Whole-plan operations record history the same way, without a local guess. */
  const runBulk = useCallback(
    async (call, message) => {
      const before = snapshotOf(plan);
      setWorking(true);
      try {
        const fresh = await call();
        setPlan(fresh);
        setHistory((current) => pushHistory(current, before));
        if (message) push(message);
        return fresh;
      } catch (error) {
        push(error.message, "error");
        return null;
      } finally {
        setWorking(false);
      }
    },
    [plan, push],
  );

  const placeCourse = useCallback(
    (courseId, termIndex) => {
      if (placedIds.has(courseId)) {
        const existing = plan.placements.find((entry) => entry.course_id === courseId);
        if (existing?.term_index === termIndex) return;
        mutate({ type: "move", courseId, termIndex }, () =>
          api.moveCourse(token, planId, courseId, termIndex),
        );
      } else {
        mutate({ type: "place", courseId, termIndex }, () =>
          api.placeCourse(token, planId, courseId, termIndex),
        );
      }
      setSelectedCourseId(null);
    },
    [mutate, placedIds, plan, token, planId],
  );

  const removeCourse = useCallback(
    (courseId) => {
      // Let the exit animation play before the row actually leaves the list.
      setLeavingId(courseId);
      window.setTimeout(() => {
        setLeavingId(null);
        mutate({ type: "remove", courseId }, () =>
          api.removeCourse(token, planId, courseId),
        );
      }, 160);
    },
    [mutate, token, planId],
  );

  const undo = useCallback(async () => {
    const step = stepBack(history, snapshotOf(plan));
    if (!step) return;
    setHistory(step.history);
    setWorking(true);
    try {
      setPlan(await api.replacePlacements(token, planId, step.target));
    } catch (error) {
      setHistory(history);
      push(error.message, "error");
    } finally {
      setWorking(false);
    }
  }, [history, plan, token, planId, push]);

  const redo = useCallback(async () => {
    const step = stepForward(history, snapshotOf(plan));
    if (!step) return;
    setHistory(step.history);
    setWorking(true);
    try {
      setPlan(await api.replacePlacements(token, planId, step.target));
    } catch (error) {
      setHistory(history);
      push(error.message, "error");
    } finally {
      setWorking(false);
    }
  }, [history, plan, token, planId, push]);

  useEffect(() => {
    function onKeyDown(event) {
      const target = event.target;
      const typing =
        target instanceof HTMLElement &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);
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
    event.dataTransfer.setData(
      "application/x-course",
      JSON.stringify({ courseId, fromTerm }),
    );
    event.dataTransfer.effectAllowed = "move";
    setDraggingId(courseId);
    setSelectedCourseId(null);
  }

  function handleDrop(courseId, fromTerm, termIndex) {
    setDraggingId(null);
    if (fromTerm === termIndex) return;
    placeCourse(courseId, termIndex);
  }

  /** Focus a course by code and scroll the grid to wherever it sits. */
  const focusByCode = useCallback(
    (code) => {
      const course = index.byCode.get(code);
      if (!course) return;
      setFocusedCourseId(course.id);
      window.requestAnimationFrame(() => {
        const node = document.querySelector(
          `.term .course[data-course-code="${CSS.escape(code)}"]`,
        );
        if (node) {
          node.scrollIntoView({ behavior: "smooth", block: "center" });
          node.classList.remove("flash");
          // Reading offsetWidth forces a reflow, which is what lets the same
          // animation replay when the same course is selected twice.
          void node.offsetWidth;
          node.classList.add("flash");
        }
      });
    },
    [index],
  );

  async function handleAutofill() {
    await runBulk(
      () => api.autofill(token, planId),
      "Filled in the rest of the degree around what you had already placed.",
    );
  }

  async function handlePickerChoice(row) {
    const current = picker;
    setPicker(null);
    if (!current) return;

    if (current.mode === "swap") {
      await mutate(
        { type: "swap", courseId: current.slot.id, replacementId: row.course_id },
        () => api.swapCourse(token, planId, current.slot.id, row.course_id),
      );
    } else {
      await mutate(
        { type: "place", courseId: row.course_id, termIndex: current.termIndex },
        () => api.placeCourse(token, planId, row.course_id, current.termIndex),
      );
    }
    if (row.would_overload) {
      push(`${row.code} puts that term over the ${limits.max} CU load limit.`);
    }
  }

  async function handleShareCreate() {
    setWorking(true);
    try {
      const body = await api.share(token, planId);
      setPlan((current) => ({ ...current, share_token: body.token }));
    } catch (error) {
      push(error.message, "error");
    } finally {
      setWorking(false);
    }
  }

  async function handleShareRevoke() {
    setWorking(true);
    try {
      await api.unshare(token, planId);
      setPlan((current) => ({ ...current, share_token: null }));
      push("The share link no longer works.");
    } catch (error) {
      push(error.message, "error");
    } finally {
      setWorking(false);
    }
  }

  async function handleExport() {
    try {
      await downloadCsv(token, planId, `${plan.name.replace(/\s+/g, "-")}.csv`);
    } catch (error) {
      push(error.message, "error");
    }
  }

  async function handleNewPlan() {
    setWorking(true);
    try {
      const created = await api.createPlan(token, {
        name: `Plan ${plans.length + 1}`,
        start_year: new Date().getFullYear(),
      });
      setPlans(await api.plans(token));
      setPlanId(created.id);
      setPlan(created);
      setHistory(emptyHistory);
    } catch (error) {
      push(error.message, "error");
    } finally {
      setWorking(false);
    }
  }

  async function handleSwitchPlan(nextId) {
    setWorking(true);
    try {
      const detail = await api.plan(token, nextId);
      setPlanId(nextId);
      setPlan(detail);
      // History is per plan. Carrying it across would let undo write one plan's
      // placements into another.
      setHistory(emptyHistory);
      setFocusedCourseId(null);
    } catch (error) {
      push(error.message, "error");
    } finally {
      setWorking(false);
    }
  }

  async function handleRename(name) {
    const trimmed = name.trim();
    if (!trimmed || trimmed === plan.name) return;
    try {
      const fresh = await api.renamePlan(token, planId, trimmed);
      setPlan(fresh);
      setPlans((current) =>
        current.map((entry) => (entry.id === planId ? { ...entry, name: trimmed } : entry)),
      );
    } catch (error) {
      push(error.message, "error");
    }
  }

  if (loading) {
    return (
      <div className="busy">
        <div>
          <div className="spinner" />
          Loading your plan
        </div>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="busy">
        <div style={{ textAlign: "center", display: "grid", gap: "0.75rem" }}>
          <p>You do not have a plan yet.</p>
          <button className="btn btn-primary" type="button" onClick={handleNewPlan}>
            Start one
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <strong>Four Year Planner</strong>
          <span>Penn CS BSE</span>
        </div>

        <input
          className="plan-name"
          defaultValue={plan.name}
          key={plan.id}
          aria-label="Plan name"
          onBlur={(event) => handleRename(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.target.blur();
          }}
        />

        {plans.length > 1 ? (
          <select
            aria-label="Switch plan"
            value={planId ?? ""}
            onChange={(event) => handleSwitchPlan(Number(event.target.value))}
            style={{ width: "auto" }}
          >
            {plans.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.name}
              </option>
            ))}
          </select>
        ) : null}

        <div className="topbar-spacer" />

        <div className="topbar-actions">
          <div className="btn-group">
            <button
              className="btn"
              type="button"
              onClick={undo}
              disabled={working || history.past.length === 0}
              title="Undo (Ctrl+Z)"
              aria-label="Undo"
            >
              Undo
            </button>
            <button
              className="btn"
              type="button"
              onClick={redo}
              disabled={working || history.future.length === 0}
              title="Redo (Ctrl+Shift+Z)"
              aria-label="Redo"
            >
              Redo
            </button>
          </div>
          <button className="btn" type="button" onClick={handleAutofill} disabled={working}>
            Autofill
          </button>
          <button
            className="btn"
            type="button"
            onClick={() => setSharing(true)}
            disabled={working}
            data-active={Boolean(plan.share_token)}
          >
            Share
          </button>
          <button className="btn" type="button" onClick={handleExport}>
            Export
          </button>
          <button className="btn" type="button" onClick={handleNewPlan} disabled={working}>
            New plan
          </button>
          <button
            className="btn btn-quiet"
            type="button"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label="Toggle dark mode"
            title="Toggle dark mode"
          >
            {theme === "dark" ? "Light" : "Dark"}
          </button>
          <span className="who">{user?.display_name}</span>
          <button className="btn btn-quiet" type="button" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      <main className="layout">
        <Catalog
          courses={courses}
          placedIds={placedIds}
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
          flaggedCodes={flaggedCodes}
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
          onResolve={(course, termIndex) =>
            setPicker({ mode: "swap", termIndex, slot: course })
          }
          onAdd={(termIndex) => setPicker({ mode: "add", termIndex })}
          onFocus={(courseId) =>
            setFocusedCourseId((current) => (current === courseId ? null : courseId))
          }
          onDragStart={handleDragStart}
          onDragEnd={() => setDraggingId(null)}
        />

        <div
          className="rail-right"
          style={{ display: "grid", gap: "clamp(0.75rem, 1.5vw, 1.25rem)", alignContent: "start" }}
        >
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
          <ProgressPanel
            progress={plan.progress}
            planned={plan.total_planned_credits}
            tracked={plan.degree_total_credits}
            published={plan.published_degree_credits}
          />
        </div>
      </main>

      {picker ? (
        <CoursePicker
          planId={planId}
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
          onCreate={handleShareCreate}
          onRevoke={handleShareRevoke}
          onClose={() => setSharing(false)}
        />
      ) : null}

      <Toasts toasts={toasts} />
    </div>
  );
}

export default function App() {
  const { user, checking } = useAuth();

  // A share link is the one route that does not need an account, so it is
  // checked before anything else. There is no router in this app; one query
  // parameter did not justify the dependency.
  const shareToken = new URLSearchParams(window.location.search).get("share");
  if (shareToken) return <SharedPlan shareToken={shareToken} />;

  if (checking) {
    return (
      <div className="busy">
        <div>
          <div className="spinner" />
          Checking your session
        </div>
      </div>
    );
  }

  return user ? <Planner /> : <AuthScreen />;
}
