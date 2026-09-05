import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Shell } from "../components/Shell.jsx";
import { Toasts } from "../components/Toasts.jsx";
import { useToasts } from "../usePlan.js";

export function Dashboard() {
  const { token, user } = useAuth();
  const { toasts, push } = useToasts();
  const [plans, setPlans] = useState(null);
  const [programs, setPrograms] = useState({});

  useEffect(() => {
    Promise.all([api.plans(token), api.programs()])
      .then(([rows, programList]) => {
        setPlans(rows);
        setPrograms(Object.fromEntries(programList.map((p) => [p.id, p])));
      })
      .catch((failure) => {
        push(failure.message, "error");
        setPlans([]);
      });
  }, [token, push]);

  async function remove(planId, name) {
    if (!window.confirm(`Delete "${name}"? This cannot be undone.`)) return;
    try {
      await api.deletePlan(token, planId);
      setPlans((current) => current.filter((plan) => plan.id !== planId));
      push("Plan deleted.");
    } catch (failure) {
      push(failure.message, "error");
    }
  }

  return (
    <Shell>
      <header className="topbar">
        <h1>My plans</h1>
        <div className="spacer" />
        <Link className="btn btn-primary" to="/plans/new">
          Start a plan
        </Link>
      </header>

      <div className="page page-narrow">
        {plans === null ? (
          <div className="busy">
            <div>
              <div className="spinner" />
              Loading your plans
            </div>
          </div>
        ) : plans.length === 0 ? (
          <div className="empty-state">
            <h2>Nothing planned yet, {user?.display_name}</h2>
            <p>
              A plan belongs to a degree, and there are ten to choose from across
              engineering and arts and sciences. Pick one and the app will lay out a
              complete first draft for you.
            </p>
            <Link className="btn btn-primary btn-lg" to="/plans/new">
              Choose a degree
            </Link>
          </div>
        ) : (
          <div className="grid-cards stagger">
            {plans.map((plan) => {
              const program = programs[plan.program_id];
              return (
                <div key={plan.id} className="program-card" style={{ cursor: "default" }}>
                  <span className="top">
                    <h3>
                      <Link to={`/plans/${plan.id}`} style={{ textDecoration: "none" }}>
                        {plan.name}
                      </Link>
                    </h3>
                    {program ? <span className="degree">{program.degree}</span> : null}
                  </span>
                  <p>{program ? program.name : "Loading degree"}</p>
                  <span className="meta">
                    Starting {plan.start_year}
                    {program?.school ? ` · ${program.school}` : ""}
                  </span>
                  <div className="row" style={{ marginTop: "0.5rem", gap: "0.35rem" }}>
                    <Link className="btn btn-sm" to={`/plans/${plan.id}`}>
                      Open
                    </Link>
                    <Link className="btn btn-sm" to={`/plans/${plan.id}/audit`}>
                      Audit
                    </Link>
                    <Link className="btn btn-sm" to={`/plans/${plan.id}/compare`}>
                      Compare
                    </Link>
                    <div className="spacer" />
                    <button
                      type="button"
                      className="btn btn-sm btn-ghost"
                      onClick={() => remove(plan.id, plan.name)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <Toasts toasts={toasts} />
    </Shell>
  );
}

export function NewPlan() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const { toasts, push } = useToasts();
  const [programs, setPrograms] = useState([]);
  const [selected, setSelected] = useState(null);
  const [name, setName] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.programs().then(setPrograms).catch((failure) => push(failure.message, "error"));
  }, [push]);

  const schools = programs.reduce((acc, program) => {
    (acc[program.school] ||= []).push(program);
    return acc;
  }, {});

  async function create() {
    if (!selected) return;
    setBusy(true);
    try {
      const plan = await api.createPlan(token, {
        program_id: selected.id,
        name: name.trim() || `${selected.name} ${selected.degree}`,
        start_year: Number(year),
      });
      navigate(`/plans/${plan.id}`);
    } catch (failure) {
      push(failure.message, "error");
      setBusy(false);
    }
  }

  return (
    <Shell>
      <header className="topbar">
        <h1>Start a plan</h1>
      </header>

      <div className="page page-narrow stack" style={{ gap: "1.4rem" }}>
        <div className="page-head" style={{ marginBottom: 0 }}>
          <span className="eyebrow">Step one</span>
          <h1>Which degree?</h1>
          <p>
            The requirements, the number of terms and what counts toward what all come
            from the degree, so this is the first thing the app needs to know.
          </p>
        </div>

        {Object.entries(schools).map(([school, rows]) => (
          <div key={school} className="stack" style={{ gap: "0.6rem" }}>
            <span className="eyebrow">{school}</span>
            <div className="grid-cards">
              {rows.map((program) => (
                <button
                  key={program.code}
                  type="button"
                  className="program-card"
                  data-selected={selected?.id === program.id}
                  onClick={() => setSelected(program)}
                >
                  <span className="top">
                    <h3>{program.name}</h3>
                    <span className="degree">{program.degree}</span>
                  </span>
                  <p>{program.notes}</p>
                  <span className="meta">
                    {program.total_units ? `${program.total_units} course units` : "Major only"}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ))}

        {selected ? (
          <section className="panel stack" style={{ padding: "1.1rem", gap: "0.9rem" }}>
            <div>
              <span className="eyebrow">Step two</span>
              <h2 style={{ marginTop: "0.2rem" }}>Name it and pick a start year</h2>
            </div>
            <div className="row" style={{ gap: "0.7rem", flexWrap: "wrap" }}>
              <div className="field" style={{ flex: "2 1 16rem" }}>
                <label htmlFor="plan-name">Plan name</label>
                <input
                  id="plan-name"
                  type="text"
                  placeholder={`${selected.name} ${selected.degree}`}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </div>
              <div className="field" style={{ flex: "1 1 8rem" }}>
                <label htmlFor="plan-year">First fall</label>
                <input
                  id="plan-year"
                  type="number"
                  min="2000"
                  max="2100"
                  value={year}
                  onChange={(event) => setYear(event.target.value)}
                />
              </div>
            </div>
            <div className="row">
              <button className="btn btn-primary btn-lg" type="button" onClick={create} disabled={busy}>
                {busy ? "Creating..." : `Create ${selected.degree} plan`}
              </button>
              <span className="small muted">
                You can change the name later and switch degrees at any time.
              </span>
            </div>
          </section>
        ) : null}
      </div>

      <Toasts toasts={toasts} />
    </Shell>
  );
}
