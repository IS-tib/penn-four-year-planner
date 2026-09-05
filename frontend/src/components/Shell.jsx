import { NavLink, useNavigate } from "react-router-dom";

import { useAuth } from "../auth.jsx";
import { useTheme } from "../theme.js";

/**
 * The signed-in layout: a persistent sidebar and a page area.
 *
 * The sidebar exists so the app has somewhere to put navigation that is not
 * the top of the planner. Before it, every control in the product competed for
 * the same strip of screen above the grid, which is why the planner felt like
 * one dense page rather than an application.
 */
export function Shell({ children, planLinks = [] }) {
  const { user, signOut } = useAuth();
  const [theme, setTheme] = useTheme();
  const navigate = useNavigate();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <strong>Course Map</strong>
          <span>Penn degree planner</span>
        </div>

        <nav className="nav" aria-label="Main">
          <span className="nav-label">Plan</span>
          <NavLink to="/plans" end>
            <span className="dot" aria-hidden="true" />
            My plans
          </NavLink>
          <NavLink to="/plans/new">
            <span className="dot" aria-hidden="true" />
            Start a plan
          </NavLink>

          {planLinks.length > 0 ? (
            <>
              <span className="nav-label">This plan</span>
              {planLinks.map((link) => (
                <NavLink key={link.to} to={link.to} end={link.end}>
                  <span className="dot" aria-hidden="true" />
                  {link.label}
                </NavLink>
              ))}
            </>
          ) : null}

          <span className="nav-label">Browse</span>
          <NavLink to="/programs">
            <span className="dot" aria-hidden="true" />
            Degrees
          </NavLink>
        </nav>

        <div className="sidebar-foot">
          <span className="who">Signed in as {user?.display_name}</span>
          <div className="row" style={{ gap: "0.35rem" }}>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              aria-label="Toggle dark mode"
            >
              {theme === "dark" ? "Light" : "Dark"}
            </button>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => {
                signOut();
                navigate("/");
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>

      <div className="main">{children}</div>
    </div>
  );
}
