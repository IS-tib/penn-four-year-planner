"""Drive the running app in a real browser and assert the flows actually work.

A verification script, not part of the deliverable's test suite. It exercises
every page end to end against a live backend: the landing page, registration,
choosing a degree, the planner and its prerequisite checking, the graph
highlighting, undo and redo, the eligibility picker, slot resolution, the
degree audit, the switch-major comparison, sharing, the public degree pages,
the responsive layout and sign out.

Run it with the backend on :8000 and the frontend dev server on :5173.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_URL", "http://127.0.0.1:5173")
SHOTS = Path(__file__).resolve().parent / "screenshots"
# Left unset, Playwright uses the Chromium it installed itself. Set CHROME_PATH
# to point at a specific binary instead.
CHROME = os.environ.get("CHROME_PATH")
PASSWORD = "a-good-password-1"

SHOTS.mkdir(exist_ok=True)

failures: list[str] = []
section = ""


def heading(text: str) -> None:
    global section
    section = text
    print(f"\n{text}")


def check(condition: bool, label: str) -> None:
    print(("  PASS  " if condition else "  FAIL  ") + label)
    if not condition:
        failures.append(f"{section}: {label}")


def html5_drag(page, source, target) -> None:
    """Playwright's mouse-based drag_to does not fire native HTML5 drag events."""
    page.evaluate(
        """([src, dst]) => {
            const data = new DataTransfer();
            const fire = (el, type) =>
                el.dispatchEvent(new DragEvent(type, {
                    dataTransfer: data, bubbles: true, cancelable: true,
                }));
            fire(src, "dragstart"); fire(dst, "dragover");
            fire(dst, "drop"); fire(src, "dragend");
        }""",
        [source.element_handle(), target.element_handle()],
    )


def start_drag(page, source) -> None:
    page.evaluate(
        """(src) => {
            window.__dt = new DataTransfer();
            src.dispatchEvent(new DragEvent("dragstart", {
                dataTransfer: window.__dt, bubbles: true, cancelable: true }));
        }""",
        source.element_handle(),
    )


def end_drag(page, source) -> None:
    page.evaluate(
        """(src) => src.dispatchEvent(new DragEvent("dragend", {
            dataTransfer: window.__dt, bubbles: true, cancelable: true }))""",
        source.element_handle(),
    )


def checks_text(page) -> str:
    return page.locator("section[aria-label='Plan checks']").inner_text()


def raw(page, selector: str = "body") -> str:
    """Text as it is written in the DOM.

    inner_text() returns what the screen shows, which means CSS
    text-transform has already been applied to it. Several labels here are
    uppercased in the stylesheet, so asserting against inner_text() would be
    asserting against the design rather than the content.
    """
    return page.locator(selector).first.text_content() or ""


def grid_card(page, code):
    return page.locator(".term .course").filter(has_text=code).first


with sync_playwright() as pw:
    launch = {"args": ["--no-sandbox"]}
    if CHROME:
        launch["executable_path"] = CHROME
    browser = pw.chromium.launch(**launch)
    context = browser.new_context(viewport={"width": 1500, "height": 1000}, accept_downloads=True)
    page = context.new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    heading("1. the landing page")
    page.goto(APP, wait_until="networkidle")
    # Each section below the fold fades in the first time it is scrolled to.
    # A full-page screenshot captures beyond the viewport without scrolling, so
    # the page has to be walked down and back before it is worth photographing;
    # otherwise the picture is a hero above four blank screens.
    for offset in range(0, 3400, 400):
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(120)
    page.wait_for_timeout(700)
    revealed = page.eval_on_selector_all(
        ".section[data-shown]", "els => els.map(e => e.dataset.shown)"
    )
    check(revealed and all(v == "true" for v in revealed), f"every section reveals ({revealed})")
    page.mouse.wheel(0, -4000)
    page.wait_for_timeout(1400)
    page.screenshot(path=f"{SHOTS}/01-landing.png", full_page=True)
    body = raw(page)
    check("Four years, laid out" in body, "hero copy renders")
    check(page.locator(".program-card").count() == 10, "all ten degrees are listed")
    check("School of Engineering and Applied Science" in body, "SEAS section renders")
    check("College of Arts and Sciences" in body, "College section renders")

    heading("2. the hero draws a real prerequisite graph")
    check(page.locator(".hero-graph .hero-node").count() == 7, "every node renders")
    # A gradient stroke measured against an object bounding box vanishes on a
    # horizontal line, which is how the CIS 1100 edge disappeared once. Asking
    # each path for its own length is what catches a path that is not there.
    lengths = page.eval_on_selector_all(
        ".hero-graph .hero-edge", "els => els.map(e => Math.round(e.getTotalLength()))"
    )
    check(len(lengths) == 6, f"every edge renders ({lengths})")
    check(all(length > 20 for length in lengths), "none of them is a degenerate path")
    # The last edge starts drawing at 0.86s and takes 1.1s, so anything under
    # two seconds is measuring the animation rather than its result.
    page.wait_for_timeout(1500)
    offsets = page.eval_on_selector_all(
        ".hero-graph .hero-edge",
        "els => els.map(e => parseFloat(getComputedStyle(e).strokeDashoffset))",
    )
    # Compared against a tolerance rather than to zero: a finished animation
    # settles to a sub-pixel float, and a half drawn edge is off by hundreds.
    check(
        all(offset < 1 for offset in offsets),
        f"the draw-in animation finishes rather than leaving edges half drawn ({offsets})",
    )

    heading("3. the replay on the landing page runs and can be stopped")
    # Polled rather than sampled twice a fixed interval apart, because the
    # replay loops on its own clock and this section does not start at the same
    # point in it every run.
    first = page.locator(".demo-check").get_attribute("data-state")
    flipped = False
    for _ in range(40):
        page.wait_for_timeout(300)
        if page.locator(".demo-check").get_attribute("data-state") != first:
            flipped = True
            break
    check(flipped, f"the check flips between failing and clear on its own (from {first})")
    page.get_by_role("button", name="Pause").click()
    paused = page.locator(".demo-mover").get_attribute("style")
    page.wait_for_timeout(4200)
    check(page.locator(".demo-mover").get_attribute("style") == paused, "pause holds it still")
    page.get_by_role("button", name="Play").click()
    check(page.locator(".demo-terms").count() == 1, "the replay is one element, not a video")

    heading("4. the public degree pages need no account")
    page.get_by_role("link", name="Browse degrees").first.click()
    page.wait_for_url("**/programs", timeout=10000)
    page.wait_for_selector(".program-card", timeout=10000)
    page.wait_for_timeout(400)
    check(page.locator(".program-card").count() == 10, "the degree index lists ten")
    page.locator(".program-card").filter(has_text="Bioengineering").first.click()
    page.wait_for_url("**/programs/BE-BSE", timeout=10000)
    page.wait_for_timeout(700)
    detail = page.inner_text("body")
    check("Bioengineering" in detail, "the degree page loads")
    check("BE 3060" in detail or "Cellular" in detail, "its requirement rows render")
    check("catalog source" in detail, "it links back to the catalog")
    page.screenshot(path=f"{SHOTS}/02-degree.png", full_page=True)

    heading("5. register")
    email = f"e2e-{uuid.uuid4().hex[:8]}@upenn.edu"
    page.goto(f"{APP}/signup", wait_until="networkidle")
    page.fill("#displayName", "Isabella")
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.get_by_role("button", name="Create account").click()
    page.wait_for_url("**/plans", timeout=15000)
    page.wait_for_timeout(700)
    check("Nothing planned yet" in page.inner_text("body"), "a new account starts with no plan")
    check(page.locator(".sidebar").count() == 1, "the app shell renders")

    heading("6. choosing a degree")
    page.get_by_role("link", name="Choose a degree").click()
    page.wait_for_url("**/plans/new", timeout=10000)
    page.wait_for_timeout(600)
    check(page.locator(".program-card").count() == 10, "every degree is offered")
    page.locator(".program-card").filter(has_text="Computer Science").filter(
        has_text="BSE"
    ).first.click()
    page.wait_for_timeout(400)
    check("Name it and pick a start year" in page.inner_text("body"), "step two appears")
    page.screenshot(path=f"{SHOTS}/03-choose-degree.png", full_page=True)
    page.fill("#plan-name", "Class of 2030")
    page.fill("#plan-year", "2026")
    page.get_by_role("button", name="Create BSE plan").click()
    page.wait_for_selector(".term", timeout=15000)
    check(page.locator(".term").count() == 8, "eight terms render")
    check("Class of 2030" in page.locator(".plan-name").input_value(), "the name is kept")

    heading("7. the catalog opens filtered to the degree")
    filtered = page.locator(".catalog-list .course").count()
    first_codes = [
        c.strip() for c in page.locator(".catalog-list .course .course-code").all_text_contents()[:4]
    ]
    check(all(not code.startswith("BE ") for code in first_codes),
          f"another school's courses are not what a CS plan opens on ({first_codes})")
    page.get_by_label("Only what counts toward this degree").uncheck()
    page.wait_for_timeout(300)
    everything = page.locator(".catalog-list .course").count()
    check(everything > filtered, f"unticking it widens the catalog ({filtered} to {everything})")
    check(filtered < 70, f"the filtered list is browsable ({filtered})")
    page.get_by_label("Only what counts toward this degree").check()
    page.wait_for_timeout(300)

    heading("8. an out-of-order prerequisite is caught by the server")
    page.fill("input[type=search]", "CIS 3200")
    page.wait_for_timeout(350)
    page.locator(".catalog-list .course").first.locator("button").first.click()
    page.locator(".term").first.click()
    page.wait_for_timeout(1000)
    check("CIS 3200 requires CIS 1210" in checks_text(page), "the missing prerequisite is named")
    check(page.locator(".course[data-flagged='true']").count() >= 1, "the course is flagged")
    page.screenshot(path=f"{SHOTS}/04-prerequisite-error.png", full_page=True)

    heading("9. clicking a check jumps to the course it blames")
    page.locator(".diag[data-jumpable='true']").first.click()
    page.wait_for_timeout(700)
    check(page.locator(".detail").count() == 1, "the detail panel opens")
    detail = page.locator(".detail").inner_text().lower()
    check("cis 3200" in detail, "it describes the right course")
    check("requires" in detail and "cis 1210" in detail, "prerequisites are listed")
    check("required by" in detail, "dependents are listed")

    heading("10. focusing a course highlights its neighbourhood")
    page.fill("input[type=search]", "")
    page.wait_for_timeout(400)
    # Take the deliberately illegal placement back out. Autofill fills in around
    # what is already placed rather than moving it, which is the behaviour we
    # want, so leaving CIS 3200 in the first term would leave a real error
    # standing and the next few checks would be measuring this test's mess
    # rather than the app's.
    page.get_by_role("button", name="Remove CIS 3200 from this plan").click()
    page.wait_for_timeout(900)
    check("all clear" in checks_text(page), "removing it clears the error")
    page.get_by_role("button", name="Autofill").click()
    page.wait_for_timeout(3500)
    page.locator(".term .course").filter(has_text="CIS 1200").first.locator("button").first.click()
    page.wait_for_timeout(600)
    check(page.locator(".years").get_attribute("data-focused") == "true", "the grid dims")
    check(
        page.locator(".course[data-relation='dependent']").count() >= 2,
        "courses that depend on CIS 1200 are marked",
    )
    page.screenshot(path=f"{SHOTS}/05-graph-focus.png", full_page=True)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    heading("11. autofill produced a complete degree")
    check("all clear" in checks_text(page), "no errors or warnings")
    snapshot = page.locator("section[aria-label='Degree progress']").inner_text()
    check("24/24" in snapshot, f"every requirement is filled ({snapshot.splitlines()[:4]})")
    loads = [page.locator(".term").nth(i).inner_text() for i in range(8)]
    check(all("CU" in text for text in loads), "every term shows a credit total")
    page.screenshot(path=f"{SHOTS}/06-full-plan.png", full_page=True)

    heading("12. undo and redo")
    page.get_by_role("button", name="Undo").click()
    page.wait_for_timeout(1200)
    check("24/24" not in page.locator("section[aria-label='Degree progress']").inner_text(),
          "undo reversed the autofill in one step")
    page.get_by_role("button", name="Redo").click()
    page.wait_for_timeout(1400)
    check("24/24" in page.locator("section[aria-label='Degree progress']").inner_text(),
          "redo put the whole plan back")

    heading("13. the per-term picker offers only what is legal")
    page.locator(".term").nth(1).locator(".term-add").click()
    page.wait_for_selector(".dialog", timeout=6000)
    page.wait_for_timeout(800)
    listed = page.locator(".picker-row").all_inner_texts()
    check(len(listed) > 5, f"the picker lists eligible courses ({len(listed)})")
    check(not any(t.startswith("CIS 1200") for t in listed), "a planned course is not offered again")
    page.screenshot(path=f"{SHOTS}/07-picker.png", full_page=True)
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)

    heading("14. resolving a requirement slot into a real course")
    slot = page.locator(".term .course[data-slot='true']").first
    slot_code = slot.locator(".course-code").inner_text()
    slot.hover()
    slot.locator(".course-icon").first.click()
    page.wait_for_selector(".dialog", timeout=6000)
    page.wait_for_timeout(800)
    check(f"Fill {slot_code}" in page.locator(".dialog-head").inner_text(), "the dialog names the slot")
    offered = page.locator(".picker-row").all_inner_texts()
    check(len(offered) > 0, f"real courses are offered ({len(offered)})")
    chosen = page.locator(".picker-row").first
    chosen_code = chosen.locator(".picker-code").inner_text()
    chosen.click()
    page.wait_for_timeout(1400)
    check(slot_code not in page.inner_text(".years"), f"{slot_code} left the grid")
    check(chosen_code in page.inner_text(".years"), f"{chosen_code} took its place")
    check("24/24" in page.locator("section[aria-label='Degree progress']").inner_text(),
          "the resolved course still satisfies the requirement")

    heading("15. dragging marks which terms are legal")
    senior = grid_card(page, "CIS 4000")
    start_drag(page, senior)
    page.wait_for_timeout(500)
    check(page.locator(".term[data-legal]").count() == 8, "every term is marked mid-drag")
    check(page.locator(".term[data-legal='false']").count() == 6,
          "the senior project is illegal in the first six terms")
    page.screenshot(path=f"{SHOTS}/08-drag-legality.png", full_page=True)
    end_drag(page, senior)
    page.wait_for_timeout(400)
    check(page.locator(".term[data-legal]").count() == 0, "the marking clears afterwards")

    heading("16. dragging a gating course breaks what depends on it")
    html5_drag(page, grid_card(page, "CIS 1200"), page.locator(".term").nth(7))
    page.wait_for_timeout(1400)
    broken = checks_text(page)
    check("CIS 1210" in broken and "CIS 2400" in broken, "both direct dependents are flagged")
    page.screenshot(path=f"{SHOTS}/09-broken-by-drag.png", full_page=True)
    html5_drag(page, grid_card(page, "CIS 1200"), page.locator(".term").nth(0))
    page.wait_for_timeout(1400)
    check(page.locator(".diag[data-severity='error']").count() == 0, "putting it back clears them")

    heading("17. the degree audit page")
    page.get_by_role("link", name="Degree audit").click()
    page.wait_for_url("**/audit", timeout=10000)
    page.wait_for_timeout(1200)
    audit = raw(page)
    check("Computer Science BSE" in audit, "it names the degree")
    check("requirements filled" in audit, "it summarises progress")
    check(page.locator(".req").count() > 15, "every requirement row is listed")
    check(page.locator(".req[data-satisfied='true']").count() > 15, "they are ticked off")
    page.screenshot(path=f"{SHOTS}/10-audit.png", full_page=True)

    heading("18. switching majors")
    page.get_by_role("link", name="Switch major").click()
    page.wait_for_url("**/compare", timeout=10000)
    page.wait_for_timeout(900)
    check(page.locator(".program-card").count() == 9, "the other nine degrees are offered")
    page.locator(".program-card").filter(has_text="Bioengineering").first.click()
    page.wait_for_selector(".verdict", timeout=12000)
    page.wait_for_timeout(600)
    verdict = raw(page, ".verdict")
    check("extra semester" in verdict or "fits in the terms" in verdict, f"a verdict is given")
    check("carries over" in verdict, "it says how much carries over")
    stats = page.locator(".stat").all_inner_texts()
    check(len(stats) >= 4, "the numbers behind it are shown")
    check("longest chain still ahead" in raw(page), "both bounds are explained")
    page.screenshot(path=f"{SHOTS}/11-compare.png", full_page=True)

    page.locator(".program-card").filter(has_text="Computer Engineering").first.click()
    page.wait_for_timeout(1600)
    check("Computer Engineering" in raw(page, ".verdict"),
          "comparing a second degree works")

    heading("19. the plan survives a reload")
    page.goto(f"{APP}/plans", wait_until="networkidle")
    page.wait_for_timeout(900)
    check("Class of 2030" in page.inner_text("body"), "the plan is listed on the dashboard")
    page.get_by_role("link", name="Open").first.click()
    page.wait_for_selector(".term", timeout=12000)
    page.wait_for_timeout(700)
    check("24/24" in page.locator("section[aria-label='Degree progress']").inner_text(),
          "it reloads complete")
    check(page.locator("button[aria-label='Undo']").is_disabled(),
          "history does not survive a reload, and the button says so")

    heading("20. CSV export")
    with page.expect_download() as info:
        page.get_by_role("button", name="Export").click()
    download = info.value
    text = open(download.path()).read()
    check(download.suggested_filename.endswith(".csv"), "a CSV downloads")
    check(text.startswith("Term,Course,Title,Course Units,Fills"), "it has a header row")
    check("Computer Science" in text, "it records the degree")

    heading("21. sharing")
    page.get_by_role("button", name="Share").click()
    page.wait_for_selector(".dialog", timeout=6000)
    page.get_by_role("button", name="Create a read-only link").click()
    page.wait_for_selector("#share-url", timeout=6000)
    share_url = page.locator("#share-url").input_value()
    check("/shared/" in share_url, f"a share URL is produced ({share_url[:44]}...)")
    page.keyboard.press("Escape")

    stranger = browser.new_context(viewport={"width": 1400, "height": 950})
    guest = stranger.new_page()
    guest.goto(share_url, wait_until="networkidle")
    guest.wait_for_selector(".term", timeout=15000)
    guest_body = guest.inner_text("body")
    check("read only" in guest.inner_text(".topbar").lower(), "it is marked read only")
    check("shared by Isabella" in guest_body, "it names the owner")
    check("Computer Science BSE" in guest_body, "it names the degree")
    check(guest.locator(".term").count() == 8, "the whole plan renders")
    check(guest.locator(".rail-left").count() == 0, "there is no catalog to edit from")
    check(guest.locator(".term-add").count() == 0, "terms cannot be added to")
    check(guest.locator(".sidebar").count() == 0, "no signed-in navigation leaks through")
    check(email not in guest_body, "the owner's email is not exposed")
    guest.screenshot(path=f"{SHOTS}/12-shared.png", full_page=True)

    heading("22. revoking the link breaks it")
    page.get_by_role("button", name="Share").click()
    page.wait_for_selector(".dialog", timeout=6000)
    page.get_by_role("button", name="Turn the link off").click()
    page.wait_for_timeout(1000)
    page.keyboard.press("Escape")
    guest.goto(share_url, wait_until="networkidle")
    guest.wait_for_timeout(1000)
    check("Link not available" in guest.inner_text("body"), "the revoked link is refused")
    stranger.close()

    heading("23. dark mode")
    page.get_by_role("button", name="Toggle dark mode").click()
    page.wait_for_timeout(500)
    check(page.locator("html").get_attribute("data-theme") == "dark", "dark theme applies")
    page.screenshot(path=f"{SHOTS}/13-dark.png", full_page=True)

    # The sidebar, the hero and the verdict panel carry light text on a dark
    # ground in both themes. If they take their colour from the palette they
    # invert with it, and white text lands on a pale navy panel. Nothing about
    # that shows up in a test that only asserts the theme attribute flipped, so
    # the actual rendered luminance is what gets checked.
    def luminance(selector: str) -> float:
        return page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return -1;
                const bg = getComputedStyle(el).backgroundImage + getComputedStyle(el).backgroundColor;
                const nums = (bg.match(/\\d+(\\.\\d+)?/g) || []).map(Number);
                const rgb = nums.slice(0, 3);
                if (rgb.length < 3) return -1;
                return (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255;
            }""",
            selector,
        )

    check(0 <= luminance(".sidebar") < 0.3, "the sidebar stays dark furniture in dark mode")
    page.goto(f"{APP}/", wait_until="networkidle")
    page.wait_for_timeout(600)
    check(0 <= luminance(".hero") < 0.3, "so does the hero")
    page.screenshot(path=f"{SHOTS}/15-dark-landing.png", full_page=True)
    page.go_back()
    page.wait_for_selector(".term", timeout=15000)
    page.get_by_role("button", name="Toggle dark mode").click()
    page.wait_for_timeout(400)

    heading("24. mobile layout")
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(700)
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    check(overflow <= 1, f"no horizontal overflow at 390px (overflow {overflow}px)")
    page.screenshot(path=f"{SHOTS}/14-mobile.png", full_page=True)
    page.goto(f"{APP}/", wait_until="networkidle")
    page.wait_for_timeout(600)
    landing_overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    check(landing_overflow <= 1, f"the landing page fits too ({landing_overflow}px)")
    page.set_viewport_size({"width": 1500, "height": 1000})

    heading("25. signing out and back in")
    page.goto(f"{APP}/plans", wait_until="networkidle")
    page.wait_for_timeout(700)
    page.get_by_role("button", name="Sign out").click()
    page.wait_for_timeout(900)
    check("/plans" not in page.url, "signing out leaves the app")
    page.goto(f"{APP}/plans", wait_until="networkidle")
    page.wait_for_timeout(900)
    check("/signin" in page.url, "a protected page redirects when signed out")

    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url("**/plans", timeout=15000)
    page.wait_for_timeout(800)
    check("Class of 2030" in page.inner_text("body"), "the plan is back after signing in")

    heading("26. a wrong password is refused")
    page.get_by_role("button", name="Sign out").click()
    page.wait_for_timeout(600)
    page.goto(f"{APP}/signin", wait_until="networkidle")
    page.fill("#email", email)
    page.fill("#password", "definitely-wrong")
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_timeout(1100)
    check(page.locator(".form-error").count() == 1, "an error is shown")
    check("Incorrect email or password" in page.inner_text(".form-error"), "the wording is right")

    # Google Fonts is unreachable from this sandbox and the wrong password is a
    # deliberate 401, so neither counts as an application error.
    ignorable = ("favicon", "401", "ERR_TUNNEL_CONNECTION_FAILED", "fonts.g", "404")
    real_errors = [e for e in errors if not any(token in e for token in ignorable)]
    heading("27. console")
    check(not real_errors, f"no unexpected console errors ({real_errors[:3]})")

    context.close()
    browser.close()

print("\n" + "=" * 66)
if failures:
    print(f"{len(failures)} CHECK(S) FAILED:")
    for item in failures:
        print(f"  - {item}")
    sys.exit(1)
print("All browser checks passed.")
