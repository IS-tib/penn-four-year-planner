import { useEffect, useMemo, useState } from "react";

import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Dialog } from "./Dialog.jsx";
import { categoryColor } from "./CourseCard.jsx";

/**
 * Pick a course the plan could legally take.
 *
 * Used for two things that turn out to be the same question. "What can I take
 * in Spring 2028" is a student staring at an empty term. "What actually fills
 * this Technical Elective slot" is the same student a month later, and both
 * want the list of courses whose prerequisites will be satisfied by then.
 *
 * The list comes from the server rather than being filtered here, because the
 * rule for what is eligible is the same rule that decides what is valid, and
 * having one implementation of it is the whole point.
 */
export function CoursePicker({ planId, termIndex, termLabel, mode, slot, onChoose, onClose }) {
  const { token } = useAuth();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [hideOverloading, setHideOverloading] = useState(false);

  const swapping = mode === "swap";

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setError(null);
    api
      .eligible(token, planId, {
        termIndex,
        // A slot is being resolved into a real course, so only offer courses
        // from the same requirement bucket, and never another placeholder.
        category: swapping ? slot?.category : undefined,
        excludePlaceholders: swapping,
      })
      .then((found) => {
        if (!cancelled) setRows(found);
      })
      .catch((failure) => {
        if (!cancelled) setError(failure.message);
      });
    return () => {
      cancelled = true;
    };
  }, [token, planId, termIndex, swapping, slot?.category]);

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (rows ?? []).filter((row) => {
      if (hideOverloading && row.would_overload) return false;
      if (!needle) return true;
      return (
        row.code.toLowerCase().includes(needle) || row.title.toLowerCase().includes(needle)
      );
    });
  }, [rows, search, hideOverloading]);

  const title = swapping ? `Fill ${slot?.code}` : `Add to ${termLabel}`;
  const subtitle = swapping
    ? `Courses in the ${slot?.category} requirement whose prerequisites are met by ${termLabel}.`
    : `Everything whose prerequisites would be satisfied by ${termLabel}.`;

  return (
    <Dialog title={title} subtitle={subtitle} onClose={onClose} wide>
      <div className="picker-controls">
        <input
          type="search"
          autoFocus
          placeholder="Search by code or title"
          aria-label="Search eligible courses"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <label className="checkline">
          <input
            type="checkbox"
            checked={hideOverloading}
            onChange={(event) => setHideOverloading(event.target.checked)}
          />
          Only what fits in the term
        </label>
      </div>

      {error ? <p className="auth-error">{error}</p> : null}
      {rows === null && !error ? (
        <p className="picker-empty">
          <span className="spinner" />
        </p>
      ) : null}

      {rows !== null && visible.length === 0 ? (
        <p className="picker-empty">
          Nothing is eligible here yet. Prerequisites have to sit in an earlier term.
        </p>
      ) : null}

      <ul className="picker-list">
        {visible.map((row) => (
          <li key={row.course_id}>
            <button
              type="button"
              className="picker-row"
              data-overload={row.would_overload}
              style={{ "--cat": categoryColor(row.category) }}
              onClick={() => onChoose(row)}
            >
              <span className="picker-code">{row.code}</span>
              <span className="picker-title">{row.title}</span>
              {row.unlocks > 0 ? (
                <span
                  className="picker-tag"
                  title="Courses this one leads to, directly or further along the chain"
                >
                  unlocks {row.unlocks}
                </span>
              ) : null}
              {row.would_overload ? (
                <span className="picker-tag" data-tone="warn">
                  over the load limit
                </span>
              ) : null}
              <span className="picker-cu">{row.credits} CU</span>
            </button>
          </li>
        ))}
      </ul>
    </Dialog>
  );
}
