"""Provider-backed booking sub-flow for the medical demo.

Active ONLY when a BookingProvider is wired in (app.state.booking_provider).
Without a provider the legacy fictional-slot flow in medical_center_demo.py runs
unchanged, so the existing test suite is untouched.

What it does when active: offer a specialty's doctor(s) with their real, dated
free windows (from the slot engine), let the visitor pick one, collect the
missing name/contact, then persist a confirmed booking to demo_appointments and
form the "готовая заявка" (demo CRM lead). Every slot it speaks comes from the
provider, so booking_guardrail validates it cleanly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from .booking_provider import BookingProvider, SlotTakenError, StoreUnavailableError, slots_to_labels
from .clinic_profile import ClinicProfile, Doctor
from .medical_center_slots import normalize_specialty, specialty_dative
from .medical_center_state import (
    ConversationState,
    apply_booking_field_seed,
    detect_symptom_specialty,
    is_affirmation,
)
from .schemas import ChatHistoryMessage
from .slot_engine import Slot

_DAY_WORDS = ("послезавтра", "завтра", "сегодня")
# Recover a slot the assistant already locked ("выбрали <label>") or confirmed
# ("Записали вас на <label>") from a previous turn — the server is stateless, so
# the pending choice lives only in the transcript.
_PENDING_LABEL_RE = re.compile(
    r"(?:выбрали|записали вас на)\s+(послезавтра|завтра|сегодня)\s+(\d{1,2}:\d{2})",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.](\d{2})\b")
_BARE_HOUR_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])(?!\d)")
_ORDINALS = (
    (re.compile(r"\bперв\w*|\b1[-\s]?(?:й|е|ый|вариант)\b", re.IGNORECASE), 0),
    (re.compile(r"\bвтор\w*|\b2[-\s]?(?:й|е|ой|вариант)\b", re.IGNORECASE), 1),
    (re.compile(r"\bтрет\w*|\b3[-\s]?(?:й|е|ий|вариант)\b", re.IGNORECASE), 2),
)


@dataclass
class BookingTurn:
    answer: str
    conversation_status: str
    offered_labels: list[str]
    appointment: object | None = None  # Appointment on confirm
    lead: dict | None = None


def find_specialty_id(profile: ClinicProfile, ru_specialty: str | None) -> str | None:
    """Map a canonical RU specialty ("офтальмолог") to the profile's specialty id
    by normalizing both sides — never a hardcoded clinic table."""
    canonical = normalize_specialty(ru_specialty)
    if not canonical:
        return None
    for specialty in profile.specialties:
        if normalize_specialty(specialty.name) == canonical:
            return specialty.id
    return None


# Adults default to a general practitioner, children to a paediatrician, when a
# symptom routes to a specialty this clinic cannot book (e.g. гастроэнтеролог has
# no doctor in the KB — the KB itself says "направление ведёт терапевт").
_GP_SPECIALTY_ADULT = "терапевт"
_GP_SPECIALTY_CHILD = "педиатр"


def _first_bookable_specialty(profile: ClinicProfile, text: str | None) -> str | None:
    """The earliest-mentioned BOOKABLE specialty in ``text``.

    Unlike normalize_specialty (which returns the first specialty by position,
    bookable or not), this scans only the profile's specialties — all of which
    have a doctor — so an ambiguous route like "гастроэнтеролог или терапевт"
    resolves to терапевт instead of the unbookable гастроэнтеролог."""
    low = (text or "").casefold()
    if not low:
        return None
    best: tuple[int, str] | None = None
    for specialty in profile.specialties:
        canonical = normalize_specialty(specialty.name)
        if not canonical:
            continue
        stem = canonical[: max(4, len(canonical) - 2)]  # tolerate declensions
        pos = low.find(stem)
        if pos != -1 and (best is None or pos < best[0]):
            best = (pos, specialty.id)
    return best[1] if best else None


def _gp_specialty(profile: ClinicProfile, state: ConversationState) -> str | None:
    gp = _GP_SPECIALTY_CHILD if getattr(state, "child_case", False) else _GP_SPECIALTY_ADULT
    return find_specialty_id(profile, gp)


def _booking_specialty(
    profile: ClinicProfile, state: ConversationState, message: str
) -> str | None:
    """A single bookable specialty to drive this booking, or None to defer.

    Order: the committed specialty, then one named in this message, then the
    symptom-routed one (picking a bookable option from an ambiguous route), then
    the GP fallback — but only when a complaint is known, so we never invent a
    specialty for a bare "запишите" with nothing to go on (KB routing rule)."""
    sid = find_specialty_id(profile, state.specialty)
    if sid:
        return sid
    sid = _first_bookable_specialty(profile, message)
    if sid:
        return sid
    if state.symptoms_or_goal:
        routed = detect_symptom_specialty(state.symptoms_or_goal)
        return _first_bookable_specialty(profile, routed or "") or _gp_specialty(profile, state)
    return None


def find_doctor_in_message(
    profile: ClinicProfile, message: str, *, specialty_id: str | None = None
) -> Doctor | None:
    """A doctor named in the message ("к Панченко"), by surname prefix. Restricted
    to ``specialty_id`` when given."""
    low = (message or "").casefold()
    pool = (
        profile.doctors_for_specialty(specialty_id) if specialty_id else profile.doctors
    )
    for doctor in pool:
        for part in doctor.name.split():
            stem = part.casefold()[: max(4, len(part) - 2)]
            if stem and stem in low:
                return doctor
    return None


def match_offered_slot(slots: list[Slot], message: str, today: date) -> Slot | None:
    """Which offered slot the visitor picked: by ordinal, exact HH:MM (optionally
    with a day word), or a lone affirmation when a single slot was offered."""
    if not slots:
        return None
    low = (message or "").casefold()

    for pattern, index in _ORDINALS:
        if pattern.search(low) and index < len(slots):
            return slots[index]

    day_in_msg = next((d for d in _DAY_WORDS if d in low), None)
    explicit = {f"{int(h):02d}:{m}" for h, m in _TIME_RE.findall(low)}
    bare_hours: set[int] = set()
    if not explicit:
        bare_hours = {int(h) for h in _BARE_HOUR_RE.findall(_TIME_RE.sub(" ", low))}

    candidates = []
    for slot in slots:
        slot_time = slot.start.strftime("%H:%M")
        slot_day = slot.relative_label(today).rsplit(" ", 1)[0]
        if day_in_msg is not None and day_in_msg != slot_day:
            continue
        if explicit:
            if slot_time in explicit:
                candidates.append(slot)
        elif slot.start.minute == 0 and slot.start.hour in bare_hours:
            candidates.append(slot)
    if len(candidates) == 1:
        return candidates[0]

    if is_affirmation(message) and len(slots) == 1:
        return slots[0]
    return None


def _recover_doctor_from_history(
    profile: ClinicProfile, history: list[ChatHistoryMessage]
) -> Doctor | None:
    """The doctor the assistant last named in the transcript (its offers always
    name the doctor), so a booking started "к Панченко" survives later turns."""
    for msg in reversed(list(history or [])):
        if msg.role != "assistant":
            continue
        found = find_doctor_in_message(profile, msg.content or "")
        if found is not None:
            return found
    return None


def _recover_pending_label(history: list[ChatHistoryMessage]) -> str | None:
    """The slot label the assistant last locked/confirmed, from the transcript."""
    pending: str | None = None
    for msg in history or []:
        if msg.role != "assistant":
            continue
        match = _PENDING_LABEL_RE.search(msg.content or "")
        if match:
            pending = f"{match.group(1).lower()} {match.group(2)}"
    return pending


def _list_windows(slots: list[Slot], today: date, limit: int = 3) -> str:
    labels = slots_to_labels(slots[:limit], today)
    if len(labels) == 1:
        return labels[0]
    return f"{', '.join(labels[:-1])} или {labels[-1]}"


def _ask_missing_fields(state: ConversationState) -> str:
    need: list[str] = []
    if not (state.patient_name or state.contact_name):
        need.append("ФИО")
    if not state.is_known("age"):
        need.append("возраст")
    if not state.contact:
        need.append("WhatsApp/телефон")
    if len(need) > 1:
        return ", ".join(need[:-1]) + " и " + need[-1]
    return need[0] if need else ""


def resolve(
    *,
    provider: BookingProvider,
    instance_id: str,
    state: ConversationState,
    message: str,
    history: list[ChatHistoryMessage],
    now: datetime,
) -> BookingTurn | None:
    """Drive one booking turn through the provider. Returns None to defer to the
    rest of the pipeline (e.g. specialty not known yet)."""
    if state.urgency_flag == "emergency":
        return None
    profile = provider._profile()  # type: ignore[attr-defined]
    today = now.astimezone(_tz(profile)).date()

    specialty_id = find_specialty_id(profile, state.specialty)
    doctor = find_doctor_in_message(profile, message, specialty_id=specialty_id)
    # Stateless server: a doctor named only on an earlier turn is recovered from
    # the transcript so a mid-booking "10:00" reply still targets the right one.
    if doctor is None and specialty_id is None:
        doctor = _recover_doctor_from_history(profile, history)
    if doctor is not None:
        specialty_id = doctor.specialty_id
    # No committed specialty yet: derive a single BOOKABLE one from the message
    # or the known complaint (an ambiguous route like "гастроэнтеролог или
    # терапевт" resolves to the bookable терапевт; a non-bookable route falls
    # back to the GP). This is what lets "запиши" close fast instead of the
    # writer dawdling with no specialty locked.
    if specialty_id is None and doctor is None:
        specialty_id = _booking_specialty(profile, state, message)
    if specialty_id is None and doctor is None:
        return None  # nothing to book on (no specialty, no complaint) — let the LLM ask

    try:
        if doctor is not None:
            slots = provider.get_slots(
                instance_id, date_from=today, date_to=_plus(today, 14), doctor_id=doctor.id
            )
        else:
            slots = provider.get_slots(
                instance_id, date_from=today, date_to=_plus(today, 14), specialty_id=specialty_id
            )
    except StoreUnavailableError:
        return None  # degrade to the legacy/LLM path

    # ---- which slot: from this message, else a slot locked on an earlier turn ----
    # The legacy state.selected_slot is ignored on purpose: it is resolved against
    # the fictional demo slots, not the provider's real ones.
    chosen_slot = match_offered_slot(slots, message, today)
    if chosen_slot is None:
        pending = _recover_pending_label(history)
        if pending:
            chosen_slot = next(
                (s for s in slots if s.relative_label(today) == pending), None
            )
    if chosen_slot is None:
        return _offer(provider, instance_id, profile, specialty_id, doctor, slots, today)
    state.selected_slot = chosen_slot.relative_label(today)

    # ---- collect name + contact, then confirm ----
    # Strip the slot's day/time tokens first so "09:00" is never mis-read as an
    # age and "сегодня" never as a name.
    seed_text = _TIME_RE.sub(" ", message)
    for day_word in _DAY_WORDS:
        seed_text = re.sub(day_word, " ", seed_text, flags=re.IGNORECASE)
    apply_booking_field_seed(state, seed_text)
    name = state.patient_name or state.contact_name
    dative = specialty_dative(profile.specialty_by_id(chosen_slot.specialty_id).name)

    if not (name and state.contact):
        missing = _ask_missing_fields(state)
        return BookingTurn(
            answer=(
                f"Отлично, выбрали {chosen_slot.relative_label(today)} "
                f"к {chosen_slot.doctor_name}.\n\n"
                f"Для записи пришлите, пожалуйста: {missing}."
            ),
            conversation_status="awaiting_contact",
            offered_labels=[chosen_slot.relative_label(today)],
        )

    # Everything present — persist a confirmed booking.
    try:
        appt = provider.book_slot(
            instance_id, doctor_id=chosen_slot.doctor_id, start=chosen_slot.start,
            patient_name=name, contact=state.contact,
        )
    except SlotTakenError:
        state.selected_slot = ""
        fresh = provider.get_slots(
            instance_id, date_from=today, date_to=_plus(today, 14),
            specialty_id=chosen_slot.specialty_id,
        )
        return _offer(provider, instance_id, profile, chosen_slot.specialty_id, None, fresh, today,
                      prefix="Это время только что заняли. ")
    except StoreUnavailableError:
        return None

    return BookingTurn(
        answer=(
            f"Готово, {name}! Записали вас на {chosen_slot.relative_label(today)} "
            f"к {chosen_slot.doctor_name} ({dative}). "
            "Администратор свяжется с вами для подтверждения деталей."
        ),
        conversation_status="booking_created",
        offered_labels=[chosen_slot.relative_label(today)],
        appointment=appt,
        lead=appt.to_lead_dict(),
    )


def _offer(
    provider: BookingProvider,
    instance_id: str,
    profile: ClinicProfile,
    specialty_id: str | None,
    doctor: Doctor | None,
    slots: list[Slot],
    today: date,
    *,
    prefix: str = "",
) -> BookingTurn:
    if not slots:
        return BookingTurn(
            answer=(
                f"{prefix}Ближайших свободных окон пока не вижу. "
                "Уточню у администратора и вернусь с вариантами."
            ),
            conversation_status="slots_offered",
            offered_labels=[],
        )

    if doctor is not None:
        dative = specialty_dative(profile.specialty_by_id(doctor.specialty_id).name)
        windows = _list_windows(slots, today)
        return BookingTurn(
            answer=(
                f"{prefix}К {doctor.name} ({dative}) ближайшие окна: {windows}.\n\n"
                "Какое время вам удобно?"
            ),
            conversation_status="slots_offered",
            offered_labels=slots_to_labels(slots, today),
        )

    # Specialty: show each doctor's soonest window (usually one doctor per
    # specialty in the demo KB; supports several).
    suggestions = provider.suggest_doctors(instance_id, specialty_id, limit_per_doctor=3)
    if not suggestions:
        return _offer(provider, instance_id, profile, specialty_id, None, [], today, prefix=prefix)

    specialty_name = profile.specialty_by_id(specialty_id).name
    dative = specialty_dative(specialty_name)
    if len(suggestions) == 1:
        _, doc_name, windows = suggestions[0]
        listed = _list_windows(windows, today)
        answer = (
            f"{prefix}К {dative} принимает {doc_name}. Ближайшие окна: {listed}.\n\n"
            "Какое время вам удобно?"
        )
    else:
        lines = [
            f"{doc_name}: {_list_windows(windows, today, limit=2)}"
            for _, doc_name, windows in suggestions[:3]
        ]
        answer = (
            f"{prefix}К {dative} могут принять несколько врачей:\n"
            + "\n".join(lines)
            + "\n\nК кому и на какое время вас записать?"
        )
    return BookingTurn(
        answer=answer,
        conversation_status="slots_offered",
        offered_labels=slots_to_labels(slots, today),
    )


def _tz(profile: ClinicProfile):
    from zoneinfo import ZoneInfo

    return ZoneInfo(profile.timezone)


def _plus(day: date, days: int) -> date:
    from datetime import timedelta

    return day + timedelta(days=days)
