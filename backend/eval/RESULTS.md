# AI triage evaluation

Model `openai/gpt-oss-120b` · triage prompt hash `f10a052562` · run 2026-10-25 12:28 UTC
28 labelled tickets: 28 answered, 0 failed calls (failures are listed below, not counted as correct).

## Results

| Metric | Result |
|---|---|
| Category correct (any accepted label) | 100% (28/28), 95% CI 88–100% |
| Category equals the primary label | 96% (27/28) |
| Priority within the accepted levels | 93% (26/28), 95% CI 77–98% |
| Priority equals the primary label | 82% (23/28) |
| Both category and priority acceptable | 93% (26/28) |
| Urgent tickets caught (expected Critical/High, predicted Critical/High) | 100% (10/10) |
| Under-triaged (less urgent than any accepted level) | 0 |
| Over-triaged (more urgent than any accepted level) | 2 |

## By difficulty

| Difficulty | Tickets | Category ok | Priority ok |
|---|---|---|---|
| ambiguous | 5 | 100% (5/5) | 100% (5/5) |
| easy | 14 | 100% (14/14) | 93% (13/14) |
| hard | 9 | 100% (9/9) | 89% (8/9) |

## Category confusion (expected vs predicted, primary label)

| expected ↓ · predicted → | ROY | ISBN | PRINT | DIST | PROD | GEN |
|---|---|---|---|---|---|---|
| ROY | 7 | · | · | · | · | · |
| ISBN | · | 3 | · | · | · | · |
| PRINT | · | · | 4 | · | · | · |
| DIST | · | · | · | 3 | · | · |
| PROD | · | · | · | · | 3 | · |
| GEN | · | 1 | · | · | · | 7 |

ROY = Royalty & Payments, ISBN = ISBN & Metadata, PRINT = Printing & Quality, DIST = Distribution & Availability, PROD = Book Status & Production, GEN = General Inquiry. Off-diagonal cells include predictions that were accepted as an alternative label.

## Misses

- **E03** [hard] Why haven't I been paid yet?: priority High (accepted Low, Medium; over-triaged). Model said: "Author reports unpaid royalties for a live book with pending amount, indicating urgent payment issue." Label note: Pending balance is below the Rs 1,000 minimum payout, so it rolls over: not overdue. Tests use of the book facts.
- **E15** [easy] Where is my book on Flipkart?: priority High (accepted Low, Medium; over-triaged). Model said: "Author's live book is missing on Flipkart, a platform availability issue requiring prompt attention." Label note: The record shows it is not listed on Flipkart.

## Confidence

Mean self-reported confidence: 0.98 when right, 0.99 when wrong. This is the model's own estimate and is not calibrated: do not present it as a probability.

## Cost and latency (triage)

Per ticket: 728 input tokens, 79 output tokens, 2111 ms, 1.00 calls (repair retries included). About 0.81M tokens per 1,000 tickets.

## Caveats

- 28 tickets is a small sample; the confidence intervals above show how much the numbers could move.
- The labels were written by the same person who wrote the prompt, so they share assumptions. Tickets written by someone else would be a stronger test.
- Editing the prompt after reading these results makes later numbers optimistic for this set; the prompt hash above says which version was measured.
- One run at low temperature: run-to-run variation was not measured.
