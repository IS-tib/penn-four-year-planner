# Penn Four Year Planner

Lay out a Penn Computer Science BSE degree across all eight semesters, drag courses between terms, and find out immediately when the order does not actually work.

Live app: _add your Vercel URL here_
API: _add your Render URL here_

## What it is

Penn CS students plan their degree in a spreadsheet, and a spreadsheet cannot tell you that you have put CIS 3200 before CIS 2620. This does. You drag a course into a semester and the server checks the whole plan against the real prerequisite graph from the Penn catalog, then reports exactly what is wrong and why: which course, which term, and which term it would have to move to.

It also works the rule forwards. Press the plus on any semester and it lists every course whose prerequisites would be satisfied by then, ranked by how much each one opens up later. Press Autofill and it lays out a complete, valid four year schedule around whatever you have already placed by hand.

## Features

**Accounts.** Register and sign in with an email and password. Passwords are hashed with bcrypt and never stored as text. Sessions are signed JSON Web Tokens with an expiry. Every plan endpoint checks ownership, and a plan belonging to another account returns 404 rather than 403 so the response does not confirm that the plan exists. Sign in and registration are rate limited.

**The planner.** Eight terms laid out as four academic years. Drag a course from the catalog into a term, drag it between terms, or remove it. Each term shows its course-unit total against Penn's 5.5 CU overload threshold, with a load bar that animates as the total changes. While a course is being dragged, every term marks itself as a legal or illegal destination.

**Prerequisite checking, on the server.** Penn states prerequisites as boolean expressions, for example CIS 1210 requires "CIS 1200 AND CIS 1600" and MATH 2400 requires "MATH 1410 OR MATH 1610". The app stores these in conjunctive normal form and evaluates them against your placements. It distinguishes a prerequisite that is missing from the plan entirely from one that is scheduled too late, and it handles the cases where the catalog permits a corequisite, such as taking PHYS 0150 alongside MATH 1400.

**The graph, made visible.** Click any course and the plan reorganises around it: what it requires, what requires it, and what it is cross-listed as are all picked out wherever they sit, and everything unrelated dims. Click a failed check and the app jumps to the course it blames and flashes it. The detail panel turns the graph into something you can walk, one course at a time.

**What can I take here.** Every term has a picker that asks the server which courses would be legal in that term given the current plan. Results are ranked by how many courses each one leads to, so what keeps the degree moving floats to the top, and anything that would push the term over the load limit is flagged rather than hidden.

**Placeholder slots that resolve.** Requirement buckets that allow hundreds of courses are seeded as explicit slots, one per course unit the degree needs, so you can lay out four years before deciding what fills each hole. Later, the pencil on any slot swaps it for a real course from the same bucket, in the same term.

**Undo and redo**, over the whole plan, with Ctrl+Z and Ctrl+Shift+Z. It covers autofill too.

**Degree checks beyond ordering.** Cross-listed pairs such as CIS 4480 and CIS 5480 are one course under two numbers, so a plan holding both is caught as counting it twice, and either number satisfies the core requirement. The rule capping 1000-level CIS electives at one course unit is enforced.

**Degree progress.** Course units planned against the target for each requirement bucket in the BSE: CIS core, math and natural science, CIS electives, technical electives, general electives and the free elective.

**Sharing and export.** A revocable read-only link lets you send a plan to an advisor without them needing an account. CSV export, and a print stylesheet that drops the interface and prints just the plan.

**The rest.** Multiple plans per account, inline plan renaming, a dark mode that persists, a layout that works down to a 390px phone, and a keyboard and touch path for every drag interaction.

## How it is built

React 18 with Vite on the front, FastAPI with SQLAlchemy and SQLite on the back. No UI framework, no state library and no drag-and-drop library; the styling is hand written CSS and the dragging is the native HTML5 drag API.

```
backend/
  app/
    catalog.py            seed data, transcribed from the Penn catalog
    config.py             environment-driven settings
    models.py             SQLAlchemy tables
    schemas.py            Pydantic request and response shapes
    security.py           bcrypt hashing, JWT issue and verify
    deps.py               current user, plan ownership
    routers/              auth, courses, plans, shared
    services/
      planner.py          prerequisite, load and degree-rule validation
      eligibility.py      the same rules walked forwards
      autofill.py         the scheduler
      ratelimit.py        sliding-window limiter
      plans.py            assembling the API view of a plan
  tests/                  127 tests
frontend/
  src/
    graph.js              reading the prerequisite graph in the browser
    planState.js          optimistic edits and the undo history
    api.js                one fetch wrapper, typed errors
    auth.jsx              session context
    App.jsx               orchestration
    components/           auth, catalog, grid, picker, detail, share, checks
    *.test.js             34 unit tests
```

### Decisions worth explaining

**Prerequisites are stored in conjunctive normal form, not as strings.** Each prerequisite row belongs to a group. Courses inside a group are OR'd, and the groups are AND'd. "CIS 1200 AND CIS 1600" is two single-member groups; "MATH 1410 OR MATH 1610" is one group with two members. Every prerequisite in the seeded catalog fits that shape, which turns validation into a plain loop over groups rather than an expression parser. If Penn ever published a prerequisite that CNF could not express, this would need revisiting; nothing in the current catalog does.

**Validation lives on the server, and every mutation returns the whole plan.** Placing a course returns the full recomputed plan including diagnostics and progress, not just the row that changed. It costs one extra query and it removes a class of bug: the browser never decides whether a plan is valid, so the client and the server cannot drift apart, and a hand-rolled request cannot slip past the rules.

**Writes are optimistic anyway.** The browser applies a drag to its local state immediately, sends the request, and replaces its state with the server's answer when it arrives. A failed request restores the snapshot taken before the change and shows a toast. This matters because the API is on a free tier that sometimes takes a second to answer, and a drag that waits on a round trip feels broken. What the browser recomputes locally is deliberately only the arithmetic the eye checks straight away, which term a card is in and what each term totals. It never recomputes diagnostics, because a second implementation of the rules is a second thing to keep correct.

**Undo restores a snapshot rather than replaying inverses.** Reversing a single placement is easy, but autofill touches twenty courses at once and a swap is really two operations. Rather than defining an inverse per operation, the client keeps snapshots of the whole placement set and undo is one atomic `PUT` that sets the plan to exactly that. A half-applied undo is not a state the plan can be in.

**Eligibility and validation are the same rules in two directions.** The validator takes a placement and says what is wrong. The eligibility finder walks the same graph forwards and says what would be fine. Two implementations of one rule is a bug waiting to happen, so there is a test that places everything the finder offers for a term and asserts the validator accepts all of it.

**404 rather than 403 for someone else's plan.** A 403 confirms the id exists, which lets an attacker enumerate how many plans the service holds. There is a test for this, and one for every write path.

**The unique constraint is in the database.** A course cannot sit in two terms of the same plan. That is enforced by a `UNIQUE (plan_id, course_id)` constraint, not by a check in the request handler, because two concurrent requests can both pass an application-level check and only the constraint actually holds.

**Login timing does not leak which emails exist.** An unknown email still runs a bcrypt verify against a dummy hash, so a wrong email and a wrong password take about the same time.

**Passwords longer than 72 bytes are rejected outright.** bcrypt only hashes the first 72 bytes and silently ignores the rest, which would make two different long passwords interchangeable.

**Share links are the entire credential, so they are built like one.** The token comes from `secrets` rather than anything derived from the plan id, the public endpoint takes only a token and never an id, it is GET only, and the response is a separate schema that carries the plan content and the owner's display name but not their email, their plan id or the token itself.

### The scheduler

Autofill is the part I would most want to talk through.

The naive version is a topological sort of the prerequisite DAG with earliest-fit placement. It produces plans that are legal and useless. Because electives and placeholder slots have no prerequisites, they are ready immediately, so they take the first term and push CIS 1210 into third year. Earliest-fit also packs the early terms to the cap and leaves the last semester empty. I only noticed because I looked at a screenshot of the output.

The version here fixes both.

Ordering is by critical path. Each course gets a height: the length of the longest chain of courses that depend on it. CIS 1200 is high because CIS 1210, CIS 3200, CIS 2400 and the systems courses all sit downstream of it. A technical elective placeholder is zero. Scheduling by height descending puts the long chains into the early terms and lets the free-floating electives fill whatever is left.

Placement is balanced rather than earliest-fit. A course goes into the first term at or after its earliest legal term that is still under a soft target of roughly one eighth of the degree, and only uses the headroom up to the real 5.5 CU limit when no such term exists. The result is every term between 4.0 and 5.5 CU, which is exactly the full-time range, so a generated plan produces no load warnings at all. There is a test asserting that.

Two things the prerequisite graph cannot express are handled separately. CIS 4000 requires senior standing, which is not an edge to another course, so it carries a minimum term index and validation reports an error if you place it earlier. CIS 1100 has no formal prerequisite relationship with CIS 1200 but is plainly meant to come first, so it carries an advising preference that the scheduler honours and validation deliberately ignores. An advising convention is not a rule and should never raise an error against a student who had a good reason to deviate.

## The catalog data

Course codes, titles, course-unit values and prerequisite expressions are transcribed from `catalog.upenn.edu` (the CIS, MATH and PHYS course pages) and the Computer Science BSE program page. It is a curated subset, not the whole university catalog.

Requirement buckets that allow hundreds of different courses are seeded as placeholder slots instead, one per course unit the degree requires. Nothing in the seed file is invented: a course appears with its real title and real prerequisites, or it appears as a clearly labelled placeholder.

Fourteen courses are also listed at the 5000 level with an identical title, which is how Penn cross-lists between the undergraduate and masters catalogs. The BSE page confirms two of them explicitly, writing the core requirements as "CIS 4480/5480" and "CIS 4710/5710". Each pair shares an equivalence key, and the seeder refuses to start if two courses sharing a key have different titles, because a typo there would silently reject a legitimate plan.

One honest gap. The requirement buckets, added up from the line items on the program page, come to 36 CU, and Penn publishes the degree as 37. The catalog page does not make clear where the extra unit sits, so the app reports both numbers and says so in the interface rather than quietly picking one. This is a planning aid, not an official degree audit.

## Testing

127 backend tests under pytest and 34 frontend unit tests under Vitest.

```bash
cd backend && python -m pytest -q
cd frontend && npm test
```

The backend tests cover registration and login, token forgery and expiry, cross-account access on every write path, the prerequisite rules including OR groups and corequisites, cross-listing, the elective level cap, course-load thresholds, the database constraints, the rate limiter's sliding window, share link minting and revocation, CSV escaping, and the scheduler's output. The frontend tests cover the graph reading and the optimistic-update and history reducers, which are pure functions and worth testing directly.

There is also `e2e_check.py`, a Playwright script that drives the running app in a real browser through 79 assertions: registering, breaking a prerequisite on purpose, jumping from a check to the course it blames, focusing a course and confirming its neighbourhood lights up, undoing and redoing with the mouse and the keyboard, opening the picker and confirming it withholds a course whose prerequisite is unplanned, resolving a placeholder slot, catching a cross-listed duplicate, checking the legality marks that appear mid-drag, exporting a CSV, minting a share link and opening it in a browser context with no session, revoking it, and checking the 390px layout does not overflow. The screenshots in `screenshots/` come from that run.

That script earned its place. It found a bug nothing else could: `PUT` was missing from the CORS `allow_methods` list, so undo and redo silently did nothing in a real browser while all 119 tests passed, because the test client does not send preflight requests. `tests/test_cors.py` now enumerates every method the API serves and asserts each one survives a preflight, so that specific class of bug cannot come back.

## Running it locally

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export SECRET_KEY="any-long-random-string"
python -m uvicorn app.main:app --reload --port 8000
```

The database file and the course catalog are created on first start. Interactive API docs are at `http://localhost:8000/docs`.

Frontend, in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Deployment

The frontend is a static build for Vercel. Set `VITE_API_URL` to the deployed API URL in the Vercel project settings.

The backend runs on Render using the included `render.yaml`. Set `SECRET_KEY` to a long random string and `CORS_ORIGINS` to the Vercel URL.

One caveat worth knowing. Render's free tier has an ephemeral filesystem, so the SQLite file is wiped on every redeploy and accounts do not survive. `DATABASE_URL` is read from the environment, so pointing it at a hosted Postgres instance is a one-line change with no code edits; `psycopg[binary]` is the only extra dependency.

## Known limitations

Native HTML5 drag and drop does not fire on touch screens. Every drag has a second path that does work there: select a course, then tap a term. That path is also the keyboard path.

The rate limiter keeps its counters in this process's memory. Two web workers each get their own window, so the effective limit is the configured one times the worker count, and a restart forgets everything. Moving the counters to Redis would fix that without changing the interface. It also keys on `X-Forwarded-For`, which is spoofable by anyone talking to the origin directly; that raises the cost of a naive attack rather than stopping a determined one.

The session token is kept in `localStorage`, which is readable by any script that manages to run on the page. An httpOnly cookie would be safer, at the cost of needing CSRF protection, and for an app on its own origin with no third-party scripts the tradeoff was not obviously worth the complexity here.

Undo history lives in the browser tab and does not survive a reload, which the disabled button makes visible rather than hiding. Persisting it would mean storing plan revisions server-side, which is a real feature rather than a small addition.

The degree audit counts course units per bucket and enforces the cross-listing and 1000-level elective rules. It does not enforce the requirement that the technical electives cover specific subject areas.

## Time spent

Roughly four hours.
