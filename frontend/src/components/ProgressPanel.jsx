import { categoryColor } from "./CourseCard.jsx";

export function ProgressPanel({ progress, planned, tracked, published }) {
  return (
    <section className="panel" aria-label="Degree progress">
      <div className="panel-head">
        <h2>Requirements</h2>
        <span className="count">course units</span>
      </div>

      <div className="progress-list">
        {progress.map((row) => {
          const percent = row.target > 0 ? Math.min(100, (row.planned / row.target) * 100) : 0;
          const done = row.planned >= row.target;
          return (
            <div className="progress-row" key={row.category}>
              <div className="progress-top">
                <b>{row.category}</b>
                <span>
                  {row.planned} / {row.target}
                </span>
              </div>
              <div
                className="progress-track"
                role="img"
                aria-label={`${row.category}: ${row.planned} of ${row.target} course units planned`}
              >
                <span
                  className="progress-fill"
                  style={{
                    width: `${percent}%`,
                    background: done ? "var(--ok)" : categoryColor(row.category),
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div className="progress-total">
        <strong>
          {planned} / {tracked} CU
        </strong>
        <small>
          Penn publishes the degree as {published} CU. The buckets above are added up from the
          line items on the catalog page and come to {tracked}, so confirm the last unit with your
          advisor rather than trusting this figure.
        </small>
      </div>
    </section>
  );
}
