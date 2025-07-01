import platform
import subprocess
import psutil
import subprocess, threading, time, datetime
#====================================================
# set NTP
# ===================================================
def set_ntp(enable: bool, ntp_server: str):
    """
    跨平台啓用或停用本機 NTP 同步。
    :param enable: True=啓用, False=停用
    [*] 目前僅支援 ntp.ubuntu.com
    """
    os_name = platform.system()
    if os_name == "Windows":
        print("正在處理 Windows 系統的 NTP 設定...")
        svc = psutil.win_service_get("W32Time")
        if enable:
            subprocess.run(["sc", "config", "W32Time", "start=", "auto"], check=True)
            subprocess.run(["sc", "start",  "W32Time"],               check=True)

            print("已啟用 Windows Time 服務並設為自動啟動")
        else:
            subprocess.run(["sc", "stop",   "W32Time"],               check=True)
            subprocess.run(["sc", "config", "W32Time", "start=", "disabled"], check=True)
            print("已停止並設為停用的 W32Time 服務")

    elif os_name == "Linux":
        print("正在處理 Linux 系統的 NTP 設定...")
        mode = "true" if enable else "false"
        # 使用 timedatectl 控制 systemd-timesyncd
        subprocess.run(["/usr/bin/sudo", "timedatectl", "set-ntp", mode], check=True)
        # 設定 NTP 伺服器
        if ntp_server:
            subprocess.run(["/usr/bin/sudo", "ntpdate", ntp_server], capture_output=True, text=True)
        subprocess.run(["/usr/bin/sudo", "hwclock", "--systohc"], check=True)
        print(f"timedatectl set-ntp {mode} 執行完成")
        # subprocess.run(["timedatectl", "status"], check=True)
         
    else:
        raise RuntimeError(f"不支援的作業系統：{os_name}")
    

#====================================================
# network switch
# ===================================================
def monitor_up(iface, evt: threading.Event):
    # 啟動一個非同步的監聽子程序
    p = subprocess.Popen(
        ["/usr/bin/sudo", "ip", "-j", "monitor", "link", "dev", iface],
        stdout=subprocess.PIPE,
        text=True
    )
    # 讀它的 stdout
    for line in p.stdout:
        if "state UP" in line or "state DOWN" in line:
            p.terminate()   # 偵測到 UP 就結束監聽
            evt.set()
            break
        
def set_NetwrokInterface(iface: str, state: bool) -> None:
    """
    指定的網路介面
    """
    evt = threading.Event()
    if state:
        state = "up"
        # 執行 therading 監聽網路介面狀態變化
        t = threading.Thread(target=monitor_up, args=(iface, evt), daemon=True)
        t.start()
    else:
        state = "down"
    
    try:
        subprocess.run(
            ["/usr/bin/sudo", "ip", "link", "set", "dev", iface, state],
            check=True
        )
        
        if state is "up":
            got = evt.wait(10)  
            if not got:
                raise TimeoutError(f"{iface} is not UP or cannot be UP")
    except subprocess.CalledProcessError as e:
        print(f"介面 {iface} 設定失敗：{e}")
 

