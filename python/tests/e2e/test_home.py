"""E2E: the home page lists every catalogued program, grouped by chapter."""

import re

import pytest
from playwright.sync_api import Page, expect

from gerald_na.registry import get_registry

pytestmark = pytest.mark.e2e

ENTRIES = get_registry().programs


def test_home_lists_programs_by_chapter(page: Page) -> None:
    page.goto("/")
    listing = page.get_by_test_id("program-list")
    expect(listing).to_be_visible()
    expect(listing.locator("[data-testid^='program-card-']")).to_have_count(len(ENTRIES))
    for entry in ENTRIES:
        section_id = (
            f"chapter-{entry.chapter}" if entry.book_ref_confirmed else "chapter-unconfirmed"
        )
        section = page.get_by_test_id(section_id)
        card = section.get_by_test_id(f"program-card-{entry.id}")
        expect(card).to_be_visible()
        expect(card.get_by_test_id(f"program-link-{entry.id}")).to_have_text(entry.title)
        expect(card.get_by_test_id(f"program-link-{entry.id}")).to_have_attribute(
            "href", f"/programs/{entry.id}"
        )
        badge = card.get_by_test_id(f"unconfirmed-badge-{entry.id}")
        expect(badge).to_have_count(0 if entry.book_ref_confirmed else 1)
        scan = "available" if entry.files.scan_pdf is not None else "missing"
        expect(card.get_by_test_id(f"scan-status-{entry.id}")).to_have_attribute("data-scan", scan)

    expect(page.get_by_test_id("chapter-1").locator("h2")).to_contain_text("Chapter 1")
    expect(page.get_by_test_id("chapter-3").locator("h2")).to_contain_text("Chapter 3")
    expect(page.get_by_test_id("chapter-4").locator("h2")).to_contain_text("Chapter 4")
    unconfirmed = page.get_by_test_id("chapter-unconfirmed")
    expect(unconfirmed.locator("h2")).to_have_text("Book reference unconfirmed")
    expect(unconfirmed.get_by_test_id("program-card-lagrange_interpolation")).to_be_visible()
    chapters = ((1, ("ch01_p01", "ch01_p02")), (3, ("ch03_p01", "ch03_p02")), (4, ("ch04_p01",)))
    for chapter, program_ids in chapters:
        section = page.get_by_test_id(f"chapter-{chapter}")
        expect(section.locator("[data-testid^='program-card-']")).to_have_count(len(program_ids))
        for program_id in program_ids:
            expect(section.get_by_test_id(f"program-card-{program_id}")).to_be_visible()


def test_home_link_opens_the_program(page: Page) -> None:
    page.goto("/")
    page.get_by_test_id("program-link-lagrange_interpolation").click()
    expect(page).to_have_url(re.compile(r"/programs/lagrange_interpolation$"))
    expect(page.get_by_test_id("program-title")).to_have_text("Lagrangian interpolation")
    page.get_by_test_id("nav-home").click()
    expect(page.get_by_test_id("program-list")).to_be_visible()
