import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { useTheme } from "../theme.js";
import { useCountUp, useReveal } from "../reveal.js";
import { HeroGraph } from "../components/HeroGraph.jsx";
import { LiveDemo } from "../components/LiveDemo.jsx";

const FEATURES = [
  {
    title: "Prerequisites as a graph",
    body: "Penn writes prerequisites as boolean expressions. They are stored and evaluated as one, so an out-of-order course is named along with the term it would have to move to.",
  },
  {
    title: "A real degree audit",
    body: "Requirements are matched to courses rather than counted, because a course may only be spent once. Penn's own footnotes say so.",
  },
  {
    title: "What can I take here",
    body: "Ask any semester what is legal in it, ranked by how much each option unlocks further down the chain.",
  },
  {
    title: "Switching majors",
    body: "See what carries over to another degree, what stops counting, and the earliest you could still finish.",
  },
  {
    title: "Built from the catalog",
    body: "Course titles, credits and prerequisites are transcribed from catalog.upenn.edu. Where the catalog is silent, so is this.",
  },
  {
    title: "Share it read only",
    body: "Send a plan to an advisor with a revocable link. They need no account and can change nothing.",
  },
];

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

  // Set on the frame after mount so the hero has a state to transition from.
  // Rendering it ready straight away would mean no entrance at all, since a
  // transition needs two computed styles to move between.
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  const [demoRef, demoShown] = useReveal();
  const [featureRef, featuresShown] = useReveal();
  const [degreesRef, degreesShown] = useReveal();

  return (
    <div className="landing">
      <header className="hero" data-ready={ready}>
        <div className="hero-inner">
          <div className="hero-copy">
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

            <HeroStats count={programs.length} />
          </div>

          <div className="hero-art" aria-hidden={false}>
            <HeroGraph />
          </div>
        </div>
      </header>

      <section className="section section-demo" ref={demoRef} data-shown={demoShown}>
        <div className="section-inner demo-layout">
          <div className="stack" style={{ gap: "0.7rem" }}>
            <span className="eyebrow">Watch it catch one</span>
            <h2 style={{ fontSize: "1.6rem" }}>
              A spreadsheet cannot tell you that CIS 3200 comes before CIS 2620.
            </h2>
            <p className="muted">
              Every check runs on the server against the prerequisite graph from the
              catalog, so it names the course, the term it is in, and the term it
              would have to move to. The plan on the right is the real thing,
              replayed.
            </p>
            <div className="hero-actions" style={{ marginTop: "0.5rem" }}>
              <Link className="btn" to={user ? "/plans" : "/signup"}>
                Try it on your own degree
              </Link>
            </div>
          </div>
          <LiveDemo />
        </div>
      </section>

      <section className="section" ref={featureRef} data-shown={featuresShown}>
        <div className="section-inner stack" style={{ gap: "1.4rem" }}>
          <div className="page-head" style={{ marginBottom: 0 }}>
            <span className="eyebrow">What it does</span>
            <h2 style={{ fontSize: "1.6rem" }}>Six things a spreadsheet will not do</h2>
          </div>

          <div className="grid-cards grid-features rise">
            {FEATURES.map((feature, index) => (
              <article className="feature" key={feature.title} style={{ "--i": index }}>
                <h3>{feature.title}</h3>
                <p>{feature.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section
        className="section section-degrees"
        ref={degreesRef}
        data-shown={degreesShown}
      >
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
              <div className="grid-cards rise">
                {rows.map((program, index) => (
                  <Link
                    key={program.code}
                    className="program-card"
                    style={{ "--i": index }}
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

function HeroStats({ count }) {
  const degrees = useCountUp(count || 10, count > 0);
  const schools = useCountUp(2, count > 0);
  const semesters = useCountUp(8, count > 0);

  return (
    <div className="hero-stats">
      <div>
        <b className="tabular">{degrees}</b>
        <span>degrees</span>
      </div>
      <div>
        <b className="tabular">{schools}</b>
        <span>schools</span>
      </div>
      <div>
        <b className="tabular">{semesters}</b>
        <span>semesters</span>
      </div>
      <div>
        <b className="tabular">1</b>
        <span>source of truth</span>
      </div>
    </div>
  );
}
