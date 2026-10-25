import pytest

from app.ai.prompts import build_triage_user
from app.models.enums import PRIORITY_RANK, TicketCategory, TicketPriority
from app.scripts import ai_eval as ev

CATS = {c.value for c in TicketCategory}
PRIS = {p.value for p in TicketPriority}
ROY, GEN = "Royalty & Payments", "General Inquiry"


@pytest.fixture(scope="module")
def tickets():
    return ev.load_tickets()


@pytest.fixture(scope="module")
def books():
    return ev.load_books()


# ---------- dataset validity ----------

def test_ids_are_unique_and_the_set_is_big_enough(tickets):
    ids = [t["id"] for t in tickets]
    assert len(ids) == len(set(ids)) and len(ids) >= 25


def test_every_label_is_valid(tickets):
    for t in tickets:
        assert t["category"] in CATS and set(t["acceptable_categories"]) <= CATS, t["id"]
        assert t["category"] in t["acceptable_categories"], t["id"]
        assert t["priority"] in PRIS and set(t["acceptable_priorities"]) <= PRIS, t["id"]
        assert t["priority"] in t["acceptable_priorities"], t["id"]
        assert t["difficulty"] in {"easy", "hard", "ambiguous"}, t["id"]
        assert t["subject"].strip() and len(t["description"]) >= 10 and t["note"].strip(), t["id"]


def test_accepted_priorities_are_adjacent_levels(tickets):
    rank = {p.value: r for p, r in PRIORITY_RANK.items()}
    for t in tickets:
        ranks = sorted(rank[p] for p in t["acceptable_priorities"])
        assert ranks == list(range(ranks[0], ranks[-1] + 1)), t["id"]


def test_every_book_reference_exists_in_the_sample_data(tickets, books):
    for t in tickets:
        assert t["book_id"] is None or t["book_id"] in books, t["id"]


def test_coverage_of_categories_priorities_and_difficulties(tickets):
    for c in CATS:
        assert sum(1 for t in tickets if t["category"] == c) >= 2, c
    for p in PRIS:
        assert any(t["priority"] == p for t in tickets), p
    assert {t["difficulty"] for t in tickets} == {"easy", "hard", "ambiguous"}


def test_dataset_books_keep_their_nulls(books):
    b = books["BK013"]
    assert b.mrp is None and b.publication_date is None and b.available_on == []
    assert books["BK005"].royalty_paid == 0 and books["BK005"].last_payout_date is None


def test_triage_context_has_book_facts_but_no_author_identity(tickets, books):
    t = next(x for x in tickets if x["book_id"] == "BK005")
    text = build_triage_user(ev.make_context(t, books))
    assert "Between Two Temples" in text and "Ananya" not in text and "@" not in text


# ---------- scoring ----------

def label(priority="High", accepted=("High",), category=ROY, categories=(ROY,)):
    return {"id": "X", "category": category, "acceptable_categories": list(categories),
            "priority": priority, "acceptable_priorities": list(accepted)}


def test_exact_versus_accepted():
    t = label(accepted=("High", "Critical"), categories=(ROY, GEN))
    s = ev.score_one(t, GEN, "Critical")
    assert not s["cat_exact"] and s["cat_ok"] and not s["pri_exact"] and s["pri_ok"] and s["direction"] == "ok"


def test_under_and_over_triage_direction():
    t = label()
    assert ev.score_one(t, ROY, "Low")["direction"] == "under"
    assert ev.score_one(t, ROY, "Medium")["direction"] == "under"
    assert ev.score_one(t, ROY, "Critical")["direction"] == "over"
    assert ev.score_one(t, ROY, "High")["direction"] == "ok"


def test_urgent_flags():
    assert ev.score_one(label("High"), ROY, "Medium")["urgent_expected"] is True
    assert ev.score_one(label("High"), ROY, "Medium")["urgent_hit"] is False
    assert ev.score_one(label("High"), ROY, "Critical")["urgent_hit"] is True
    assert ev.score_one(label("Medium", ("Medium",)), ROY, "Medium")["urgent_expected"] is False


def test_wilson_interval():
    assert ev.wilson(0, 0) == (0.0, 0.0)
    lo, hi = ev.wilson(10, 10)
    assert hi == pytest.approx(1.0) and 0.7 < lo < 1.0
    lo, hi = ev.wilson(5, 10)
    assert lo < 0.5 < hi
    lo, hi = ev.wilson(0, 10)
    assert lo == 0.0 and 0.0 < hi < 0.4


# ---------- aggregation and report ----------

def result(t, pc, pp, difficulty="easy"):
    r = {**t, "difficulty": difficulty, "error": None, "pred_category": pc, "pred_priority": pp,
         "confidence": 0.9, "rationale": "because"}
    r.update(ev.score_one(t, pc, pp))
    return r


T_HIGH = label("High", ("High",), ROY, (ROY,)) | {"id": "X1"}
T_LOW = label("Low", ("Low",), GEN, (GEN,)) | {"id": "X2"}
ROWS = [
    result(T_HIGH, ROY, "High"),
    result(T_HIGH, ROY, "Low"),
    result(T_LOW, ROY, "Low"),
    {**T_LOW, "difficulty": "easy", "error": "ai_timeout", "pred_category": None, "pred_priority": None},
]


def test_summary_counts_only_answered_calls():
    s = ev.summarise(ROWS)
    assert (s["total"], s["answered"], s["failed"]) == (4, 3, 1)
    assert s["cat_ok"] == 2 and s["pri_ok"] == 2 and s["both_ok"] == 1
    assert s["urgent_total"] == 2 and s["urgent_caught"] == 1
    assert s["under"] == 1 and s["over"] == 0
    assert s["by_difficulty"]["easy"]["n"] == 3


def test_confusion_ignores_failed_calls():
    m = ev.confusion(ROWS)
    assert m[ROY][ROY] == 2 and m[GEN][ROY] == 1 and sum(m[GEN].values()) == 1


def test_report_lists_misses_and_failures():
    md = ev.render_report({"model": "m", "prompt_hash": "abc", "run_at": "now"},
                          ev.summarise(ROWS), ROWS, ev.confusion(ROWS), {})
    assert "AI triage evaluation" in md and "**X1**" in md and "under-triaged" in md and "ai_timeout" in md