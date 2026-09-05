import { categoryColor } from "./CourseCard.jsx";

/**
 * The focused course and its neighbourhood in the prerequisite graph.
 *
 * This panel is why focusing a course is worth doing at all. Everything in it
 * is either stored on the course or derived from the graph on the server, so it
 * answers the two questions a student actually has when choosing between
 * electives: what do I need first, and what does this open up.
 */
export function CourseDetail({ course, plan, termLabels, onDismiss, onJumpTo }) {
  if (!course) return null;

  const placement = plan?.placements.find((entry) => entry.course_id === course.id);
  const problems = (plan?.diagnostics ?? []).filter(
    (item) => item.course_code === course.code && item.severity === "error",
  );

  return (
    <section className="panel detail" aria-label={`About ${course.code}`}>
      <div className="panel-head">
        <h2>
          <span style={{ color: categoryColor(course.category) }}>{course.code}</span>
        </h2>
        <button type="button" className="btn btn-quiet" onClick={onDismiss}>
          Clear
        </button>
      </div>

      <div className="detail-body">
        <p className="detail-title">{course.title}</p>
        <p className="detail-meta">
          {course.credits} CU &middot; {course.category}
          {placement ? ` · ${termLabels[placement.term_index]}` : " · not in this plan"}
        </p>

        {course.description ? <p className="detail-note">{course.description}</p> : null}

        {problems.length > 0 ? (
          <div className="detail-problems">
            {problems.map((item, index) => (
              <p key={index}>{item.message}</p>
            ))}
          </div>
        ) : null}

        <DetailList
          label="Requires"
          codes={course.prerequisite_codes}
          text={course.prerequisite_text}
          onJumpTo={onJumpTo}
          empty="Nothing. It can go in any term."
        />
        {/* "Required by" rather than "unlocks", because this lists the courses
            that name it directly. The picker's "unlocks" count is the whole
            downstream chain, and using one word for both would be misleading. */}
        <DetailList
          label="Required by"
          codes={course.unlocks_codes}
          onJumpTo={onJumpTo}
          empty="No other course in this catalog needs it."
        />
        {course.equivalent_codes.length > 0 ? (
          <DetailList
            label="Also listed as"
            codes={course.equivalent_codes}
            onJumpTo={onJumpTo}
            note="Same course, two numbers. Only one can count toward the degree."
          />
        ) : null}
      </div>

      <div className="legend">
        <span data-relation="prerequisite">prerequisite</span>
        <span data-relation="dependent">unlocked by it</span>
        <span data-relation="equivalent">same course</span>
      </div>
    </section>
  );
}

function DetailList({ label, codes, text, onJumpTo, empty, note }) {
  const list = codes ?? [];
  return (
    <div className="detail-row">
      <h3>{label}</h3>
      {list.length === 0 ? (
        <p className="detail-empty">{empty}</p>
      ) : (
        <>
          <p className="detail-codes">
            {list.map((code) => (
              <button
                key={code}
                type="button"
                className="code-chip"
                onClick={() => onJumpTo(code)}
                title={`Show ${code}`}
              >
                {code}
              </button>
            ))}
          </p>
          {/* The rendered expression matters where the codes alone are
              ambiguous: "MATH 1410, MATH 1610" does not say whether you need
              both or either, and "(MATH 1410 or MATH 1610)" does. */}
          {text && list.length > 1 ? <p className="detail-expression">{text}</p> : null}
          {note ? <p className="detail-empty">{note}</p> : null}
        </>
      )}
    </div>
  );
}
