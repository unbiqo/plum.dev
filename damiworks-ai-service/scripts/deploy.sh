#!/usr/bin/env bash
# Deploy cheat sheet for the DamiWorks monorepo.
#
# This is a reference script, not meant to run end-to-end unattended —
# fill in the variables below, then run the section(s) you need by hand
# (copy/paste or `bash scripts/deploy.sh sync`, `bash scripts/deploy.sh restart`, etc).
#
# Frontend (damiworks-site, Vercel): if the GitHub repo is connected to a
# Vercel project, `git push` to main triggers an automatic production deploy —
# no separate command needed. Check https://vercel.com/dashboard to confirm
# the project is linked and watching this repo/branch.
#
# Backend (damiworks-ai-service): Vercel does not host it. It runs as a
# Docker container on your VPS and must be synced + rebuilt manually (or wire
# up a CI job later if this gets old).

set -euo pipefail

# ── Fill these in for your VPS ────────────────────────────────────────────
VPS_USER="root"
VPS_HOST="46.62.130.62"
REMOTE_DIR="/opt/damiworks/damiworks-ai-service"   # git clone of this repo's backend, tracks origin/main
LOCAL_BACKEND_DIR="damiworks-ai-service"   # relative to repo root

# ---------------------------------------------------------------------------
# git: commit + push (triggers Vercel auto-deploy for the frontend)
# ---------------------------------------------------------------------------
git_push() {
  git add -A
  git commit -m "${1:-deploy: update}"
  git push origin main
}

# ---------------------------------------------------------------------------
# backend: the VPS dir is a git clone of this repo (root, not just the
# backend subfolder) tracking origin/main — pull is the normal path.
# git_push MUST run first so origin/main actually has the new commit.
# ---------------------------------------------------------------------------
pull() {
  ssh "${VPS_USER}@${VPS_HOST}" "cd ${REMOTE_DIR} && git fetch origin && git pull --ff-only origin main"
}

# Fallback if you ever need to push loose files instead of git (excludes
# venv/cache/secrets). Not used by deploy_backend by default.
sync() {
  rsync -avz \
    --exclude ".venv" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude ".env" \
    --exclude ".git" \
    "${LOCAL_BACKEND_DIR}/" "${VPS_USER}@${VPS_HOST}:${REMOTE_DIR}/"
}

# Alternative one-shot copy (no rsync available): scp the whole folder
scp_copy() {
  scp -r "${LOCAL_BACKEND_DIR}" "${VPS_USER}@${VPS_HOST}:${REMOTE_DIR}"
}

# ---------------------------------------------------------------------------
# backend: rebuild + restart the container on the VPS
# ---------------------------------------------------------------------------
rebuild() {
  ssh "${VPS_USER}@${VPS_HOST}" "cd ${REMOTE_DIR} && docker compose up -d --build"
}

# Restart without rebuilding image (e.g. only .env changed)
restart() {
  ssh "${VPS_USER}@${VPS_HOST}" "cd ${REMOTE_DIR} && docker compose restart api"
}

# ---------------------------------------------------------------------------
# backend: verify
# ---------------------------------------------------------------------------
status() {
  ssh "${VPS_USER}@${VPS_HOST}" "cd ${REMOTE_DIR} && docker compose ps"
}

logs() {
  ssh "${VPS_USER}@${VPS_HOST}" "cd ${REMOTE_DIR} && docker compose logs -f --tail=100 api"
}

health() {
  ssh "${VPS_USER}@${VPS_HOST}" "curl -sf http://localhost:8000/health" && echo " OK"
}

# ---------------------------------------------------------------------------
# full deploy: pull -> rebuild -> health check
# Requires git_push to have run first (or any push to origin/main).
# ---------------------------------------------------------------------------
deploy_backend() {
  pull
  rebuild
  sleep 3
  health
}

# ---------------------------------------------------------------------------
# entrypoint — run a single step by name, e.g.:
#   bash scripts/deploy.sh sync
#   bash scripts/deploy.sh deploy_backend
#   bash scripts/deploy.sh git_push "fix: english school general advice"
# ---------------------------------------------------------------------------
"$@"
