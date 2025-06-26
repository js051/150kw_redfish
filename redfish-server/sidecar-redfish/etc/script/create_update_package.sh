#!/usr/bin/env bash

###############################################################################
# redfish-server/sidecar-redfish/etc/script/create_update_package.sh
#
# 功能描述:
#   本腳本用於為一個包含多個服務的整合專案 (Monorepo)，建立一個差異化的
#   離線更新包。它會比對兩個指定的 Git 版本 (TAG 或 Commit HASH)，並只打包
#   在這兩個版本之間有變動的應用程式碼，以及有差異的 Python 依賴套件。
#
#   最終產出的 .tar.gz 壓縮檔將包含一個自動化的更新腳本 (update.sh)，
#   此腳本可在沒有離線環境中，安全、可靠的執行升級。
#
# 先決條件:
#   - 在LINUX或VM或WSL環境中執行
#   - 執行腳本的環境需已安裝 Git, Python (包含 pip 與 venv), 以及 rsync。
#   - 所有需要比對的 Git TAG 必須已存在於本地 (可執行 'git fetch --tags' 來獲取)。
#
# 使用方法:
#   ./create_update_package.sh <OLD_TAG> <NEW_TAG>
#
# 參數說明:
#   <舊版號>: 起始版本的 Git TAG 或 Commit HASH。
#   <新版號>: 要更新到的目標版本的 Git TAG 或 Commit HASH。
#
# 使用範例:
#   ./create_update_package.sh v0.1.0 v0.2.0
#
#   chmod +x ./redfish-server/sidecar-redfish/etc/script/create_update_package.sh
#   ./redfish-server/sidecar-redfish/etc/script/create_update_package.sh v0.1.0 v0.2.0
# ----------------------------------------------------------------------------
#
# 更新壓縮包本地驗證流程 (Dry Run):
#   模擬測試，以確保其內容與邏輯的正確性，建議步驟如下(在根目錄下逐一執行)：
#
#   1. 預覽包內容 (確認檔案結構):
#      tar -tvf ITG_Update_*.tar.gz
#
#   2. 建立臨時測試環境:
#      mkdir -p test_update/update_package
#      tar -xzf ITG_Update_*.tar.gz -C test_update/update_package
#      cd test_update/update_package
#
#   3. 模擬更新 (最關鍵的一步):
#      a. 建立一個模擬的生產路徑 (因為我們的專案有多個服務，
#         所以我們模擬到根目錄即可):
#         mkdir -p ../mock_prod_env/
#
#      b. 暫時修改 update.sh，將 TARGET_DIR 改為模擬路徑。
#         (可手動編輯，或使用以下 sed 指令自動替換)
#         sed -i.bak 's|TARGET_DIR="/home/user/service"|TARGET_DIR="../mock_prod_env"|' update.sh
#
#      c. 暫時註解掉 update.sh 中需要 root 權限的指令 (如果權限不足)。
#         例如：開頭的 systemctl 和結尾的 chown。
#
#      d. 執行模擬更新:
#         chmod +x update.sh
#         ./update.sh
#
#   4. 檢查結果:
#      ls -lR ../mock_prod_env/
#      # 確認 app/ 中的所有檔案是否已正確複製進來。
#
#   5. 清理測試環境:
#      cd ../..
#      rm -rf test_update
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
# --diff-filter=ACMRT excludes deleted files to prevent errors with git archive
CHANGED_FILES=$(git diff --name-only --diff-filter=ACMRT "$OLD_TAG" "$NEW_TAG")

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
REQUIREMENT_FILES=$( (git ls-tree -r --name-only "$OLD_TAG" 2>/dev/null || true; git ls-tree -r --name-only "$NEW_TAG") | grep 'requirements.txt$' | sort -u)

if [ -z "$REQUIREMENT_FILES" ]; then
    echo "No requirements.txt files found in the project."
else
    # Download all dependencies for the OLD_TAG
    echo "Downloading dependencies for OLD_TAG ($OLD_TAG)..."
    while IFS= read -r req_file; do
        if git cat-file -e "$OLD_TAG:$req_file" >/dev/null 2>&1; then
            echo "  - Processing $req_file from old tag"
            # python3 -m pip
            git show "$OLD_TAG:$req_file" | python3 -m pip download --quiet -r /dev/stdin -d old_wheels --platform manylinux2014_x86_64 --python-version 3.10 --only-binary=:all: >/dev/null
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
            # python3 -m pip
            python3 -m pip download --quiet -r "$UPDATE_DIR/app/$req_file" -d new_wheels --platform manylinux2014_x86_64 --python-version 3.10 --only-binary=:all: >/dev/null
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
