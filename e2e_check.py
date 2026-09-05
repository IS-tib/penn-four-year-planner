"""Drive the running app in a real browser and assert the flows actually work.

This is a verification script, not part of the deliverable's test suite. It
exercises every feature end to end against a live backend: registration, the
prerequisite checking, the graph highlighting, the eligibility picker, slot
resolution, undo and redo, sharing, export, the responsive layout and sign out.

Run it with the backend on :8000 and the frontend dev server on :5173.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_URL", "http://127.0.0.1:5173/")
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
    """Playwright's mouse-based drag_to does not trigger native HTML5 drag
    events, so dispatch the real sequence with a shared DataTransfer."""
    page.evaluate(
        """([src, dst]) => {
            const data = new DataTransfer();
            const fire = (el, type) =>
                el.dispatchEvent(new DragEvent(type, {
                    dataTransfer: data, bubbles: true, cancelable: true,
                }));
            fire(src, "dragstart");
            fire(dst, "dragover");
            fire(dst, "drop");
            fire(src, "dragend");
        }""",
        [source.element_handle(), target.element_handle()],
    )


def start_drag(page, source) -> None:
    """Begin a drag and leave it in flight, to inspect the legality hints."""
    page.evaluate(
        """(src) => {
            window.__dt = new DataTransfer();
            src.dispatchEvent(new DragEvent("dragstart", {
                dataTransfer: window.__dt, bubbles: true, cancelable: true,
            }));
        }""",
        source.element_handle(),
    )


def end_drag(page, source) -> None:
    page.evaluate(
        """(src) => src.dispatchEvent(new DragEvent("dragend", {
            dataTransfer: window.__dt, bubbles: true, cancelable: true,
        }))""",
        source.element_handle(),
    )


def checks_text(page) -> str:
    return page.locator("section[aria-label='Plan checks']").inner_text()


def grid_card(page, code):
    return page.locator(".term .course").filter(has_text=code).first


def total(page) -> str:
    return page.locator(".progress-total strong").inner_text()


with sync_playwright() as pw:
    launch = {"args": ["--no-sandbox"]}
    if CHROME:
        launch["executable_path"] = CHROME
    browser = pw.chromium.launch(**launch)
    context = browser.new_context(
        viewport={"width": 1500, "height": 1000}, accept_downloads=True
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    heading("1. auth screen")
    page.goto(APP, wait_until="networkidle")
    page.screenshot(path=f"{SHOTS}/01-sign-in.png", full_page=True)
    check("Four years of Penn CS" in page.inner_text("body"), "landing copy renders")

    heading("2. register")
    email = f"e2e-{uuid.uuid4().hex[:8]}@upenn.edu"
    page.get_by_role("tab", name="Create account").click()
    page.fill("#displayName", "Isabella")
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.get_by_role("button", name="Create account").click()
    page.wait_for_selector(".topbar", timeout=15000)
    check(page.locator(".plan-name").input_value() == "My Four Year Plan", "starter plan loads")
    check(page.locator(".term").count() == 8, "eight terms render")
    check(page.locator("button[aria-label='Undo']").is_disabled(), "undo starts disabled")

    heading("3. place a course by selecting it then clicking a term")
    page.fill("input[type=search]", "CIS 1200")
    page.wait_for_timeout(250)
    page.locator(".catalog-list .course").first.locator("button").first.click()
    page.locator(".term").first.click()
    page.wait_for_timeout(700)
    check("CIS 1200" in page.locator(".term").first.inner_text(), "CIS 1200 lands in term one")
    check("1 CU" in page.locator(".term").first.inner_text(), "term credit total updates")
    check(not page.locator("button[aria-label='Undo']").is_disabled(), "undo is now available")

    heading("4. an out-of-order prerequisite is caught by the server")
    page.fill("input[type=search]", "CIS 3200")
    page.wait_for_timeout(250)
    page.locator(".catalog-list .course").first.locator("button").first.click()
    page.locator(".term").first.click()
    page.wait_for_timeout(900)
    check("CIS 3200 requires CIS 1210" in checks_text(page), "missing prerequisite is reported")
    check(page.locator(".diag[data-severity='error']").count() >= 1, "styled as an error")
    check(page.locator(".course[data-flagged='true']").count() >= 1, "the course is flagged")
    page.screenshot(path=f"{SHOTS}/03-prerequisite-error.png", full_page=True)

    heading("5. clicking a check jumps to the course it blames")
    page.locator(".diag[data-jumpable='true']").first.click()
    page.wait_for_timeout(700)
    check(page.locator(".detail").count() == 1, "the detail panel opens")
    check("CIS 3200" in page.locator(".detail").inner_text(), "it describes the right course")
    check(
        page.locator(".course[data-relation='focus']").count() >= 1,
        "the course is marked as focused",
    )

    heading("6. the detail panel shows the graph around a course")
    # inner_text returns rendered text, and the section headings are uppercased
    # by CSS, so compare case-insensitively.
    detail = page.locator(".detail").inner_text().lower()
    check("requires" in detail and "cis 1210" in detail, "prerequisites are listed")
    check("cis 2620" in detail, "both prerequisites are listed")
    check("required by" in detail, "dependents are listed")
    page.locator(".detail .code-chip").first.click()
    page.wait_for_timeout(500)
    check("CIS 1210" in page.locator(".detail").inner_text(), "chips navigate the graph")

    heading("7. focusing a course highlights its neighbourhood")
    page.fill("input[type=search]", "")
    page.wait_for_timeout(300)
    page.locator(".term .course").filter(has_text="CIS 1200").first.locator(
        "button"
    ).first.click()
    page.wait_for_timeout(500)
    check(
        page.locator(".years").get_attribute("data-focused") == "true",
        "the grid enters focused mode",
    )
    check(
        page.locator(".course[data-relation='dependent']").count() >= 2,
        "courses that depend on CIS 1200 are marked",
    )
    check(
        "CIS 1210" in page.locator(".course[data-relation='dependent']").first.inner_text()
        or page.locator(".course[data-relation='dependent']").count() >= 2,
        "CIS 1210 is among them",
    )
    page.screenshot(path=f"{SHOTS}/08-graph-focus.png", full_page=True)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    check(page.locator(".detail").count() == 0, "escape clears the focus")

    heading("8. undo and redo")
    before_undo = page.locator(".term").first.inner_text()
    check("CIS 3200" in before_undo, "CIS 3200 is in the first term to begin with")
    page.get_by_role("button", name="Undo").click()
    page.wait_for_timeout(900)
    check("CIS 3200" not in page.locator(".term").first.inner_text(), "undo removed it")
    check(page.locator(".diag[data-severity='error']").count() == 0, "and cleared the error")
    page.get_by_role("button", name="Redo").click()
    page.wait_for_timeout(900)
    check("CIS 3200" in page.locator(".term").first.inner_text(), "redo put it back")
    page.get_by_role("button", name="Undo").click()
    page.wait_for_timeout(900)
    check("CIS 3200" not in page.locator(".term").first.inner_text(), "undone again")

    heading("9. undo works from the keyboard")
    page.locator("body").click(position={"x": 5, "y": 400})
    page.keyboard.press("Control+z")
    page.wait_for_timeout(900)
    check("CIS 1200" not in page.locator(".term").first.inner_text(), "ctrl+z stepped back")
    page.keyboard.press("Control+Shift+z")
    page.wait_for_timeout(900)
    check("CIS 1200" in page.locator(".term").first.inner_text(), "ctrl+shift+z stepped forward")

    heading("10. the per-term picker offers only what is legal")
    page.locator(".term").nth(1).locator(".term-add").click()
    page.wait_for_selector(".dialog", timeout=5000)
    rows = page.locator(".picker-row")
    page.wait_for_timeout(600)
    listed = rows.all_inner_texts()
    check(len(listed) > 5, f"the picker lists eligible courses ({len(listed)})")
    check(
        any("CIS 2400" in text for text in listed),
        "CIS 2400 is offered, because CIS 1200 is in an earlier term",
    )
    check(
        not any("CIS 1210" in text for text in listed),
        "CIS 1210 is withheld, because CIS 1600 is not planned",
    )
    check(
        not any(text.startswith("CIS 1200") for text in listed),
        "a course already in the plan is not offered again",
    )
    page.screenshot(path=f"{SHOTS}/09-picker.png", full_page=True)
    page.locator(".picker-row").filter(has_text="CIS 2400").first.click()
    page.wait_for_timeout(900)
    check("CIS 2400" in page.locator(".term").nth(1).inner_text(), "picking places the course")
    check(page.locator(".dialog").count() == 0, "the dialog closes")

    heading("11. autofill still produces a clean plan")
    page.get_by_role("button", name="Autofill").click()
    page.wait_for_timeout(3000)
    check("all clear" in checks_text(page), "no errors or warnings after autofill")
    check(total(page).startswith("36 / 36"), f"the degree is complete (got {total(page)!r})")
    check("CIS 2400" in page.locator(".term").nth(1).inner_text(), "hand placements survived")
    page.screenshot(path=f"{SHOTS}/04-full-plan.png", full_page=True)

    heading("12. a placeholder slot can be resolved into a real course")
    slot = page.locator(".term .course").filter(has_text="TECH-").first
    slot_code = slot.locator(".course-code").inner_text()
    slot.hover()
    slot.locator(".course-icon").first.click()
    page.wait_for_selector(".dialog", timeout=5000)
    page.wait_for_timeout(600)
    check(f"Fill {slot_code}" in page.locator(".dialog-head").inner_text(), "the dialog names the slot")
    offered = page.locator(".picker-row").all_inner_texts()
    check(len(offered) > 0, f"real courses are offered for the slot ({len(offered)})")
    check(
        not any("TECH-" in text or "SSH-" in text for text in offered),
        "no other placeholder is offered as a replacement",
    )
    chosen = page.locator(".picker-row").first
    chosen_code = chosen.locator(".picker-code").inner_text()
    chosen.click()
    page.wait_for_timeout(1000)
    check(slot_code not in page.inner_text(".years"), f"{slot_code} is gone from the grid")
    check(chosen_code in page.inner_text(".years"), f"{chosen_code} took its place")
    check(total(page).startswith("36 / 36"), "the degree total is unchanged by the swap")

    heading("13. cross-listed duplicates are caught")
    page.fill("input[type=search]", "CIS 5710")
    page.wait_for_timeout(400)
    page.locator(".catalog-list .course").first.locator("button").first.click()
    page.locator(".term").nth(7).click()
    page.wait_for_timeout(1000)
    check(
        "same course cross-listed" in checks_text(page),
        "planning CIS 4710 and CIS 5710 is reported as double counting",
    )
    page.get_by_role("button", name="Undo").click()
    page.wait_for_timeout(900)
    check("same course cross-listed" not in checks_text(page), "undo clears it")
    page.fill("input[type=search]", "")
    page.wait_for_timeout(300)

    heading("14. dragging marks which terms are legal")
    source = grid_card(page, "CIS 1200")
    start_drag(page, source)
    page.wait_for_timeout(400)
    legal = page.locator(".term[data-legal='true']").count()
    illegal = page.locator(".term[data-legal='false']").count()
    check(legal + illegal == 8, "every term is marked while a drag is in flight")
    check(legal == 8, "CIS 1200 has no prerequisites, so every term is legal")
    end_drag(page, source)
    page.wait_for_timeout(300)

    senior = grid_card(page, "CIS 4000")
    start_drag(page, senior)
    page.wait_for_timeout(400)
    check(
        page.locator(".term[data-legal='false']").count() == 6,
        "the senior project is illegal in the first six terms",
    )
    page.screenshot(path=f"{SHOTS}/10-drag-legality.png", full_page=True)
    end_drag(page, senior)
    page.wait_for_timeout(300)
    check(page.locator(".term[data-legal]").count() == 0, "the marking clears after the drag")

    heading("15. dragging a gating course breaks what depends on it")
    html5_drag(page, grid_card(page, "CIS 1200"), page.locator(".term").nth(7))
    page.wait_for_timeout(1200)
    check("CIS 1200" in page.locator(".term").nth(7).inner_text(), "CIS 1200 moved by drag")
    broken = checks_text(page)
    check("CIS 1210" in broken and "CIS 2400" in broken, "both direct dependents are flagged")
    check(
        page.locator(".course[data-flagged='true']").count() >= 2,
        "the broken courses are highlighted in the grid",
    )
    page.screenshot(path=f"{SHOTS}/07-broken-by-drag.png", full_page=True)

    heading("16. the plan survives a reload")
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".topbar", timeout=15000)
    check("CIS 1200" in page.locator(".term").nth(7).inner_text(), "placement persisted")
    check(page.locator(".plan-name").input_value() == "My Four Year Plan", "session persisted")
    check(
        page.locator("button[aria-label='Undo']").is_disabled(),
        "history does not survive a reload, and the button says so",
    )

    heading("17. putting it back clears every error")
    html5_drag(page, grid_card(page, "CIS 1200"), page.locator(".term").nth(0))
    page.wait_for_timeout(1200)
    check(page.locator(".diag[data-severity='error']").count() == 0, "the plan is valid again")

    heading("18. CSV export")
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Export").click()
    download = download_info.value
    check(download.suggested_filename.endswith(".csv"), "a CSV file is downloaded")
    body = open(download.path()).read()
    check(body.startswith("Term,Course,Title,Course Units,Requirement"), "it has a header row")
    check("CIS 1200" in body and "Fall" in body, "it lists placements with their terms")
    check("Total planned" in body, "it ends with a total")

    heading("19. sharing")
    page.get_by_role("button", name="Share").click()
    page.wait_for_selector(".dialog", timeout=5000)
    page.get_by_role("button", name="Create a read-only link").click()
    page.wait_for_selector("#share-url", timeout=5000)
    share_url = page.locator("#share-url").input_value()
    check("?share=" in share_url, f"a share URL is produced ({share_url[:40]}...)")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    check(page.locator(".dialog").count() == 0, "escape closes the dialog")

    heading("20. a shared link opens without an account")
    stranger = browser.new_context(viewport={"width": 1400, "height": 950})
    guest = stranger.new_page()
    guest.goto(share_url, wait_until="networkidle")
    guest.wait_for_selector(".topbar", timeout=15000)
    # The badge is uppercased by CSS, and inner_text returns rendered text.
    check("read only" in guest.inner_text(".topbar").lower(), "it is marked read only")
    check("shared by Isabella" in guest.inner_text(".brand"), "it names the owner")
    check(guest.locator(".term").count() == 8, "the whole plan renders")
    check(guest.locator(".rail-left").count() == 0, "there is no catalog to edit from")
    check(guest.locator(".term-add").count() == 0, "terms cannot be added to")
    check(guest.locator(".course-actions .course-icon").count() == 0, "courses cannot be removed")
    check(email not in guest.inner_text("body"), "the owner's email is not exposed")
    guest.screenshot(path=f"{SHOTS}/11-shared.png", full_page=True)

    heading("21. revoking a share link breaks it")
    page.get_by_role("button", name="Share").click()
    page.wait_for_selector(".dialog", timeout=5000)
    page.get_by_role("button", name="Turn the link off").click()
    page.wait_for_timeout(900)
    page.keyboard.press("Escape")
    guest.goto(share_url, wait_until="networkidle")
    guest.wait_for_timeout(900)
    check("Link not available" in guest.inner_text("body"), "the revoked link is refused")
    stranger.close()

    heading("22. dark mode")
    page.get_by_role("button", name="Toggle dark mode").click()
    page.wait_for_timeout(400)
    check(page.locator("html").get_attribute("data-theme") == "dark", "dark theme applies")
    page.screenshot(path=f"{SHOTS}/05-dark.png", full_page=True)
    page.get_by_role("button", name="Toggle dark mode").click()
    page.wait_for_timeout(300)

    heading("23. mobile layout")
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(600)
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    check(overflow <= 1, f"no horizontal overflow at 390px (overflow {overflow}px)")
    page.locator(".term").first.locator(".term-add").click()
    page.wait_for_selector(".dialog", timeout=5000)
    dialog_overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    check(dialog_overflow <= 1, "the picker dialog fits on a phone too")
    page.screenshot(path=f"{SHOTS}/06-mobile.png", full_page=True)
    page.keyboard.press("Escape")
    page.set_viewport_size({"width": 1500, "height": 1000})
    page.wait_for_timeout(400)

    heading("24. signing out and back in")
    page.get_by_role("button", name="Sign out").click()
    page.wait_for_timeout(600)
    check(page.locator(".auth-card").count() == 1, "signed out returns to the auth screen")
    page.reload(wait_until="networkidle")
    check(page.locator(".auth-card").count() == 1, "sign out survives a reload")

    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_selector(".topbar", timeout=15000)
    check(total(page).startswith("36 / 36"), "the full plan is back after signing in again")

    heading("25. a wrong password is refused")
    page.get_by_role("button", name="Sign out").click()
    page.wait_for_timeout(400)
    page.fill("#email", email)
    page.fill("#password", "definitely-wrong")
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_timeout(900)
    check(page.locator(".auth-error").count() == 1, "wrong password shows an error")
    check("Incorrect email or password" in page.inner_text(".auth-error"), "error text is right")

    # Google Fonts is unreachable from this sandbox and the wrong password is a
    # deliberate 401, so neither counts as an application error.
    ignorable = ("favicon", "401", "ERR_TUNNEL_CONNECTION_FAILED", "fonts.g", "404")
    real_errors = [e for e in errors if not any(token in e for token in ignorable)]
    heading("26. console")
    check(not real_errors, f"no unexpected console errors ({real_errors[:3]})")

    context.close()
    browser.close()

print("\n" + "=" * 64)
if failures:
    print(f"{len(failures)} CHECK(S) FAILED:")
    for item in failures:
        print(f"  - {item}")
    sys.exit(1)
print("All browser checks passed.")
