from app.scripts.seed_demo import DEMO


def test_demo_keys_are_unique_and_complete():
    keys = [d[0] for d in DEMO]
    assert len(keys) == len(set(keys))
    for key, email, book, subject, description, hours, status, extra in DEMO:
        assert email.endswith("@email.com") and subject.strip() and len(description) >= 10
        assert status in {"Open", "In Progress", "Resolved"} and hours > 0
        assert ("reply" in extra or "note" in extra) <= ("assign" in extra)  # replies/notes need an assigned admin


def test_demo_covers_a_spread_of_ages_and_states():
    assert {d[6] for d in DEMO} == {"Open", "In Progress", "Resolved"}
    assert max(d[5] for d in DEMO) >= 7 * 24 and min(d[5] for d in DEMO) <= 3  # shows red and fresh ages