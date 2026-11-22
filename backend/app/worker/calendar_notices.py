"""Worker task with the calendar notices of accepted rentals (F-50, H023-3).

Every 15 minutes both parties of each ``accepted`` rental receive:

* ``rental_starting`` on the eve of the start (``start_date`` = tomorrow);
* ``return_due`` on the eve of the end (``end_date`` = tomorrow);
* ``rental_overdue`` once the end has passed without completion (``end_date`` < today).

Dates are calendar days in America/Sao_Paulo. Duplicates are prevented by the partial unique
index ``uq_notifications_worker_user_type_rental`` (H022-1) with ``ON CONFLICT DO NOTHING``, so
running the task again never creates a second notice for the same party and event.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.rental_situation import today_br
from app.worker.registry import registry

# (type, date column that triggers it, comparison with the reference date, reference)
EVENTS = (
    ("rental_starting", "start_date", "=", "tomorrow"),
    ("return_due", "end_date", "=", "tomorrow"),
    ("rental_overdue", "end_date", "<", "today"),
)

# One row per party: the renter and the owner of the listing. Deleted accounts are skipped.
# The payload carries only identifiers, the snapshot title, the date and the role (section 5).
_INSERT = """
INSERT INTO notifications (user_id, type, rental_id, payload)
SELECT party.user_id, :type, r.id,
       jsonb_build_object(
           'rental_id', r.id,
           'listing_id', r.listing_id,
           'listing_title', COALESCE(r.listing_snapshot ->> 'title', l.title),
           '{date_column}', r.{date_column},
           'role', party.role
       )
FROM rentals r
JOIN listings l ON l.id = r.listing_id
CROSS JOIN LATERAL (VALUES (r.renter_id, 'renter'), (l.owner_id, 'owner')) AS party(user_id, role)
JOIN users u ON u.id = party.user_id AND u.deleted_at IS NULL
WHERE r.status = 'accepted' AND r.{date_column} {operator} :reference
ON CONFLICT (user_id, type, rental_id)
    WHERE type IN ('rental_starting', 'return_due', 'rental_overdue')
    DO NOTHING
"""


def send_calendar_notices(session: Session, now: datetime) -> int:
    """Insert the notices due at ``now``; return how many new rows were created."""
    today = today_br(now)
    references = {"today": today, "tomorrow": today + timedelta(days=1)}
    created = 0
    for notification_type, date_column, operator, reference in EVENTS:
        statement = text(_INSERT.format(date_column=date_column, operator=operator))
        result = session.execute(
            statement, {"type": notification_type, "reference": references[reference]}
        )
        created += result.rowcount or 0
    return created


@registry.register("calendar_notices", minutes=15)
def calendar_notices(session: Session, now: datetime) -> None:
    send_calendar_notices(session, now)
