import { useMemo, useState } from "react";
import { CourseCard } from "./CourseCard.jsx";

const CATEGORIES = [
  "CIS Core",
  "Math & Natural Science",
  "CIS Elective",
  "Technical Elective",
  "General Elective",
  "Free Elective",
];

export function Catalog({
  courses,
  placedIds,
  selectedId,
  onSelect,
  onDragStart,
  onDragEnd,
  draggingId,
  relationOf,
}) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [hidePlaced, setHidePlaced] = useState(true);

  // Filtering happens in the browser because the whole catalog is a few dozen
  // rows and already loaded. A search box that hits the network on every
  // keystroke would be slower and would not behave any better.
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return courses.filter((course) => {
      if (category && course.category !== category) return false;
      if (hidePlaced && placedIds.has(course.id)) return false;
      if (!needle) return true;
      return (
        course.code.toLowerCase().includes(needle) ||
        course.title.toLowerCase().includes(needle)
      );
    });
  }, [courses, search, category, hidePlaced, placedIds]);

  return (
    <section className="panel sticky-rail rail-left" aria-label="Course catalog">
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
          aria-label="Filter by requirement"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        >
          <option value="">All requirements</option>
          {CATEGORIES.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <label
          style={{
            display: "flex",
            gap: "0.4rem",
            alignItems: "center",
            fontSize: "0.78rem",
            color: "var(--ink-soft)",
          }}
        >
          <input
            type="checkbox"
            checked={hidePlaced}
            onChange={(event) => setHidePlaced(event.target.checked)}
          />
          Hide courses already in the plan
        </label>
      </div>

      <div className="catalog-list">
        {visible.length === 0 ? (
          <p className="catalog-empty">Nothing matches that search.</p>
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
