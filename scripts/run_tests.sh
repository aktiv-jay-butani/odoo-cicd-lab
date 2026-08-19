#!/usr/bin/env bash
# Runs a fresh install of all custom modules with tests enabled, on a
# throwaway database, and fails if the log contains any error/traceback
# or test failure — mirroring what odoo.sh's build step checks for.
set -uo pipefail

IMAGE="${1:?Usage: run_tests.sh <image> <db_host> <db_user> <db_password>}"
DB_HOST="${2:?missing db host}"
DB_USER="${3:?missing db user}"
DB_PASSWORD="${4:?missing db password}"

TEST_DB="ci_test_$(date +%s)"
LOG_FILE="/tmp/odoo_test_${TEST_DB}.log"

# Auto-detect every custom module folder under ./addons
MODULES=$(ls addons | paste -sd, -)
if [ -z "$MODULES" ]; then
  echo "No modules found under ./addons — nothing to test."
  exit 0
fi
echo "Modules to install & test: $MODULES"

# Build "/mod1,/mod2,/mod3" so --test-tags runs tests scoped to just these modules
TEST_TAGS=$(echo "$MODULES" | tr ',' '\n' | sed 's#^#/#' | paste -sd, -)

docker run --rm \
  --network host \
  -e HOST="$DB_HOST" \
  -e USER="$DB_USER" \
  -e PASSWORD="$DB_PASSWORD" \
  "$IMAGE" \
  odoo -d "$TEST_DB" \
    --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons \
    -i "$MODULES" \
    --test-enable \
    --test-tags="$TEST_TAGS" \
    --stop-after-init \
    --log-level=test \
    --without-demo=False \
  2>&1 | tee "$LOG_FILE"

RUN_EXIT=${PIPESTATUS[0]}

echo "---- scanning log for failures ----"
if grep -E -i "CRITICAL |ERROR |FAILED |Traceback \(most recent call last\)" "$LOG_FILE"; then
  echo "❌ Errors/tracebacks found in install/test log — failing build."
  exit 1
fi

if [ "$RUN_EXIT" -ne 0 ]; then
  echo "❌ odoo-bin exited non-zero ($RUN_EXIT) — failing build."
  exit 1
fi

echo "✅ Install + tests completed with no errors."
