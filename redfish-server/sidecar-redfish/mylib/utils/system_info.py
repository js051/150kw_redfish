import uuid
import psutil
import subprocess
import socket
import time
import os
import struct

#====================================================
# get system uuid
#====================================================
def get_system_uuid():
    """
    Get system uuid by command: `sudo dmidecode -s system-uuid`
    @Author: Chatgpt, welson
    @Note: You can impl. this function by `pip install python-dmidecode`, only works on specific Linux. 
    """
    try:
        # FAIL: it will requuest user to type-in password in terminal
        # output = subprocess.check_output(
        #     ["sudo", "dmidecode", "-s", "system-uuid"],
        #     stderr=subprocess.DEVNULL  # 隱藏錯誤訊息
        # ).decode().strip()
        # return output
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(get_first_mac_psutil())))
    except Exception as e:
        return str(uuid.uuid3(uuid.NAMESPACE_DNS, str(get_first_mac_psutil())))

def get_first_mac_psutil() -> str:
    """
    抓取所有mac並排序，回傳第一張
    """
    macs = []
    for ifname, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == psutil.AF_LINK:
                mac = addr.address
                if mac and mac != "00:00:00:00:00:00":
                    macs.append(mac)
    result = sorted(set(macs))         
    # print(f"MACs: {result}")       
    return result[0]

#====================================================
# get network info 
# ===================================================
def get_default_gateways():
    """
    回傳 dict: { iface_name: gateway_ip, ... }
    會把 /proc/net/route 中所有 Destination=0 的 default route 全掃一遍。
    """
    gateways = {}
    with open("/proc/net/route") as f:
        for line in f.readlines()[1:]:
            iface, dest, gw, flags = line.split()[:4]
            # 0.0.0.0/0 且 flags bit1 (0x2) 代表 RTF_GATEWAY
            if dest == "00000000" and int(flags, 16) & 0x2:
                # 小端 hex 轉成 IPv4 字串
                ip = socket.inet_ntoa(struct.pack("<L", int(gw, 16)))
                gateways[iface] = ip
    return gateways

def is_dhcp_ipcmd(ifname):
    """
    判斷指定的網路介面是否是 DHCP 取得的 IP
    """
    try:
        out = subprocess.check_output(
            ["ip","addr","show",ifname], text=True
        )
        return "dynamic" in out
    except:
        return False

def get_physical_nics():
    base = "/sys/class/net"
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()

    # 1. 讀取 /etc/resolv.conf 裡的 DNS
    name_servers = []
    with open("/etc/resolv.conf") as f:
        for line in f:
            if line.startswith("nameserver"):
                name_servers.append(line.split()[1])

    # 2. 取得 default gateway
    getway_data = get_default_gateways()

    interfaces = []
    for name in os.listdir(base):
        # 只要有 /device 就是真實 NIC
        if not os.path.exists(f"{base}/{name}/device"):
            continue
        # 排除 lo、docker、bridge、veth…
        if name in ("lo",) or name.startswith(("docker", "br-", "veth", "virbr")):
            continue

        stat = stats.get(name)
        iface = {
            "Name":            name,
            "MAC":             "",
            "IPv4":            "",
            "SubnetMask":      "",
            "AddressOrigin":   "Static",
            "Gateway":         "",
            "IPv6":            [],
            "Speed_Mbps":      stat.speed if stat else 0,
            "MTU":             stat.mtu   if stat else 0,
            "FullDuplex":      bool(stat.duplex == psutil.NIC_DUPLEX_FULL) if stat else False,
            "isUp": bool(stat.isup) if stat else False,
            "NameServers":     name_servers
        }

        for addr in addrs.get(name, []):
            # IPv4
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                iface["IPv4"]       = addr.address
                iface["SubnetMask"] = addr.netmask
                # DHCP 存在就標為 DHCP
                if is_dhcp_ipcmd(name):
                    iface["AddressOrigin"] = "DHCP"
                # 如果這個介面就是 default route，就填 Gateway
                if name in getway_data:
                    iface["Gateway"] = getway_data.get(name, "")

            # IPv6
            elif addr.family == socket.AF_INET6:
                iface["IPv6"].append(addr.address.split("%")[0])

            # MAC
            elif addr.family in (psutil.AF_LINK, socket.AF_PACKET):
                iface["MAC"] = addr.address

        interfaces.append(iface)
    return interfaces    
#====================================================
# get system uptime
# ===================================================
def get_uptime():
    # psutil.boot_time() 回傳開機到目前時間
    boot_ts = psutil.boot_time()
    now_ts  = time.time()
    uptime_s = now_ts - boot_ts
    # print(f"系統啟動時間: {time.ctime(boot_ts)}")
    # print(f"目前時間: {time.ctime(now_ts)}")
    # print(f"系統運行時間 (秒): {uptime_s}")
    hours, rem = divmod(int(uptime_s), 3600)
    minutes, seconds = divmod(rem, 60)
    # print(f"Uptime: {hours}h {minutes}m {seconds}s")
    return hours, minutes, seconds

#====================================================
# get NTP status
# ===================================================
def get_ntp_status():
    ntp_status = subprocess.run(["/usr/bin/timedatectl", "show", "-p", "NTP"], text=True, capture_output=True, check=True).stdout.strip()
    ntp_status = ntp_status.split("=",1)[1]
    ntp_status = True if ntp_status == "yes" else False
    return ntp_status


#====================================================
# get system uptime
# ===================================================
def get_uptime():
    # psutil.boot_time() 回傳開機到目前時間
    boot_ts = psutil.boot_time()
    now_ts  = time.time()
    uptime_s = now_ts - boot_ts
    # print(f"系統啟動時間: {time.ctime(boot_ts)}")
    # print(f"目前時間: {time.ctime(now_ts)}")
    # print(f"系統運行時間 (秒): {uptime_s}")
    hours, rem = divmod(int(uptime_s), 3600)
    minutes, seconds = divmod(rem, 60)
    # print(f"Uptime: {hours}h {minutes}m {seconds}s")
    return hours, minutes, seconds

#====================================================
# get NTP status
# ===================================================
def get_ntp_status():
    ntp_status = subprocess.run(["/usr/bin/timedatectl", "show", "-p", "NTP"], text=True, capture_output=True, check=True).stdout.strip()
    ntp_status = ntp_status.split("=",1)[1]
    ntp_status = True if ntp_status == "yes" else False
    return ntp_status
