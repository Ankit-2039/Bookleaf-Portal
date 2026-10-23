import enum


class UserRole(str, enum.Enum):
    AUTHOR = "author"
    ADMIN = "admin"


class TicketStatus(str, enum.Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class TicketCategory(str, enum.Enum):
    ROYALTY = "Royalty & Payments"
    ISBN = "ISBN & Metadata Issues"
    PRINTING = "Printing & Quality"
    DISTRIBUTION = "Distribution & Availability"
    PRODUCTION = "Book Status & Production Updates"
    GENERAL = "General Inquiry"


class TicketPriority(str, enum.Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


# Lower number = more urgent. Mongo sorts strings alphabetically, so the queue
# sorts on this integer instead of the priority label.
PRIORITY_RANK = {
    TicketPriority.CRITICAL: 0,
    TicketPriority.HIGH: 1,
    TicketPriority.MEDIUM: 2,
    TicketPriority.LOW: 3,
}


class ClassificationStatus(str, enum.Enum):
    PENDING = "pending"   # AI not run yet
    OK = "ok"             # AI result saved
    FAILED = "failed"     # AI call failed; fallback values in use


class MessageKind(str, enum.Enum):
    PUBLIC = "public"
    INTERNAL = "internal"