import { Shell } from "./Shell.jsx";

/** The shell plus a plan-aware topbar, shared by the three plan pages. */
export function PlanChrome({ plan, planId, title, actions, onRename, children }) {
  const links = [
    { to: `/plans/${planId}`, label: "Planner", end: true },
    { to: `/plans/${planId}/audit`, label: "Degree audit" },
    { to: `/plans/${planId}/compare`, label: "Switch major" },
  ];

  return (
    <Shell planLinks={links}>
      <header className="topbar">
        {plan && onRename ? (
          <input
            className="plan-name"
            defaultValue={plan.name}
            key={plan.id}
            aria-label="Plan name"
            onBlur={(event) => onRename(event.target.value.trim() || plan.name)}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.target.blur();
            }}
          />
        ) : (
          <h1>{plan ? plan.name : title}</h1>
        )}
        {plan ? (
          <span className="chip" data-tone="navy">
            {plan.program.name} {plan.program.degree}
          </span>
        ) : null}
        <div className="spacer" />
        <div className="row" style={{ gap: "0.35rem" }}>
          {actions}
        </div>
      </header>
      {children}
    </Shell>
  );
}
