#!/usr/bin/env bash
# Daily cron: profile today's load against the learned baseline; alert on breaches.
set -uo pipefail
DAY=$(date +%F)
datalens analyze --cc nightly_export -o /var/lib/datalens --version-tag "$DAY" --run-date "$DAY" \
  --compare-to rolling --fail-on fail --history-retention-days 90 \
  --notify "webhook:https://alerts.example.com/datalens" --format json > "/var/log/datalens/$DAY.json"
exit $?
