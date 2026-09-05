import { useEffect, useRef, useState } from "react";

/**
 * The app catching a mistake, on a loop, without an account.
 *
 * A landing page can describe prerequisite checking or it can show it. This is
 * a scripted replay of the single interaction the whole project exists for:
 * CIS 3200 placed before CIS 1210, the server saying so in the terms the
 * student needs, and the check clearing once it moves.
 *
 * It is deliberately a replay and not a live embed. Everything it asserts is
 * true of the real app, but a real plan needs an account, and a landing page
 * that silently creates one would be worse than an honest reconstruction.
 */

const TERMS = [
  { label: "Fall 2026", course: "CIS 1100", title: "Introduction to Computer Programming" },
  { label: "Spring 2027", course: "CIS 1200", title: "Programming Languages and Techniques I" },
  { label: "Fall 2027", course: "CIS 1210", title: "Programming Languages and Techniques II" },
  { label: "Spring 2028", course: "CIS 2400", title: "Introduction to Computer Systems" },
];

// slot is the column the travelling card sits in; lifted means mid-drag, which
// is when the real app marks every term legal or illegal.
const SCRIPT = [
  { slot: 0, lifted: false, state: "error", hold: 2800 },
  { slot: 0, lifted: true, state: "error", hold: 900 },
  { slot: 3, lifted: true, state: "ok", hold: 700 },
  { slot: 3, lifted: false, state: "ok", hold: 3200 },
  { slot: 3, lifted: true, state: "ok", hold: 900 },
  { slot: 0, lifted: true, state: "error", hold: 700 },
];

export function LiveDemo() {
  const [step, setStep] = useState(0);
  const [running, setRunning] = useState(true);
  const timer = useRef(null);

  useEffect(() => {
    if (!running) return undefined;
    timer.current = window.setTimeout(
      () => setStep((current) => (current + 1) % SCRIPT.length),
      SCRIPT[step].hold,
    );
    return () => window.clearTimeout(timer.current);
  }, [step, running]);

  const frame = SCRIPT[step];
  // CIS 1210 is in the third term, so the third is the earliest legal one.
  const legalFrom = 3;

  return (
    <div className="demo">
      <div className="demo-head">
        <span className="eyebrow">A plan being fixed</span>
        {/* An explicit control rather than pause-on-hover, which a phone has no
            way to express. */}
        <button
          type="button"
          className="btn btn-sm btn-ghost"
          onClick={() => setRunning((current) => !current)}
        >
          {running ? "Pause" : "Play"}
        </button>
      </div>

      <div className="demo-scroll">
        <div className="demo-terms">
          {TERMS.map((term, index) => (
            <div
              className="demo-term"
              key={term.label}
              data-legal={frame.lifted ? index >= legalFrom : undefined}
            >
              <div className="demo-term-head">
                <span>{term.label}</span>
              </div>
              <div className="demo-card" title={term.title}>
                <span className="demo-code">{term.course}</span>
              </div>
              <div className="demo-slot" />
            </div>
          ))}

          <div
            className="demo-mover"
            data-lifted={frame.lifted}
            data-state={frame.state}
            style={{ "--slot": frame.slot }}
          >
            <div className="demo-card demo-card-moving">
              <span className="demo-code">CIS 3200</span>
              <span className="demo-title">Introduction to Algorithms</span>
            </div>
          </div>
        </div>
      </div>

      <div className="demo-check" data-state={frame.state} role="status" aria-live="polite">
        <span className="demo-dot" aria-hidden="true" />
        {frame.state === "error" ? (
          <span>
            <strong>CIS 3200 requires CIS 1210</strong>, which is not scheduled until
            Fall 2027. Move it to Spring 2028 or later.
          </span>
        ) : (
          <span>
            <strong>Every prerequisite is in order</strong> and no term is over the
            load limit.
          </span>
        )}
      </div>
    </div>
  );
}
