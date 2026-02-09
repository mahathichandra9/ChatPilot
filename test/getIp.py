#!/usr/bin/env python3
"""
net_os_sweep_fixed.py

Improved auto-detection of local IPv4 addresses. If auto-detect picks a wrong IP,
the script prints all candidate IPv4 addresses and lets you choose the correct one.

Usage:
    python3 net_os_sweep_fixed.py            # interactive: auto-detect or choose
    python3 net_os_sweep_fixed.py 192.168.1  # use provided prefix directly
    python3 net_os_sweep_fixed.py --auto     # force auto-detect first suitable IP
    python3 net_os_sweep_fixed.py --start 1 --end 50

Notes:
 - Works on Windows, Linux, macOS.
 - If you have VPNs/virtual adapters, choose the real LAN adapter from the list.
"""

import argparse
import concurrent.futures
import platform
import re
import socket
import subprocess
import sys
from typing import List, Optional, Tuple

# small apple OUI set (can expand)
APPLE_OUIS = {"00:1e:c2", "00:17:f2", "00:1f:5b", "ac:bc:32", "3c:5a:b4"}

def list_local_ipv4_addresses() -> List[str]:
    """
    Return a list of non-loopback IPv4 addresses found on the host.
    Uses platform-specific commands, falls back to trying socket technique.
    """
    system = platform.system().lower()
    addrs = set()

    try:
        if system == "windows":
            # parse ipconfig - using simpler more robust patterns
            proc = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=3)
            out = proc.stdout
            # Match IPv4 addresses with various spacing patterns
            for m in re.finditer(r"IPv4\s+[Aa]ddress[\s\.]+:\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", out):
                ip = m.group(1)
                if not ip.startswith("127.") and not ip.startswith("169.254"):
                    addrs.add(ip)
            # Also try simple pattern
            if not addrs:
                for m in re.finditer(r"((?:[0-9]{1,3}\.){3}[0-9]{1,3})", out):
                    ip = m.group(1)
                    if not ip.startswith("127.") and not ip.startswith("169.254"):
                        # validate it looks like an IP
                        try:
                            parts = [int(x) for x in ip.split(".")]
                            if all(0 <= p <= 255 for p in parts) and parts != [255, 255, 255, 255]:
                                addrs.add(ip)
                        except:
                            pass
        else:
            # try `ip -4 addr` (Linux)
            proc = subprocess.run(["/sbin/ip", "-4", "addr"], capture_output=True, text=True, timeout=2)
            out = proc.stdout
            if not out:
                # fallback to "ip -4 addr show"
                proc = subprocess.run(["ip", "-4", "addr", "show"], capture_output=True, text=True, timeout=2)
                out = proc.stdout
            if out:
                for m in re.finditer(r"inet\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)/", out):
                    ip = m.group(1)
                    if not ip.startswith("127.") and not ip.startswith("169.254"):
                        addrs.add(ip)
            else:
                # macOS or systems without ip command -> parse ifconfig
                proc = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=2)
                out = proc.stdout
                for m in re.finditer(r"\s+inet\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)\s", out):
                    ip = m.group(1)
                    if not ip.startswith("127.") and not ip.startswith("169.254"):
                        addrs.add(ip)
    except Exception as e:
        print(f"Debug: Exception during address detection: {e}")

    # Last-resort: socket trick (may return a single IP, sometimes 127.x)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127.") and not ip.startswith("169.254"):
            addrs.add(ip)
    except Exception:
        pass

    return sorted(addrs)

# ---- ping + TTL parsing + arp functions (similar to previous) ----
def run_ping_and_get_ttl(ip: str, timeout_ms: int = 800) -> Optional[int]:
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    elif system == "linux":
        secs = max(1, int((timeout_ms + 999) // 1000))
        cmd = ["ping", "-c", "1", "-W", str(secs), ip]
    elif system == "darwin":
        cmd = ["ping", "-c", "1", "-W", str(timeout_ms), ip]
    else:
        cmd = ["ping", "-c", "1", ip]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=(timeout_ms/1000)+2)
        out = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0:
            return None
        m = re.search(r"[Tt][Tt][Ll]=\s*?(\d{1,3})", out)
        if m: return int(m.group(1))
        m2 = re.search(r"[Tt][Tt][Ll]\s+(\d{1,3})", out)
        if m2: return int(m2.group(1))
        m3 = re.search(r"TTL[:=]?\s*(\d{1,3})", out, re.I)
        if m3: return int(m3.group(1))
        return None
    except Exception:
        return None

def get_mac_from_arp(ip: str) -> Optional[str]:
    system = platform.system().lower()
    try:
        if system == "windows":
            c = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=3)
            out = c.stdout
            pat = re.compile(rf"^\s*{re.escape(ip)}\s+([0-9a-fA-F\-]+)\s+", re.M)
            m = pat.search(out)
            if m: return m.group(1).replace("-", ":").lower()
            return None
        else:
            c = subprocess.run(["arp", "-n", ip], capture_output=True, text=True, timeout=2)
            out = (c.stdout or "") + (c.stderr or "")
            m = re.search(r"([0-9a-fA-F]{2}(?:[:\-][0-9a-fA-F]{2}){5})", out)
            if m: return m.group(1).replace("-", ":").lower()
            c2 = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=2)
            out2 = c2.stdout
            m2 = re.search(rf"{re.escape(ip)}.*?(([0-9a-fA-F]{{2}}[:\-]){{5}}[0-9a-fA-F]{{2}})", out2)
            if m2: return m2.group(1).replace("-", ":").lower()
            m3 = re.search(r" at ([0-9a-fA-F:]{17}) ", out2)
            if m3: return m3.group(1).lower()
            return None
    except Exception:
        return None

def guess_os_from_ttl(ttl: Optional[int]) -> str:
    if ttl is None: return "unknown"
    if ttl >= 240: return "network-gear/other"
    if ttl >= 120: return "windows"
    if 50 <= ttl <= 90: return "unix-like"
    return "unknown"

def refine_guess_with_name_and_mac(guess: str, hostname: Optional[str], mac: Optional[str]) -> str:
    name = (hostname or "").lower()
    if "iphone" in name or "ipad" in name: return "ios"
    if "macbook" in name or "macmini" in name or ("mac" in name and "macos" in name): return "macos"
    if mac:
        prefix = ":".join(mac.split(":")[0:3])
        if prefix in APPLE_OUIS:
            if "iphone" in name or "ipad" in name: return "ios"
            if "mac" in name or "macbook" in name: return "macos"
            return "apple-device"
    if guess == "unix-like": return "linux"
    return guess

def probe_ip(prefix: str, last_octet: int, timeout_ms: int = 800) -> Optional[Tuple[str,str,str,Optional[str]]]:
    ip = f"{prefix}.{last_octet}"
    ttl = run_ping_and_get_ttl(ip, timeout_ms=timeout_ms)
    if ttl is None: return None
    hostname = ip
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except Exception:
        hostname = ip
    mac = get_mac_from_arp(ip)
    base_guess = guess_os_from_ttl(ttl)
    final = refine_guess_with_name_and_mac(base_guess, hostname, mac)
    return (ip, final, hostname, mac)

def scan_network(prefix: str, start: int = 0, end: int = 255, workers: int = 200):
    if start<0 or end>255 or start> end: raise ValueError("invalid range")
    print(f"Scanning {prefix}.{start} -> {prefix}.{end} ...")
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(probe_ip, prefix, i): i for i in range(start, end+1)}
        completed=0
        total = end-start+1
        for fut in concurrent.futures.as_completed(futures):
            completed+=1
            try:
                res = fut.result()
            except Exception:
                res = None
            if res:
                results.append(res)
                ip, os_guess, hostname, mac = res
                print(f"{ip:15} | {os_guess:15} | {hostname:30} | {mac or 'N/A'}")
            if completed % 25 == 0 or completed==total:
                print(f"Progress: {completed}/{total}")
    return results

def choose_prefix_interactive() -> str:
    addrs = list_local_ipv4_addresses()
    if not addrs:
        print("No non-loopback IPv4 addresses discovered automatically.")
        # fallback to socket try
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8",80))
            ip = s.getsockname()[0]
            s.close()
            addrs = [ip] if ip and not ip.startswith("127.") else []
        except Exception:
            pass
    if not addrs:
        print("Could not detect local addresses. Please provide the prefix manually (e.g. 192.168.1).")
        sys.exit(1)

    print("\nDetected IPv4 addresses on this machine:")
    for idx, a in enumerate(addrs):
        print(f"  [{idx}] {a}")
    
    # prefer a non-VPN-looking address heuristically: pick the first 192.168.* or 10.* or 172.16-31.*
    # Exclude addresses that look like VPN (high numbered addresses, VM addresses, etc.)
    def is_likely_real_lan(addr):
        parts = addr.split(".")
        first = int(parts[0])
        second = int(parts[1]) if len(parts) > 1 else 0
        
        # Prefer common private ranges
        if first == 192 and second == 168:
            return True
        if first == 10:
            return True
        if first == 172 and 16 <= second <= 31:
            return True
        return False
    
    preferred = None
    for a in addrs:
        if is_likely_real_lan(a):
            try:
                # Try to ping to verify it's actually active
                res = run_ping_and_get_ttl(a, timeout_ms=400)
                if res is not None:
                    preferred = a
                    break
            except:
                preferred = a
                break
    
    if preferred:
        print(f"\nAuto-selecting preferred address: {preferred}")
        ip_choice = preferred
    else:
        # ask user to choose
        print()
        while True:
            choice = input(f"Choose address index [0-{len(addrs)-1}] (or press Enter to pick {addrs[0]}): ").strip()
            if choice=="":
                ip_choice = addrs[0]; break
            try:
                i = int(choice)
                if 0 <= i < len(addrs):
                    ip_choice = addrs[i]; break
            except Exception:
                pass
            print("Invalid choice.")
    prefix = ".".join(ip_choice.split(".")[:3])
    print(f"Using prefix: {prefix}.x (from {ip_choice})\n")
    return prefix

def main():
    parser = argparse.ArgumentParser(description="LAN sweep with better local IP detection.")
    parser.add_argument("prefix", nargs="?", help="first 3 octets e.g. 192.168.1 (optional)")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=255)
    parser.add_argument("--workers", type=int, default=200)
    parser.add_argument("--timeout", type=int, default=800)
    parser.add_argument("--auto", action="store_true", help="auto-select a detected address instead of prompting")
    args = parser.parse_args()

    prefix = args.prefix
    if prefix:
        prefix = prefix.rstrip(".")
        if len(prefix.split(".")) != 3:
            print("Prefix must be three octets, e.g. 192.168.1")
            sys.exit(1)
    else:
        # interactive detection + choice
        if args.auto:
            addrs = list_local_ipv4_addresses()
            if not addrs:
                print("Auto-detect failed, falling back to interactive choice.")
                prefix = choose_prefix_interactive()
            else:
                # pick preferred
                preferred = None
                for a in addrs:
                    parts = a.split(".")
                    if parts[0]=="192" or parts[0]=="10" or (parts[0]=="172" and 16 <= int(parts[1]) <=31):
                        preferred = a; break
                if not preferred:
                    preferred = addrs[0]
                prefix = ".".join(preferred.split(".")[:3])
                print(f"Auto-using prefix {prefix}.x from address {preferred}")
        else:
            prefix = choose_prefix_interactive()

    results = scan_network(prefix, args.start, args.end, args.workers)
    print("\nScan complete. Found:", len(results), "hosts up")
    print(f"{'IP':15} | {'OS guess':15} | {'hostname':30} | {'MAC'}")
    print("-"*100)
    for ip, os_guess, hostname, mac in sorted(results, key=lambda x: tuple(int(p) for p in x[0].split("."))):
        print(f"{ip:15} | {os_guess:15} | {hostname:30} | {mac or 'N/A'}")

if __name__ == "__main__":
    main()
