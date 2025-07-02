TARGET_DIR=/home/user/service/redfish-server
SERVICE_NAME=sidecar-redfish.service
VENV_PATH=$TARGET_DIR/redfish_venv
SCRIPT_PATH=$TARGET_DIR/sidecar-redfish/app.py
SYSTEMD_PATH=/etc/systemd/system/$SERVICE_NAME

# 進入目標資料夾
cd $TARGET_DIR

#安裝python3-venv
# sudo apt install python3.10-venv

# 建立 venv 環境
python3 -m venv $VENV_PATH

# 啟動 virtual environment
source $VENV_PATH/bin/activate

# 安裝 requirements.txt 中的依賴
pip install --no-index --find-links=./wheelhouse --upgrade -r requirements.txt || true


# 創建 service 檔案
cat <<EOL | sudo tee $SYSTEMD_PATH
[Unit]
Description=Redfish Mockup Service
After=network.target

[Service]
User=
Group=user
WorkingDirectory=$TARGET_DIR
Environment="PATH=$VENV_PATH/bin"
ExecStart=$VENV_PATH/bin/python3 $SCRIPT_PATH

# Restart options
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL




# 權限、重載、啟動、設定開機啟動
sudo chmod 644 $SYSTEMD_PATH
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME
sudo systemctl status $SERVICE_NAME
deactivate
