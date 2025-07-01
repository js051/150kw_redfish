#!/usr/bin/env bash

###############################################################################
# Script Name: create_update_package.sh
#
# 功能描述:
#   為一個多模組的 Monorepo 專案建立一個精簡的、差異化的離線更新包。
#   - 只打包在兩個 Git 版本之間有變動的應用程式碼。
#   - 只打包新增或版本變更的 Python 依賴 (.whl 檔案)。
#   - 每個模組的依賴會被分開存放在各自的 wheelhouse 目錄中。
#   - 不生成任何執行腳本，只負責打包。
#
# 使用範例:
#   ./create_update_package.sh v0.1.0 v0.2.0
#   ./redfish-server/sidecar-redfish/etc/script/create_update_package.sh v0.1.0 v0.2.0
#
# 備註:
#   - 執行前會驗證 TAG 是否存在，並在任一步驟失敗時終止。
###############################################################################

set -e # Exit immediately if a command exits with a non-zero status.

# --- Main execution flow ---
main() {
    validate_input "$1" "$2"
    prepare_workspace
    package_changed_files
    package_python_dependencies_by_module
    archive_package
    cleanup

    echo "---------------------------------"
    echo "Incremental update package created successfully!"
    echo "File: ${ARCHIVE_NAME}"
    echo "---------------------------------"
}

# --- Function definitions ---

# Validate input and set global variables
validate_input() {
    if [ -z "$1" ] || [ -z "$2" ]; then
        echo "Error: missing OLD_TAG or NEW_TAG."
        echo "Usage: $0 <OLD_TAG> <NEW_TAG>"
        exit 1
    fi

    if ! git cat-file -e "$1" >/dev/null 2>&1; then
        echo "Error: OLD_TAG not found: $1"
        exit 1
    fi
    if ! git cat-file -e "$2" >/dev/null 2>&1; then
        echo "Error: NEW_TAG not found: $2"
        exit 1
    fi

    OLD_TAG=$1
    NEW_TAG=$2
    UPDATE_DIR="update_package"
    ARCHIVE_NAME="ITG_Update_${OLD_TAG}_to_${NEW_TAG}.tar.gz"

    echo "Creating incremental update package from ${OLD_TAG} to ${NEW_TAG}..."
}

# Prepare a clean workspace
prepare_workspace() {
    echo "Preparing workspace..."
    rm -rf "$UPDATE_DIR"
    mkdir -p "$UPDATE_DIR/app" "$UPDATE_DIR/wheels"
    echo "Workspace ready."
}

# Locate and package source files that changed between the two tags
package_changed_files() {
    echo "Finding changed application files..."
    local changed_files
    changed_files=$(git diff --name-only --diff-filter=ACMRT "$OLD_TAG" "$NEW_TAG")

    if [ -z "$changed_files" ]; then
        echo "No application files changed."
    else
        echo "$changed_files" | rsync -a --files-from=- . "$UPDATE_DIR/app/"
        echo "Application files packaged."
    fi
}

# For each module, package only the new or updated Python wheels
package_python_dependencies_by_module() {
    echo "Searching for differing Python dependencies by module..."

    local requirement_files
    requirement_files=$(git ls-tree -r --name-only "$NEW_TAG" | grep 'requirements.txt$' | sort -u)

    if [ -z "$requirement_files" ]; then
        echo "No requirements.txt found in project. Skipping dependency packaging."
        return
    fi

    # Iterate over every requirements.txt file
    while IFS= read -r req_file; do
        local service_dir
        service_dir=$(dirname "$req_file")

        echo ">> Processing module: ${service_dir}"

        # Create isolated temp wheel directories for comparison
        local old_wheels="temp_old_${service_dir//\//_}"
        local new_wheels="temp_new_${service_dir//\//_}"
        rm -rf "$old_wheels" "$new_wheels"
        mkdir -p "$old_wheels" "$new_wheels"

        # Download wheels for the old commit; if file absent, treat as empty
        if git cat-file -e "$OLD_TAG:$req_file" >/dev/null 2>&1; then
            git show "$OLD_TAG:$req_file" |
                python3 -m pip download --quiet -r /dev/stdin -d "$old_wheels" \
                    --platform manylinux2014_x86_64 --python-version 3.10 --only-binary=:all: >/dev/null
        fi

        # Download wheels for the new commit (always present)
        git show "$NEW_TAG:$req_file" |
            python3 -m pip download --quiet -r /dev/stdin -d "$new_wheels" \
                --platform manylinux2014_x86_64 --python-version 3.10 --only-binary=:all: >/dev/null

        # Copy wheels that exist only in the new version to the update package
        diff -rq "$old_wheels" "$new_wheels" | grep "Only in $new_wheels" | awk '{print $4}' | while read f; do
            mkdir -p "$UPDATE_DIR/wheels/$service_dir"
            cp "$new_wheels/$f" "$UPDATE_DIR/wheels/$service_dir/"
        done

        # Remove temporary directories
        rm -rf "$old_wheels" "$new_wheels"
    done <<<"$requirement_files"

    # Remove wheels directory if no changes were detected
    if [ -d "$UPDATE_DIR/wheels" ] && [ -z "$(ls -A "$UPDATE_DIR/wheels")" ]; then
        echo "No dependency changes across all modules."
        rm -rf "$UPDATE_DIR/wheels"
    fi
}

# Compress the assembled package into a tarball
archive_package() {
    echo "Compressing update package..."
    (cd "$UPDATE_DIR" && tar -czf "../${ARCHIVE_NAME}" .)
    echo "Compression complete."
}

# Delete temporary workspace
cleanup() {
    echo "Cleaning up temporary files..."
    rm -rf "$UPDATE_DIR"
    echo "Cleanup complete."
}

# --- Script entry point ---
main "$@"
