import uuid
import psutil
import subprocess
import socket
import time
import os

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
def get_default_gateway():
    """
    讀 /proc/net/route，找出 Destination=0 的那行，
    返回 (gateway_ip, interface_name)，如果找不到則回 (None, None)
    """
    with open("/proc/net/route") as f:
        for line in f.readlines()[1:]:
            fields = line.strip().split()
            iface, dest, gateway, flags = fields[0], fields[1], fields[2], fields[3]
            # flags bit1 (0x2) 代表 UP，dest=="00000000" 代表 default route
            if dest == "00000000" and int(flags, 16) & 0x2:
                gw = socket.inet_ntoa(struct.pack("<L", int(gateway, 16)))
                return gw, iface
    return None, None

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
    default_gw, gw_iface = get_default_gateway()

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
            "MAC":             None,
            "IPv4":            None,
            "SubnetMask":      None,
            "AddressOrigin":   "Static",
            "Gateway":         None,
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
                # DHCP lease 存在就標為 DHCP
                lease = f"/var/lib/dhcp/dhclient.{name}.lease"
                if os.path.exists(lease):
                    iface["AddressOrigin"] = "DHCP"
                # 如果這個介面就是 default route，就填 Gateway
                if name == gw_iface:
                    iface["Gateway"] = default_gw

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
