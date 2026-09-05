import { useState } from "react";
import { CourseCard } from "./CourseCard.jsx";

const YEAR_NAMES = ["First year", "Second year", "Third year", "Fourth year"];

function loadState(credits, limits) {
  if (credits === 0) return "empty";
  if (credits > limits.max) return "over";
  if (credits < limits.min) return "under";
  return "ok";
}

function Term({
  term,
  courses,
  flaggedCodes,
  limits,
  armed,
  legality,
  relationOf,
  focusedId,
  readOnly,
  onDrop,
  onSelectTerm,
  onRemove,
  onResolve,
  onFocus,
  onAdd,
  onDragStart,
  onDragEnd,
  draggingId,
  leavingId,
}) {
  const [over, setOver] = useState(false);
  const state = loadState(term.credits, limits);
  const fill = Math.min(100, (term.credits / limits.max) * 100);

  function handleDrop(event) {
    event.preventDefault();
    setOver(false);
    const raw = event.dataTransfer.getData("application/x-course");
    if (!raw) return;
    try {
      const { courseId, fromTerm } = JSON.parse(raw);
      onDrop(courseId, fromTerm, term.index);
    } catch {
      /* a drag from outside the app, ignore it */
    }
  }

  return (
    <div
      className="term"
      data-over={over}
      data-armed={armed}
      // While something is being dragged, every term says whether the course
      // could legally land there. It is a hint computed in the browser from the
      // same graph the server uses; the server still decides.
      data-legal={legality === undefined ? undefined : legality}
      onDragOver={
        readOnly
          ? undefined
          : (event) => {
              event.preventDefault();
              event.dataTransfer.dropEffect = "move";
              if (!over) setOver(true);
            }
      }
      onDragLeave={(event) => {
        // Moving between children fires dragleave on the parent, so only clear
        // the highlight when the pointer really left the term box.
        if (!event.currentTarget.contains(event.relatedTarget)) setOver(false);
      }}
      onDrop={readOnly ? undefined : handleDrop}
      onClick={() => armed && onSelectTerm(term.index)}
    >
      <div className="term-head">
        <span className="term-name">{term.label}</span>
        <span className="term-cu" data-state={state}>
          {term.credits} CU
        </span>
        {readOnly ? null : (
          <button
            type="button"
            className="term-add"
            aria-label={`Show what you could take in ${term.label}`}
            title="What can I take here?"
            onClick={(event) => {
              event.stopPropagation();
              onAdd(term.index);
            }}
          >
            +
          </button>
        )}
      </div>

      <div
        className="load-bar"
        role="img"
        aria-label={`${term.credits} of a ${limits.max} course unit maximum`}
      >
        <span style={{ width: `${fill}%` }} data-state={state} />
      </div>

      <div className="term-courses">
        {courses.length === 0 ? (
          <p className="term-empty">
            {armed ? "Click to place the selected course here" : "Drop a course here"}
          </p>
        ) : (
          courses.map((course) => (
            <CourseCard
              key={course.id}
              course={course}
              showPrerequisites={false}
              flagged={flaggedCodes.has(course.code)}
              dragging={draggingId === course.id}
              leaving={leavingId === course.id}
              selected={focusedId === course.id}
              relation={relationOf(course)}
              onActivate={() => onFocus(course.id)}
              onRemove={
                readOnly
                  ? undefined
                  : (event) => {
                      event.stopPropagation();
                      onRemove(course.id);
                    }
              }
              onResolve={
                readOnly || !course.is_placeholder
                  ? undefined
                  : (event) => {
                      event.stopPropagation();
                      onResolve(course, term.index);
                    }
              }
              onDragStart={
                readOnly ? undefined : (event) => onDragStart(event, course.id, term.index)
              }
              onDragEnd={onDragEnd}
            />
          ))
        )}
      </div>
    </div>
  );
}

export function TermGrid({
  terms,
  coursesById,
  flaggedCodes,
  limits,
  armed,
  legality,
  focusedId,
  ...handlers
}) {
  const years = [];
  for (let start = 0; start < terms.length; start += 2) {
    years.push(terms.slice(start, start + 2));
  }

  return (
    // Dimming the unrelated cards is what makes a focused course's chain
    // findable, so the whole grid needs to know something is focused.
    <div className="years" data-focused={focusedId !== null && focusedId !== undefined}>
      {years.map((pair, yearIndex) => (
        <section className="year" key={yearIndex} aria-label={YEAR_NAMES[yearIndex]}>
          <h3 className="year-label">{YEAR_NAMES[yearIndex] ?? `Year ${yearIndex + 1}`}</h3>
          <div className="year-terms">
            {pair.map((term) => (
              <Term
                key={term.index}
                term={term}
                courses={term.course_ids.map((id) => coursesById.get(id)).filter(Boolean)}
                flaggedCodes={flaggedCodes}
                limits={limits}
                armed={armed}
                legality={legality ? legality[term.index] : undefined}
                focusedId={focusedId}
                {...handlers}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
