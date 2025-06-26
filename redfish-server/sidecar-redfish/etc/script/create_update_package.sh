#!/usr/bin/env bash

###############################################################################
#
# Script Name: create_update_package.sh (v2)
#
# Description:
#   This script creates a differential offline update package for a multi-service
#   monorepo project. It compares two specified Git versions (tags or commits)
#   and packages only the application code that has changed between them, along
#   with any differing Python dependencies for each service.
#   The resulting .tar.gz archive contains an automated update script (update.sh)
#   designed to be executed in a production environment without internet access.
#
# Prerequisites:
#   - Must be executed from the root directory of the Git repository.
#   - Requires Git, Python (with pip and venv), and rsync to be installed.
#   - The target Git tags must exist locally (use 'git fetch --tags' to retrieve them).
#
# Usage:
#   ./create_update_package.sh <OLD_VERSION> <NEW_VERSION>
#
# Example:
#   ./create_update_package.sh v0.2.0 v0.3.0
#
# ----------------------------------------------------------------------------
#
# Verification (Dry Run):
#   (Your excellent verification steps remain valid here)
#
###############################################################################

# --- Script Configuration ---
set -e # Exit immediately if any command fails

OLD_TAG=$1
NEW_TAG=$2

# The root directory for deployment on the production server
PROD_APP_PATH="/home/user/service"
UPDATE_DIR="update_package"
ARCHIVE_NAME="ITG_Update_${OLD_TAG}_to_${NEW_TAG}.tar.gz"

# --- Argument and Tag Validation ---
if [ -z "$OLD_TAG" ] || [ -z "$NEW_TAG" ]; then
    echo "Error: OLD_TAG or NEW_TAG not provided."
    echo "Usage: $0 <OLD_TAG> <NEW_TAG>"
    exit 1
fi

# Check if tags exist to fail early
if ! git cat-file -e "$OLD_TAG" >/dev/null 2>&1; then
    echo "Error: OLD_TAG not found: $OLD_TAG"
    exit 1
fi
if ! git cat-file -e "$NEW_TAG" >/dev/null 2>&1; then
    echo "Error: NEW_TAG not found: $NEW_TAG"
    exit 1
fi

echo "Creating incremental update package from ${OLD_TAG} to ${NEW_TAG}..."

# --- Workspace Preparation ---
rm -rf "$UPDATE_DIR" old_wheels new_wheels
mkdir -p "$UPDATE_DIR/app" "$UPDATE_DIR/wheels"
echo "Workspace cleaned and prepared."

# --- 1. Find and copy changed application files ---
echo "Finding changed application files..."
# --diff-filter=d excludes deleted files to prevent errors with git archive
CHANGED_FILES=$(git diff --name-only --diff-filter=d "$OLD_TAG" "$NEW_TAG")

if [ -z "$CHANGED_FILES" ]; then
    echo "No changed application files found."
else
    # Use rsync to robustly preserve directory structure and handle all file types.
    # git archive is also great but rsync is very clear and powerful.
    echo "$CHANGED_FILES" | rsync -a --files-from=- . "$UPDATE_DIR/app/"
    echo "Application files have been packaged."
fi

# --- 2. Find and package differing Python dependencies for all services ---
echo "Finding differing Python dependencies across all services..."

# Dynamically find all unique requirements.txt files from both old and new tags
# This handles cases where requirements files might be added or removed.
REQUIREMENT_FILES=$( (
    git ls-tree -r --name-only "$OLD_TAG" | grep 'requirements.txt$'
    git ls-tree -r --name-only "$NEW_TAG" | grep 'requirements.txt$'
) | sort -u)

if [ -z "$REQUIREMENT_FILES" ]; then
    echo "No requirements.txt files found in the project."
else
    # Download all dependencies for the OLD_TAG
    echo "Downloading dependencies for OLD_TAG ($OLD_TAG)..."
    while IFS= read -r req_file; do
        if git cat-file -e "$OLD_TAG:$req_file" >/dev/null 2>&1; then
            echo "  - Processing $req_file from old tag"
            git show "$OLD_TAG:$req_file" | pip download --quiet -r /dev/stdin -d old_wheels --platform manylinux2014_x86_64 --python-version 3.10 --only-binary=:all: >/dev/null
        fi
    done <<<"$REQUIREMENT_FILES"

    # Download all dependencies for the NEW_TAG
    echo "Downloading dependencies for NEW_TAG ($NEW_TAG)..."
    while IFS= read -r req_file; do
        if git cat-file -e "$NEW_TAG:$req_file" >/dev/null 2>&1; then
            echo "  - Processing $req_file from new tag"
            # Also copy the new requirements file into the update package for use by update.sh
            # Ensure the directory exists before copying
            mkdir -p "$UPDATE_DIR/app/$(dirname "$req_file")"
            git show "$NEW_TAG:$req_file" >"$UPDATE_DIR/app/$req_file"
            pip download --quiet -r "$UPDATE_DIR/app/$req_file" -d new_wheels --platform manylinux2014_x86_64 --python-version 3.10 --only-binary=:all: >/dev/null
        fi
    done <<<"$REQUIREMENT_FILES"

    # Compare and copy only new or updated .whl files
    echo "Comparing wheel file versions..."
    WHEEL_COUNT=$(diff -rq old_wheels new_wheels | grep "Only in new_wheels" | awk '{print $4}' | xargs -I {} cp "new_wheels/{}" "$UPDATE_DIR/wheels/" | wc -l)
    echo "Packaged ${WHEEL_COUNT} new or updated dependency wheels."
fi

# --- 3. Create the update execution script ---
echo "Creating update script (update.sh)..."

# Dynamically generate the list of services for update.sh
SERVICE_VENV_CONFIG=""
for service_dir in $(echo "$REQUIREMENT_FILES" | sed 's|/requirements.txt||' | sort -u); do
    # Simple logic to guess venv name. Customize if needed.
    venv_name="venv"
    [[ "$service_dir" == "PLC" ]] && venv_name="plcenv"
    [[ "$service_dir" == "RestAPI" ]] && venv_name="apienv"
    [[ "$service_dir" == "snmp" ]] && venv_name="snmpvenv"
    [[ "$service_dir" == "webUI" ]] && venv_name="webvenv"
    [[ "$service_dir" == "redfish-server" ]] && venv_name="redfish_venv"

    SERVICE_VENV_CONFIG+="        [\"${service_dir}\"]=\"\${TARGET_DIR}/${service_dir}/${venv_name}\"\n"
done

# Use a Here Document to create update.sh
cat <<EOF >"$UPDATE_DIR/update.sh"
#!/bin/bash
set -e

echo "================================="
echo "Starting System Update"
echo "================================="

TARGET_DIR="${PROD_APP_PATH}"

# It is recommended to stop all related services before updating.
# Customize the service names and uncomment the line below.
echo "Stopping services..."
sudo systemctl stop plc.service modbusProxy.service snmp.service restapi.service webui.service sidecar-redfish.service nginx.service || echo "Some services could not be stopped (may not exist), continuing..."

echo "Updating application files..."
# rsync -a preserves permissions, timestamps, etc. -v is verbose, -h is human-readable.
rsync -avh --progress ./app/ "\$TARGET_DIR/"

# Check if there are any new wheels to install
if [ -d "./wheels" ] && [ "\$(ls -A ./wheels)" ]; then
    echo "New Python packages detected, updating dependencies for each service..."
    
    # This associative array is dynamically generated by the create_update_package.sh script
    declare -A SERVICES=(
${SERVICE_VENV_CONFIG}
    )

    for service in "\${!SERVICES[@]}"; do
        VENV_PATH="\${SERVICES[\$service]}"
        REQUIREMENTS_PATH="\$TARGET_DIR/\$service/requirements.txt"

        if [ -f "\$REQUIREMENTS_PATH" ]; then
            echo ">> Updating dependencies for \$service..."
            if [ -d "\$VENV_PATH" ]; then
                # Use the python binary from the venv to ensure packages are installed in the correct environment.
                "\$VENV_PATH/bin/python3" -m pip install --upgrade --no-index --find-links=./wheels -r "\$REQUIREMENTS_PATH"
            else
                echo "   Warning: Virtual environment for \$service not found at \$VENV_PATH. Creating it."
                python3 -m venv "\$VENV_PATH"
                "\$VENV_PATH/bin/python3" -m pip install --upgrade --no-index --find-links=./wheels -r "\$REQUIREMENTS_PATH"
            fi
        fi
    done
else
    echo "No new Python packages to install."
fi

echo "Fixing file permissions..."
# Ensure the entire service directory has the correct ownership.
# Please adjust 'user:user' according to the target environment.
sudo chown -R user:user "\$TARGET_DIR"

echo "================================="
echo "Update complete!"
echo "Please run 'restart.sh' or manually restart all services to apply changes."
echo "================================="
EOF

chmod +x "$UPDATE_DIR/update.sh"
echo "Update script created and made executable."

# --- 4. Archive the package ---
echo "Archiving the update package..."
(cd "$UPDATE_DIR" && tar -czf "../${ARCHIVE_NAME}" .)
echo "Archive created: ${ARCHIVE_NAME}"

# --- 5. Cleanup ---
echo "Cleaning up temporary files..."
rm -rf old_wheels new_wheels "$UPDATE_DIR"
echo "Done."
