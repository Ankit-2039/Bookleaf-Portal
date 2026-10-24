from app.models.enums import TicketCategory

PAYOUT_THRESHOLD_INR = 1000

KB_SECTIONS: dict[str, str] = {
    "company": """\
COMPANY
- BookLeaf Publishing is a self-publishing company operating in India and the US.
- Publishing packages: Standard Free (no upfront cost) and Bestseller Breakthrough (premium, paid package with marketing and distribution add-ons).
- BookLeaf handles cover design, typesetting, ISBN assignment, printing, distribution and royalty management.
- The in-house printing facility and warehouse are in Delhi. Print partners: Repro India and Epitome Books.""",

    "royalty": """\
ROYALTY POLICY
- Royalty split: 80% of the net profit per book goes to the author, 20% to BookLeaf.
- Net profit = MRP minus printing cost, platform commission (Amazon/Flipkart) and shipping charges.
- Royalties are calculated quarterly and paid within 45 days of the quarter ending.
- Minimum payout threshold: ₹1,000. Accumulated royalties below this roll over to the next quarter.
- Payouts are made by bank transfer to the account linked in the author's dashboard.
- Authors can view a detailed royalty breakdown in their dashboard, showing sales figures per platform.
- Never calculate an individual author's exact royalty entitlement. Quote stored figures only; escalate discrepancies.
Response guide:
- "No royalty received yet": acknowledge the frustration; explain the quarterly cycle and the 45-day payout window; say the team will confirm the bank account linked in the dashboard; do not state a specific payout date unless one appears in the facts; if the payment looks genuinely overdue, own it and escalate with a 48-hour resolution timeline.
- "Royalty seems too low": explain net profit (MRP minus printing, platform commission and shipping); offer a detailed line-by-line royalty breakdown; be transparent and never defensive.""",

    "isbn": """\
ISBN POLICY
- Every book published through BookLeaf receives a unique ISBN assigned by BookLeaf, registered under BookLeaf's publisher imprint.
- An author who wants an ISBN under their own imprint must obtain it independently.
- A reported ISBN error (duplicate, wrong book linked, mismatch between platform and physical copy) is a high-priority issue escalated to the production team.
Response guide:
- ISBN error: treat as high priority; acknowledge it is a serious data issue; confirm it is being escalated to the production team immediately; give a 48-hour resolution timeline. Do not say it has been fixed.""",

    "metadata_updates": """\
METADATA UPDATES
- Metadata updates (for example a book description on Amazon) can be submitted through the dashboard or by emailing the BookLeaf team.
- Changes typically reflect on platforms within 3–5 business days.""",

    "printing": """\
PRINTING & QUALITY
- In-house printing handles most orders. Overflow or specific format requirements go to Repro India or Epitome Books.
- Standard print turnaround: 5–7 business days from order confirmation.
- For a quality issue (misprints, binding defects, color inconsistency) BookLeaf arranges a free reprint after verification. The author may need to share photos of the defective copy.
Response guide:
- Quality complaint: apologise sincerely; ask for photos of the defective copies; say a free reprint will be arranged once the defect is verified; give 5–7 business days for the reprint. Do not say the defect is verified or a reprint is ordered.""",

    "distribution": """\
DISTRIBUTION & AVAILABILITY
- Books are listed on Amazon India, Flipkart, Amazon US, Amazon UK and the BookLeaf Store.
- New listings typically go live within 7–10 business days after publication is complete.
- A book showing as unavailable on a platform usually indicates a stock sync issue. The BookLeaf team can trigger a re-sync, which takes 24–48 hours.
Response guide:
- "Currently Unavailable": explain it is typically a stock sync issue; say the team will trigger a re-sync with the distribution team; set the expectation of 24–48 hours. Do not say the re-sync has already been triggered.""",

    "production": """\
PRODUCTION STAGES
- Stages: Manuscript Received → Editing (if opted) → Cover Design → Typesetting → Proofreading → ISBN Assignment → Printing → Distribution Setup → Published & Live.
- Authors are updated at each stage via email.
- Delays typically happen at Cover Design (waiting for author approval) and Proofreading (revision rounds).
Response guide:
- Production question: use the stored book status from the facts, never an estimate based on elapsed time; if delayed, be honest about the typical reasons and frame it collaboratively, never blaming the author; give a specific updated timeline only if the facts support one, otherwise say the team will confirm within 48 hours.""",

    "tone": """\
COMMUNICATION TONE
- Always empathetic and professional. Authors are partners, not customers to be managed.
- Acknowledge the author's concern before jumping to solutions.
- Be specific: use actual numbers, dates and statuses from the facts, not vague reassurances.
- If something is BookLeaf's fault (delayed royalties, ISBN error), own it directly. No corporate deflection.
- If the issue requires escalation or investigation, give a clear timeline (for example "Our team will look into this and get back to you within 48 hours"), not an open-ended promise.
- Always end with a clear next step for the author and/or the BookLeaf team.""",
}

CATEGORY_SECTIONS: dict[TicketCategory, list[str]] = {
    TicketCategory.ROYALTY: ["royalty"],
    TicketCategory.ISBN: ["isbn", "metadata_updates"],
    TicketCategory.PRINTING: ["printing"],
    TicketCategory.DISTRIBUTION: ["distribution"],
    TicketCategory.PRODUCTION: ["production"],
    TicketCategory.GENERAL: ["company", "metadata_updates"],
}


def kb_context(category: TicketCategory, include_tone: bool = True) -> str:
    """Only the sections relevant to this category: this is how we control prompt size."""
    keys = list(CATEGORY_SECTIONS[category]) + (["tone"] if include_tone else [])
    return "\n\n".join(KB_SECTIONS[k] for k in keys)