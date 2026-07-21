"""CLI: seed (and optionally reset) demo bookings for a showing.

    python scripts/seed_demo_appointments.py                 # seed medical demo
    python scripts/seed_demo_appointments.py --reset          # wipe first, then seed
    python scripts/seed_demo_appointments.py --instance <id>  # another instance

Uses the real Supabase-backed provider. Deterministic: every other doctor's
soonest window is booked, so the demo shows partial availability.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.booking_provider import DemoBookingProvider, SupabaseAppointmentStore  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.demo_seed import seed_demo_appointments  # noqa: E402
from app.medical_center_demo import MEDICAL_CENTER_INSTANCE_ID  # noqa: E402
from app.supabase_service import SupabaseService  # noqa: E402

load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo appointments")
    parser.add_argument("--instance", default=MEDICAL_CENTER_INSTANCE_ID)
    parser.add_argument("--reset", action="store_true", help="Wipe the instance first.")
    args = parser.parse_args()

    settings = get_settings()
    supabase = SupabaseService(settings)
    provider = DemoBookingProvider(SupabaseAppointmentStore(supabase.client))

    if args.reset:
        removed = provider.reset(args.instance)
        print(f"reset: removed {removed} appointments for {args.instance}")

    booked = seed_demo_appointments(provider, args.instance)
    print(f"seeded {booked} appointments for {args.instance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
