"""Deterministic demo booking seed.

Books a fixed subset of slots so a fresh demo shows partial availability (some
windows already taken) instead of a suspiciously empty calendar. Deterministic:
no randomness — every other doctor (by profile order) gets their soonest free
window booked, relative to the provider's clock. Derived entirely from the
current KB profile, so a KB swap seeds the new company's staff automatically.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from .booking_provider import BookingProvider, SlotTakenError, StoreUnavailableError

logger = logging.getLogger(__name__)

_SEED_PATIENT = "Демо Пациент"
_SEED_CONTACT = "+7 700 000 00 00"


def seed_demo_appointments(provider: BookingProvider, instance_id: str) -> int:
    """Book every other doctor's soonest window. Returns how many were booked."""
    profile = provider._profile()  # type: ignore[attr-defined]
    now = provider.now()
    today = now.astimezone(_tz(profile)).date()
    booked = 0
    for index, doctor in enumerate(profile.doctors):
        if index % 2 != 0:
            continue  # every other doctor, deterministically
        slots = provider.get_slots(
            instance_id, date_from=today, date_to=today + timedelta(days=14),
            doctor_id=doctor.id,
        )
        if not slots:
            continue
        try:
            provider.book_slot(
                instance_id, doctor_id=doctor.id, start=slots[0].start,
                patient_name=_SEED_PATIENT, contact=_SEED_CONTACT,
            )
            booked += 1
        except (SlotTakenError, StoreUnavailableError):
            continue
    logger.info("Seeded %d demo appointments for %s", booked, instance_id)
    return booked


def _tz(profile):
    from zoneinfo import ZoneInfo

    return ZoneInfo(profile.timezone)
