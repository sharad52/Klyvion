#!/usr/bin/env bash
# One-time GitHub repository setup for Klyvion.
# Labels, branches, protection, discussions, and security features live on
# GitHub's side (not in files), so this script configures them via `gh` CLI.
#
# Prereqs: gh CLI installed and authenticated (gh auth login), repo pushed.
# Usage:   REPO=sharad52/klyvion bash scripts/setup_github.sh
set -euo pipefail
REPO="${REPO:-sharad52/klyvion}"
# Solo-maintainer note: GitHub won't let you approve your own PRs, so the
# spec's "2 approvals" would block all merges on a one-person project.
# Start with 0 and raise via APPROVALS=2 once co-maintainers join.
APPROVALS="${APPROVALS:-0}"

echo "== Labels =="
create_label(){ gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force; }
create_label "bug"              "d73a4a" "Something isn't working"
create_label "documentation"    "0075ca" "Improvements or additions to docs"
create_label "enhancement"      "a2eeef" "New feature or request"
create_label "good first issue" "7057ff" "Good for newcomers"
create_label "help wanted"      "008672" "Extra attention is needed"
create_label "question"         "d876e3" "Further information is requested"
create_label "performance"      "fbca04" "Speed, memory, or latency"
create_label "security"         "b60205" "Security-related"
create_label "api"              "1d76db" "HTTP API / server"
create_label "voice"            "c2e0c6" "Voice presets and cloning"
create_label "tts"              "5319e7" "Synthesis engines and quality"
create_label "good documentation" "0e8a16" "Exemplary docs worth imitating"
create_label "breaking change"  "e11d21" "Requires a major version bump"
create_label "dependencies"     "0366d6" "Dependency updates"
create_label "ci"               "ededed" "Continuous integration"

echo "== Branches =="
DEFAULT_SHA=$(gh api "repos/$REPO/git/ref/heads/main" -q .object.sha)
for BR in develop release; do
  gh api "repos/$REPO/git/refs" -f ref="refs/heads/$BR" -f sha="$DEFAULT_SHA" 2>/dev/null \
    && echo "created $BR" || echo "$BR exists"
done

echo "== Branch protection: main =="
gh api -X PUT "repos/$REPO/branches/main/protection" \
  --input - << JSON
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["Lint", "Tests (3.10)", "Tests (3.11)", "Tests (3.12)", "Build", "Type Check", "Security Scan"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": $APPROVALS,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

echo "== Branch protection: develop (lighter) =="
gh api -X PUT "repos/$REPO/branches/develop/protection" \
  --input - << JSON
{
  "required_status_checks": { "strict": false, "contexts": ["Lint", "Tests (3.12)"] },
  "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": $APPROVALS },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

echo "== Merge strategy: squash + rebase only =="
gh api -X PATCH "repos/$REPO" \
  -F allow_squash_merge=true -F allow_rebase_merge=true -F allow_merge_commit=false \
  -F delete_branch_on_merge=true \
  -F has_discussions=true -F has_wiki=false -F has_projects=true

echo "== Security features =="
gh api -X PUT "repos/$REPO/vulnerability-alerts" || true
gh api -X PUT "repos/$REPO/automated-security-fixes" || true
gh api -X PATCH "repos/$REPO" --input - << 'JSON' || true
{ "security_and_analysis": {
    "secret_scanning": { "status": "enabled" },
    "secret_scanning_push_protection": { "status": "enabled" } } }
JSON

echo "== Milestones =="
for M in "v0.2 — Streaming API & language pack 1" "v0.5 — Multi-engine routing (Piper) & per-session voices" "v1.0 — Stable API, benchmarks, PyPI release"; do
  gh api "repos/$REPO/milestones" -f title="$M" 2>/dev/null || true
done

echo
echo "Done. Manual steps remaining (no API): upload assets/social-preview.png"
echo "under Settings → General → Social preview, and create Discussions"
echo "categories (Announcements, Ideas, Q&A, Show and Tell, General)."
