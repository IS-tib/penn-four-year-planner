import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Shell } from "../components/Shell.jsx";
import { useTheme } from "../theme.js";

/** Public pages, so the degrees can be linked to without an account. */
function Frame({ title, children }) {
  const { user } = useAuth();
  useTheme();

  if (user) {
    return (
      <Shell>
        <header className="topbar">
          <h1>{title}</h1>
        </header>
        {children}
      </Shell>
    );
  }
  return (
    <div>
      <header className="topbar">
        <Link to="/" style={{ textDecoration: "none" }}>
          <strong style={{ fontFamily: "var(--serif)" }}>Course Map</strong>
        </Link>
        <div className="spacer" />
        <Link className="btn btn-sm" to="/signin">
          Sign in
        </Link>
      </header>
      {children}
    </div>
  );
}

export function Programs() {
  const [programs, setPrograms] = useState(null);

  useEffect(() => {
    api.programs().then(setPrograms).catch(() => setPrograms([]));
  }, []);

  const schools = (programs ?? []).reduce((acc, program) => {
    (acc[program.school] ||= []).push(program);
    return acc;
  }, {});

  return (
    <Frame title="Degrees">
      <div className="page page-narrow stack" style={{ gap: "1.4rem" }}>
        <div className="page-head" style={{ marginBottom: 0 }}>
          <span className="eyebrow">Supported</span>
          <h1>Ten degrees, two schools</h1>
          <p>
            Each one is seeded from its own page of the Penn catalog, so the
            requirement structures differ as much as the real degrees do. A
            bioengineering degree is a long prescribed chain; a mathematics BA is
            mostly choices between equivalent courses.
          </p>
        </div>

        {programs === null ? (
          <div className="busy">
            <div>
              <div className="spinner" />
              Loading degrees
            </div>
          </div>
        ) : (
          Object.entries(schools).map(([school, rows]) => (
            <div key={school} className="stack" style={{ gap: "0.6rem" }}>
              <span className="eyebrow">{school}</span>
              <div className="grid-cards">
                {rows.map((program) => (
                  <Link key={program.code} className="program-card" to={`/programs/${program.code}`}>
                    <span className="top">
                      <h3>{program.name}</h3>
                      <span className="degree">{program.degree}</span>
                    </span>
                    <p>{program.notes}</p>
                    <span className="meta">
                      {program.total_units
                        ? `${program.total_units} course units`
                        : "Major only"}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </Frame>
  );
}

export function ProgramDetail() {
  const { code } = useParams();
  const [program, setProgram] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.program(code).then(setProgram).catch((failure) => setError(failure.message));
  }, [code]);

  if (error) {
    return (
      <Frame title="Not found">
        <div className="page page-narrow">
          <div className="empty-state">
            <h2>No such degree</h2>
            <p>{error}</p>
            <Link className="btn" to="/programs">
              Back to all degrees
            </Link>
          </div>
        </div>
      </Frame>
    );
  }

  if (!program) {
    return (
      <Frame title="Degree">
        <div className="busy">
          <div>
            <div className="spinner" />
            Loading
          </div>
        </div>
      </Frame>
    );
  }

  const total = program.groups.reduce((sum, group) => sum + group.credits, 0);

  return (
    <Frame title={`${program.name} ${program.degree}`}>
      <div className="page page-narrow stack" style={{ gap: "1.1rem" }}>
        <div className="page-head" style={{ marginBottom: 0 }}>
          <span className="eyebrow">{program.school}</span>
          <h1>
            {program.name} {program.degree}
          </h1>
          <p>{program.notes}</p>
        </div>

        <div className="stat-row">
          <div className="stat">
            <b>{program.total_units ?? total}</b>
            <span>course units</span>
          </div>
          <div className="stat">
            <b>{program.groups.length}</b>
            <span>requirement groups</span>
          </div>
          <div className="stat">
            <b>{program.groups.reduce((n, g) => n + g.requirements.length, 0)}</b>
            <span>requirement rows</span>
          </div>
          <div className="stat">
            <b>{program.term_count}</b>
            <span>semesters</span>
          </div>
        </div>

        <section className="panel">
          <div className="panel-head">
            <h2>Requirements</h2>
            <span className="count">
              <a href={program.source_url} target="_blank" rel="noreferrer">
                catalog source
              </a>
            </span>
          </div>

          {program.groups.map((group, index) => (
            <details className="req-group" key={group.name + index} open={index < 2}>
              <summary>
                {group.name}
                <span className="spacer" />
                <span className="small muted tabular">{group.credits} CU</span>
              </summary>
              <div className="req-list">
                {group.notes ? <p className="detail-empty">{group.notes}</p> : null}
                {group.requirements.map((requirement) => (
                  <div className="req" key={requirement.id}>
                    <span aria-hidden="true" />
                    <span className="label">
                      <span>{requirement.label}</span>
                      {requirement.option_codes.length > 1 ? (
                        <span className="matched">
                          {requirement.option_codes.join(", ")}
                        </span>
                      ) : null}
                      {requirement.notes ? (
                        <span className="detail-empty">{requirement.notes}</span>
                      ) : null}
                    </span>
                    <span className="filled tabular">
                      {requirement.slots > 1
                        ? `${requirement.slots} courses`
                        : `${requirement.credits} CU`}
                    </span>
                  </div>
                ))}
              </div>
            </details>
          ))}
        </section>

        <p className="small muted">
          Transcribed from the Penn catalog. Rows the catalog leaves open, such as
          "select four social science or humanities courses", appear as slots rather
          than an invented course list. A planning aid, not an official degree audit.
        </p>
      </div>
    </Frame>
  );
}
