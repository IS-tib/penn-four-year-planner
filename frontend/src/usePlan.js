import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "./api.js";
import { useAuth } from "./auth.jsx";
import { buildCourseIndex, flaggedCodes as flaggedCodesOf } from "./graph.js";
import {
  applyLocally,
  emptyHistory,
  pushHistory,
  snapshotOf,
  stepBack,
  stepForward,
} from "./planState.js";

/**
 * Everything three pages need to know about one plan.
 *
 * The planner, the degree audit and the switch comparison all read the same
 * plan and all want the same loading, error and mutation behaviour, so it lives
 * here once rather than three times.
 */
export function usePlan(planId, { toast } = {}) {
  const { token } = useAuth();
  const [plan, setPlan] = useState(null);
  const [courses, setCourses] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [history, setHistory] = useState(emptyHistory);
  const notify = useRef(toast);
  notify.current = toast;

  const report = useCallback((message, tone = "error") => {
    notify.current?.(message, tone);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setHistory(emptyHistory);
    Promise.all([api.plan(token, planId), api.courses(token)])
      .then(([detail, catalog]) => {
        if (cancelled) return;
        setPlan(detail);
        setCourses(catalog);
        setError(null);
      })
      .catch((failure) => {
        if (!cancelled) setError(failure.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, planId]);

  const coursesById = useMemo(() => {
    const map = new Map(courses.map((course) => [course.id, course]));
    plan?.placements.forEach((entry) => map.set(entry.course_id, entry.course));
    return map;
  }, [courses, plan]);

  const index = useMemo(() => buildCourseIndex([...coursesById.values()]), [coursesById]);
  const placedIds = useMemo(
    () => new Set(plan?.placements.map((entry) => entry.course_id) ?? []),
    [plan],
  );
  const flagged = useMemo(() => flaggedCodesOf(plan), [plan]);

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
      } catch (failure) {
        setPlan(snapshot);
        report(failure.message);
        return null;
      } finally {
        setWorking(false);
      }
    },
    [plan, coursesById, report],
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
        if (message) report(message, "info");
        return fresh;
      } catch (failure) {
        report(failure.message);
        return null;
      } finally {
        setWorking(false);
      }
    },
    [plan, report],
  );

  const restore = useCallback(
    async (step) => {
      if (!step) return;
      const previous = history;
      setHistory(step.history);
      setWorking(true);
      try {
        setPlan(await api.replacePlacements(token, planId, step.target));
      } catch (failure) {
        setHistory(previous);
        report(failure.message);
      } finally {
        setWorking(false);
      }
    },
    [history, token, planId, report],
  );

  const undo = useCallback(
    () => restore(stepBack(history, snapshotOf(plan))),
    [restore, history, plan],
  );
  const redo = useCallback(
    () => restore(stepForward(history, snapshotOf(plan))),
    [restore, history, plan],
  );

  return {
    plan,
    setPlan,
    courses,
    coursesById,
    index,
    placedIds,
    flagged,
    loading,
    working,
    error,
    history,
    mutate,
    runBulk,
    undo,
    redo,
    canUndo: history.past.length > 0,
    canRedo: history.future.length > 0,
    report,
  };
}

/** Toast queue, shared by every page that can fail. */
export function useToasts() {
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
