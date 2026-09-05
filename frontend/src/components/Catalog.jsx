import { useMemo, useState } from "react";
import { CourseCard } from "./CourseCard.jsx";

export function Catalog({
  courses,
  placedIds,
  relevantIds,
  selectedId,
  onSelect,
  onDragStart,
  onDragEnd,
  draggingId,
  relationOf,
}) {
  const [search, setSearch] = useState("");
  const [subject, setSubject] = useState("");
  const [hidePlaced, setHidePlaced] = useState(true);
  // On by default. Two hundred courses sorted by code opens a Computer Science
  // plan on Bioengineering, which is a worse first impression than it sounds.
  const [onlyRelevant, setOnlyRelevant] = useState(true);

  const subjects = useMemo(
    () => [...new Set(courses.filter((c) => !c.is_slot).map((c) => c.subject))].sort(),
    [courses],
  );

  // Filtering happens in the browser because the whole catalog is already
  // loaded. A search box that hit the network on every keystroke would be
  // slower and would not behave any better.
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return courses.filter((course) => {
      if (subject === "__slots") {
        if (!course.is_slot) return false;
      } else if (subject && course.subject !== subject) {
        return false;
      }
      if (hidePlaced && placedIds.has(course.id)) return false;
      if (onlyRelevant && relevantIds && !relevantIds.has(course.id)) return false;
      if (!needle) return true;
      return (
        course.code.toLowerCase().includes(needle) ||
        course.title.toLowerCase().includes(needle)
      );
    });
  }, [courses, search, subject, hidePlaced, onlyRelevant, relevantIds, placedIds]);

  return (
    <section className="panel rail rail-left" aria-label="Course catalog">
      <div className="panel-head">
        <h2>Catalog</h2>
        <span className="count">{visible.length} shown</span>
      </div>

      <div className="catalog-controls">
        <input
          type="search"
          placeholder="Search by code or title"
          aria-label="Search courses"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <select
          aria-label="Filter by subject"
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
        >
          <option value="">All subjects</option>
          <option value="__slots">Requirement slots</option>
          {subjects.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        {relevantIds ? (
          <label className="checkline" title="Courses some requirement of this degree accepts">
            <input
              type="checkbox"
              checked={onlyRelevant}
              onChange={(event) => setOnlyRelevant(event.target.checked)}
            />
            Only what counts toward this degree
          </label>
        ) : null}
        <label className="checkline">
          <input
            type="checkbox"
            checked={hidePlaced}
            onChange={(event) => setHidePlaced(event.target.checked)}
          />
          Hide what is already planned
        </label>
      </div>

      <div className="catalog-list">
        {visible.length === 0 ? (
          <p className="picker-empty">
            {onlyRelevant && relevantIds
              ? "Nothing here matches. Untick the degree filter to search the whole catalog."
              : "Nothing matches that search."}
          </p>
        ) : (
          visible.map((course) => (
            <CourseCard
              key={course.id}
              course={course}
              selected={selectedId === course.id}
              placed={placedIds.has(course.id)}
              dragging={draggingId === course.id}
              relation={relationOf ? relationOf(course) : null}
              onActivate={() => onSelect(course.id)}
              onDragStart={(event) => onDragStart(event, course.id, null)}
              onDragEnd={onDragEnd}
            />
          ))
        )}
      </div>

      <p className="hint">
        Drag a course into a semester, or select it and then choose a semester.
      </p>
    </section>
  );
}
