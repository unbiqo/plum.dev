-- Demo booking store for the vertical demos (medical center, etc.).
-- Idempotent: safe to run repeatedly. Rollback block at the bottom (manual).
--
-- Holds a real, dated appointment the demo visitor books through the bot. The
-- slot engine (app/slot_engine.py) treats confirmed rows and un-expired holds
-- as busy. NOT a production table — demo data only; wiped by /demo/reset_appointments.

create extension if not exists pgcrypto;

create table if not exists public.demo_appointments (
    id uuid primary key default gen_random_uuid(),
    instance_id text not null,
    specialty_id text not null,
    doctor_id text not null,
    doctor_name text,
    start_ts timestamptz not null,
    status text not null default 'hold' check (status in ('hold', 'confirmed', 'cancelled')),
    patient_name text,
    contact text,
    hold_expires_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Race protection: at most one ACTIVE (hold/confirmed) appointment per doctor +
-- start instant, per instance. A cancelled row never blocks rebooking. An
-- expired hold must be swept to 'cancelled' (done by the provider before a new
-- hold) so it does not falsely block this index.
create unique index if not exists demo_appointments_active_slot_unique
    on public.demo_appointments (instance_id, doctor_id, start_ts)
    where status in ('hold', 'confirmed');

-- Range/scan index for the busy-slot lookup per instance and time window.
create index if not exists demo_appointments_instance_start_idx
    on public.demo_appointments (instance_id, start_ts);

-- ---------------------------------------------------------------------------
-- ROLLBACK (manual — NOT applied by tooling). Run in the Supabase SQL editor
-- only to fully remove the demo booking store:
--
--   drop index if exists public.demo_appointments_instance_start_idx;
--   drop index if exists public.demo_appointments_active_slot_unique;
--   drop table if exists public.demo_appointments;
-- ---------------------------------------------------------------------------
