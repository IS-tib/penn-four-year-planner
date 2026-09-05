import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { useTheme } from "../theme.js";

export function Landing() {
  const { user } = useAuth();
  const [programs, setPrograms] = useState([]);
  useTheme();

  useEffect(() => {
    api.programs().then(setPrograms).catch(() => setPrograms([]));
  }, []);

  const schools = programs.reduce((acc, program) => {
    (acc[program.school] ||= []).push(program);
    return acc;
  }, {});

  return (
    <div>
      <header className="hero">
        <div className="hero-inner">
          <span className="eyebrow" style={{ color: "#9db2dc" }}>
            Penn degree planning
          </span>
          <h1>Four years, laid out, and checked against the real rules.</h1>
          <p>
            Drag courses into semesters and find out immediately whether the order
            actually works. Prerequisites, class standing, course load and every
            requirement of the degree, checked on the server as you build.
          </p>
          <div className="hero-actions">
            {user ? (
              <Link className="btn btn-primary btn-lg" to="/plans">
                Go to my plans
              </Link>
            ) : (
              <>
                <Link className="btn btn-primary btn-lg" to="/signup">
                  Start planning
                </Link>
                <Link className="btn btn-lg" to="/signin">
                  Sign in
                </Link>
              </>
            )}
            <Link className="btn btn-lg" to="/programs">
              Browse degrees
            </Link>
          </div>

          <div className="hero-stats">
            <div>
              <b>{programs.length || 10}</b>
              <span>degrees</span>
            </div>
            <div>
              <b>2</b>
              <span>schools</span>
            </div>
            <div>
              <b>8</b>
              <span>semesters</span>
            </div>
            <div>
              <b>1</b>
              <span>source of truth</span>
            </div>
          </div>
        </div>
      </header>

      <section className="section">
        <div className="section-inner stack" style={{ gap: "1.4rem" }}>
          <div className="page-head" style={{ marginBottom: 0 }}>
            <span className="eyebrow">What it does</span>
            <h2 style={{ fontSize: "1.6rem" }}>
              A spreadsheet cannot tell you that CIS 3200 comes before CIS 2620.
            </h2>
          </div>

          <div className="grid-cards stagger">
            <article className="feature">
              <h3>Prerequisites as a graph</h3>
              <p>
                Penn writes prerequisites as boolean expressions. They are stored and
                evaluated as one, so an out-of-order course is named along with the
                term it would have to move to.
              </p>
            </article>
            <article className="feature">
              <h3>A real degree audit</h3>
              <p>
                Requirements are matched to courses rather than counted, because a
                course may only be spent once. Penn's own footnotes say so.
              </p>
            </article>
            <article className="feature">
              <h3>What can I take here</h3>
              <p>
                Ask any semester what is legal in it, ranked by how much each option
                unlocks further down the chain.
              </p>
            </article>
            <article className="feature">
              <h3>Switching majors</h3>
              <p>
                See what carries over to another degree, what stops counting, and the
                earliest you could still finish.
              </p>
            </article>
            <article className="feature">
              <h3>Built from the catalog</h3>
              <p>
                Course titles, credits and prerequisites are transcribed from
                catalog.upenn.edu. Where the catalog is silent, so is this.
              </p>
            </article>
            <article className="feature">
              <h3>Share it read only</h3>
              <p>
                Send a plan to an advisor with a revocable link. They need no account
                and can change nothing.
              </p>
            </article>
          </div>
        </div>
      </section>

      <section className="section" style={{ background: "var(--surface-2)", borderTop: "1px solid var(--line)" }}>
        <div className="section-inner stack">
          <div className="page-head" style={{ marginBottom: 0 }}>
            <span className="eyebrow">Supported degrees</span>
            <h2 style={{ fontSize: "1.6rem" }}>Ten programs, two schools</h2>
            <p>
              Every one is seeded from its own catalog page, so the requirement
              structures differ as much as the real degrees do.
            </p>
          </div>

          {Object.entries(schools).map(([school, rows]) => (
            <div key={school} className="stack" style={{ gap: "0.6rem" }}>
              <span className="eyebrow">{school}</span>
              <div className="grid-cards">
                {rows.map((program) => (
                  <Link
                    key={program.code}
                    className="program-card"
                    to={`/programs/${program.code}`}
                  >
                    <span className="top">
                      <h3>{program.name}</h3>
                      <span className="degree">{program.degree}</span>
                    </span>
                    <p>{program.notes}</p>
                    <span className="meta">
                      {program.total_units ? `${program.total_units} course units` : "Major only"}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <footer className="section" style={{ paddingTop: 0 }}>
        <div className="section-inner small muted">
          A planning aid, not an official degree audit. Confirm anything that matters
          with your advisor.
        </div>
      </footer>
    </div>
  );
}
