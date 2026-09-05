const SUBJECT_VAR = {
  CIS: "var(--cat-cis)",
  NETS: "var(--cat-cis)",
  MATH: "var(--cat-math)",
  STAT: "var(--cat-math)",
  ENM: "var(--cat-math)",
  PHYS: "var(--cat-phys)",
  BIOL: "var(--cat-bio)",
  BE: "var(--cat-bio)",
  CHEM: "var(--cat-chem)",
  ESE: "var(--cat-eng)",
  MEAM: "var(--cat-eng)",
  ENGR: "var(--cat-eng)",
};

/** Colour by subject, so a plan reads as a shape rather than a list. */
export function subjectColor(subject) {
  return SUBJECT_VAR[subject] ?? "var(--cat-slot)";
}

const RELATION_LABEL = {
  prerequisite: "prerequisite",
  dependent: "needs it",
  equivalent: "same course",
};

/**
 * One course, in the catalog list or inside a term.
 *
 * It is a button rather than a div so the whole card is reachable with a
 * keyboard. Dragging is the fast path for a mouse; selecting the card and then
 * choosing a term is the path that works on a phone and with a keyboard, and
 * both end at the same API call.
 *
 * `relation` is how this course relates to whichever one is focused, and it is
 * what makes the prerequisite graph legible: focus CIS 1200 and everything
 * downstream lights up wherever it sits in the plan.
 */
export function CourseCard({
  course,
  selected = false,
  placed = false,
  flagged = false,
  dragging = false,
  leaving = false,
  relation = null,
  showPrerequisites = true,
  onActivate,
  onRemove,
  onResolve,
  onDragStart,
  onDragEnd,
}) {
  const label = placed
    ? `${course.code}, ${course.title}, already in this plan`
    : `${course.code}, ${course.title}, ${course.credits} course units`;

  return (
    <div
      className="course"
      style={{ "--cat": subjectColor(course.subject) }}
      data-course-code={course.code}
      data-selected={selected}
      data-placed={placed}
      data-flagged={flagged}
      data-dragging={dragging}
      data-leaving={leaving}
      data-slot={course.is_slot}
      data-relation={relation ?? undefined}
      draggable={Boolean(onDragStart)}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
    >
      <button
        type="button"
        className="course-hit"
        onClick={onActivate}
        aria-pressed={selected}
        aria-label={label}
      >
        <span className="course-top">
          <span className="course-code">{course.code}</span>
          <span className="course-cu">{course.credits} CU</span>
        </span>
        <span className="course-title">{course.title}</span>
        {showPrerequisites && course.prerequisite_text ? (
          <span className="course-prereq">Requires {course.prerequisite_text}</span>
        ) : null}
      </button>

      {relation && relation !== "focus" ? (
        <span className="relation-tag" data-relation={relation}>
          {RELATION_LABEL[relation]}
        </span>
      ) : null}

      <span className="course-actions">
        {onResolve ? (
          <button
            type="button"
            className="course-icon"
            onClick={onResolve}
            aria-label={`Choose a course for ${course.code}`}
            title="Choose a course for this slot"
          >
            &#9998;
          </button>
        ) : null}
        {onRemove ? (
          <button
            type="button"
            className="course-icon danger"
            onClick={onRemove}
            aria-label={`Remove ${course.code} from this plan`}
            title="Remove"
          >
            &times;
          </button>
        ) : null}
      </span>
    </div>
  );
}
