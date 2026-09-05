const ORDER = { error: 0, warning: 1, info: 2 };

export function Diagnostics({ diagnostics, onSelectCourse }) {
  const sorted = [...diagnostics].sort(
    (a, b) => (ORDER[a.severity] ?? 3) - (ORDER[b.severity] ?? 3),
  );
  const problems = sorted.filter((item) => item.severity !== "info");

  return (
    <section className="panel" aria-label="Plan checks">
      <div className="panel-head">
        <h2>Checks</h2>
        <span className="count">
          {problems.length === 0 ? "all clear" : `${problems.length} to look at`}
        </span>
      </div>

      {problems.length === 0 ? (
        <p className="all-clear">
          <span aria-hidden="true">&#10003;</span>
          Every prerequisite is in order and no term is over the load limit.
        </p>
      ) : null}

      <div className="diagnostics" aria-live="polite">
        {sorted.map((item, index) => {
          const jumpable = Boolean(item.course_code && onSelectCourse);
          const Element = jumpable ? "button" : "div";
          return (
            <Element
              className="diag"
              type={jumpable ? "button" : undefined}
              data-severity={item.severity}
              data-jumpable={jumpable}
              // A course can fail two prerequisite groups at once, so the code
              // and course together are not unique. The index makes them so.
              key={`${item.code}-${item.course_code ?? ""}-${item.term_index ?? ""}-${index}`}
              onClick={jumpable ? () => onSelectCourse(item.course_code) : undefined}
              title={jumpable ? `Show ${item.course_code} in the plan` : undefined}
            >
              <span className="diag-dot" aria-hidden="true" />
              <span>{item.message}</span>
            </Element>
          );
        })}
      </div>
    </section>
  );
}
