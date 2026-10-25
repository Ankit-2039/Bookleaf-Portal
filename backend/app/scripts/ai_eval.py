"""Measure triage quality on labelled tickets: python -m app.scripts.ai_eval  (run from backend/).
Options: --limit N (quick partial run, writes no files), --delay SECONDS between calls."""
import argparse
import asyncio
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.ai.client import AIClient
from app.ai.context import BookFacts, TicketContext
from app.ai.errors import AIError
from app.ai.prompts import TRIAGE_SYSTEM
from app.ai.provider import UnconfiguredProvider, build_provider
from app.ai.triage import triage_ticket
from app.core.config import get_settings
from app.models.enums import PRIORITY_RANK, TicketCategory, TicketPriority

BACKEND = Path(__file__).resolve().parents[2]
TICKETS_FILE = BACKEND / "eval" / "eval_tickets.json"
DATASET_FILE = BACKEND / "data" / "bookleaf_sample_data.json"
RESULTS_DIR = BACKEND / "eval" / "results"
REPORT_FILE = BACKEND / "eval" / "RESULTS.md"
TODAY = date(2026, 10, 25)  # fixed, so runs stay comparable over time

RANK = {p.value: r for p, r in PRIORITY_RANK.items()}  # lower number = more urgent
URGENT = ("Critical", "High")
ABBR = {
    "Royalty & Payments": "ROY",
    "ISBN & Metadata Issues": "ISBN",
    "Printing & Quality": "PRINT",
    "Distribution & Availability": "DIST",
    "Book Status & Production Updates": "PROD",
    "General Inquiry": "GEN",
}
DIRECTION_TEXT = {"under": "under-triaged", "over": "over-triaged", "off": "off", "ok": "ok"}


# ------------------------------------------------------------------ data

def _date(v):
    return date.fromisoformat(v) if v else None


def _money(v):
    return Decimal(str(v)) if v is not None else None


def load_tickets() -> list[dict]:
    return json.loads(TICKETS_FILE.read_text(encoding="utf-8"))


def load_books() -> dict[str, BookFacts]:
    data = json.loads(DATASET_FILE.read_text(encoding="utf-8"))
    books: dict[str, BookFacts] = {}
    for author in data["authors"]:
        for b in author["books"]:
            books[b["book_id"]] = BookFacts(
                title=b["title"],
                status=b["status"],
                isbn=b.get("isbn"),
                publication_date=_date(b.get("publication_date")),
                mrp=_money(b.get("mrp")),
                copies_sold=b.get("total_copies_sold", 0),
                royalty_earned=_money(b.get("total_royalty_earned")) or Decimal("0"),
                royalty_paid=_money(b.get("royalty_paid")) or Decimal("0"),
                royalty_pending=_money(b.get("royalty_pending")) or Decimal("0"),
                last_payout_date=_date(b.get("last_royalty_payout_date")),
                print_partner=b.get("print_partner"),
                available_on=list(b.get("available_on", [])),
            )
    return books


def make_context(t: dict, books: dict[str, BookFacts]) -> TicketContext:
    digits = "".join(ch for ch in t["id"] if ch.isdigit())
    return TicketContext(
        ticket_number=int(digits or 0),
        subject=t["subject"],
        description=t["description"],
        status="Open",
        category=TicketCategory.GENERAL,   # placeholders: triage does not use them
        priority=TicketPriority.MEDIUM,
        created_at=datetime(2026, 10, 25, tzinfo=timezone.utc),
        author_first_name="Author",
        book=books[t["book_id"]] if t["book_id"] else None,
        today=TODAY,
    )


# ------------------------------------------------------------------ scoring

def score_one(t: dict, pred_category: str, pred_priority: str) -> dict:
    accepted = [RANK[p] for p in t["acceptable_priorities"]]
    pr = RANK[pred_priority]
    pri_ok = pred_priority in t["acceptable_priorities"]
    if pri_ok:
        direction = "ok"
    elif pr > max(accepted):      # less urgent than anything we would accept
        direction = "under"
    elif pr < min(accepted):      # more urgent than anything we would accept
        direction = "over"
    else:
        direction = "off"
    return {
        "cat_exact": pred_category == t["category"],
        "cat_ok": pred_category in t["acceptable_categories"],
        "pri_exact": pred_priority == t["priority"],
        "pri_ok": pri_ok,
        "direction": direction,
        "urgent_expected": t["priority"] in URGENT,
        "urgent_hit": pred_priority in URGENT,
    }


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion k/n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _mean(values):
    return sum(values) / len(values) if values else None


def summarise(results: list[dict]) -> dict:
    answered = [r for r in results if r["error"] is None]
    n = len(answered)

    def count(rows, key):
        return sum(1 for r in rows if r[key])

    urgent = [r for r in answered if r["urgent_expected"]]
    both = [r for r in answered if r["cat_ok"] and r["pri_ok"]]
    s = {
        "total": len(results),
        "answered": n,
        "failed": len(results) - n,
        "cat_exact": count(answered, "cat_exact"),
        "cat_ok": count(answered, "cat_ok"),
        "pri_exact": count(answered, "pri_exact"),
        "pri_ok": count(answered, "pri_ok"),
        "both_ok": len(both),
        "urgent_total": len(urgent),
        "urgent_caught": count(urgent, "urgent_hit"),
        "under": sum(1 for r in answered if r["direction"] == "under"),
        "over": sum(1 for r in answered if r["direction"] == "over"),
        "by_difficulty": {},
    }
    s["cat_ok_ci"] = wilson(s["cat_ok"], n)
    s["pri_ok_ci"] = wilson(s["pri_ok"], n)
    for d in sorted({r["difficulty"] for r in answered}):
        rows = [r for r in answered if r["difficulty"] == d]
        s["by_difficulty"][d] = {"n": len(rows), "cat_ok": count(rows, "cat_ok"), "pri_ok": count(rows, "pri_ok")}
    s["conf_when_right"] = _mean([r["confidence"] for r in both])
    s["conf_when_wrong"] = _mean([r["confidence"] for r in answered if not (r["cat_ok"] and r["pri_ok"])])
    return s


def confusion(results: list[dict]) -> dict[str, Counter]:
    matrix = {c.value: Counter() for c in TicketCategory}
    for r in results:
        if r["error"] is None:
            matrix[r["category"]][r["pred_category"]] += 1
    return matrix


# ------------------------------------------------------------------ report

def pct(k: int, n: int) -> str:
    return f"{round(100 * k / n)}% ({k}/{n})" if n else "n/a"


def _ci(ci: tuple[float, float]) -> str:
    return f"{round(ci[0] * 100)}–{round(ci[1] * 100)}%"


def _matrix_lines(conf: dict[str, Counter]) -> list[str]:
    cats = [c.value for c in TicketCategory]
    lines = [
        "| expected ↓ · predicted → | " + " | ".join(ABBR[c] for c in cats) + " |",
        "|---|" + "---|" * len(cats),
    ]
    for exp in cats:
        cells = [str(conf[exp][p]) if conf[exp][p] else "·" for p in cats]
        lines.append(f"| {ABBR[exp]} | " + " | ".join(cells) + " |")
    return lines


def render_report(meta: dict, s: dict, results: list[dict], conf: dict[str, Counter], usage: dict) -> str:
    n = s["answered"]
    L = [
        "# AI triage evaluation",
        "",
        f"Model `{meta['model']}` · triage prompt hash `{meta['prompt_hash']}` · run {meta['run_at']}",
        f"{s['total']} labelled tickets: {n} answered, {s['failed']} failed calls (failures are listed below, not counted as correct).",
        "",
        "## Results",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Category correct (any accepted label) | {pct(s['cat_ok'], n)}, 95% CI {_ci(s['cat_ok_ci'])} |",
        f"| Category equals the primary label | {pct(s['cat_exact'], n)} |",
        f"| Priority within the accepted levels | {pct(s['pri_ok'], n)}, 95% CI {_ci(s['pri_ok_ci'])} |",
        f"| Priority equals the primary label | {pct(s['pri_exact'], n)} |",
        f"| Both category and priority acceptable | {pct(s['both_ok'], n)} |",
        f"| Urgent tickets caught (expected Critical/High, predicted Critical/High) | {pct(s['urgent_caught'], s['urgent_total'])} |",
        f"| Under-triaged (less urgent than any accepted level) | {s['under']} |",
        f"| Over-triaged (more urgent than any accepted level) | {s['over']} |",
        "",
        "## By difficulty",
        "",
        "| Difficulty | Tickets | Category ok | Priority ok |",
        "|---|---|---|---|",
    ]
    for d, v in s["by_difficulty"].items():
        L.append(f"| {d} | {v['n']} | {pct(v['cat_ok'], v['n'])} | {pct(v['pri_ok'], v['n'])} |")

    L += ["", "## Category confusion (expected vs predicted, primary label)", ""]
    L += _matrix_lines(conf)
    L += ["", "ROY = Royalty & Payments, ISBN = ISBN & Metadata, PRINT = Printing & Quality, "
          "DIST = Distribution & Availability, PROD = Book Status & Production, GEN = General Inquiry. "
          "Off-diagonal cells include predictions that were accepted as an alternative label."]

    L += ["", "## Misses", ""]
    misses = [r for r in results if r["error"] is None and not (r["cat_ok"] and r["pri_ok"])]
    if not misses:
        L.append("None: every answered ticket was within the accepted labels.")
    for r in misses:
        problems = []
        if not r["cat_ok"]:
            problems.append(f"category {r['pred_category']} (expected {r['category']})")
        if not r["pri_ok"]:
            problems.append(
                f"priority {r['pred_priority']} (accepted {', '.join(r['acceptable_priorities'])}; "
                f"{DIRECTION_TEXT[r['direction']]})"
            )
        line = f"- **{r['id']}** [{r['difficulty']}] {r.get('subject', '')}: " + "; ".join(problems)
        line += f'. Model said: "{r.get("rationale", "")}"'
        if r.get("note"):
            line += f" Label note: {r['note']}"
        L.append(line)

    failed = [r for r in results if r["error"] is not None]
    if failed:
        L += ["", "## Failed calls", ""]
        L += [f"- **{r['id']}** {r.get('subject', '')}: {r['error']}" for r in failed]

    L += ["", "## Confidence", ""]
    if s["conf_when_right"] is not None:
        wrong = f"{s['conf_when_wrong']:.2f}" if s["conf_when_wrong"] is not None else "n/a"
        L.append(f"Mean self-reported confidence: {s['conf_when_right']:.2f} when right, {wrong} when wrong. "
                 "This is the model's own estimate and is not calibrated: do not present it as a probability.")

    if usage:
        k = len(usage)
        ain = sum(u["in"] for u in usage.values()) / k
        aout = sum(u["out"] for u in usage.values()) / k
        ams = sum(u["ms"] for u in usage.values()) / k
        calls = sum(u["calls"] for u in usage.values()) / k
        L += [
            "", "## Cost and latency (triage)", "",
            f"Per ticket: {ain:.0f} input tokens, {aout:.0f} output tokens, {ams:.0f} ms, {calls:.2f} calls (repair retries included). "
            f"About {(ain + aout) * 1000 / 1e6:.2f}M tokens per 1,000 tickets.",
        ]

    L += [
        "", "## Caveats", "",
        f"- {s['total']} tickets is a small sample; the confidence intervals above show how much the numbers could move.",
        "- The labels were written by the same person who wrote the prompt, so they share assumptions. Tickets written by someone else would be a stronger test.",
        "- Editing the prompt after reading these results makes later numbers optimistic for this set; the prompt hash above says which version was measured.",
        "- One run at low temperature: run-to-run variation was not measured.",
    ]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ run

async def run_one(client: AIClient, t: dict, ctx: TicketContext):
    for attempt in range(3):
        try:
            return await triage_ticket(client, ctx, ticket_id=t["id"]), None
        except AIError as e:
            if e.code == "ai_rate_limited" and attempt < 2:
                await asyncio.sleep(min(e.retry_after or 10, 60))
                continue
            return None, e.code
    return None, "ai_rate_limited"


async def evaluate(client: AIClient, tickets: list[dict], books: dict, delay: float) -> list[dict]:
    results = []
    for i, t in enumerate(tickets, 1):
        triage, error = await run_one(client, t, make_context(t, books))
        if triage is None:
            row = {**t, "error": error, "pred_category": None, "pred_priority": None}
            print(f"[{i}/{len(tickets)}] {t['id']} FAILED ({error})")
        else:
            pc, pp = triage.category.value, triage.priority.value
            row = {**t, "error": None, "pred_category": pc, "pred_priority": pp,
                   "confidence": triage.confidence, "rationale": triage.rationale, **score_one(t, pc, pp)}
            flag = "ok" if row["cat_ok"] and row["pri_ok"] else "MISS"
            print(f"[{i}/{len(tickets)}] {t['id']} {flag}: {pc} / {pp}")
        results.append(row)
        await asyncio.sleep(delay)
    return results


async def main(limit: int | None, delay: float) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to a narrow encoding
    except Exception:
        pass
    settings = get_settings()
    provider = build_provider(settings)
    if isinstance(provider, UnconfiguredProvider):
        raise SystemExit("LLM_API_KEY is not set in backend/.env")

    tickets = load_tickets()
    if limit:
        tickets = tickets[:limit]
    usage_rows: list[dict] = []

    async def sink(row: dict) -> None:
        usage_rows.append(row)

    results = await evaluate(AIClient(provider, usage_sink=sink), tickets, load_books(), delay)

    usage: dict = {}
    for row in usage_rows:
        u = usage.setdefault(row["ticket_id"], {"in": 0, "out": 0, "ms": 0, "calls": 0})
        u["in"] += row["input_tokens"] or 0
        u["out"] += row["output_tokens"] or 0
        u["ms"] += row["latency_ms"] or 0
        u["calls"] += 1

    meta = {
        "model": settings.llm_model,
        "prompt_hash": hashlib.sha256(TRIAGE_SYSTEM.encode("utf-8")).hexdigest()[:10],
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    summary = summarise(results)
    report = render_report(meta, summary, results, confusion(results), usage)
    print("\n" + report)

    if limit:
        print("Partial run (--limit): no files written.")
        return
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta, "summary": summary, "results": results}
    (RESULTS_DIR / "latest.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(f"Wrote {REPORT_FILE.relative_to(BACKEND)} and eval/results/latest.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=0.5)
    args = ap.parse_args()
    asyncio.run(main(args.limit, args.delay))