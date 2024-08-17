#! cd .. && python -m demo.pong2_launcher
# Windows only launcher.
# 

import os
import sys
import datetime
import time
import ctypes
user32 = ctypes.windll.user32
import win32con
import win32gui
import win32process
import subprocess

# https://github.com/ahrm/SDWM/blob/main/window-manager.py


def get_window_order_helper(hwnd):
    if not hwnd:
        return []
    next_window = user32.GetWindow(hwnd, win32con.GW_HWNDNEXT)
    if win32gui.IsWindowVisible(hwnd) and len(win32gui.GetWindowText(hwnd)) > 0:
        return [hwnd] + get_window_order_helper(next_window)
    else:
        return get_window_order_helper(next_window)

def get_visible_window_order():
    top = user32.GetTopWindow(None)
    return get_window_order_helper(top)

def get_window_placement(hwnd):
    placement = win32gui.GetWindowPlacement(hwnd)
    rect = win32gui.GetWindowRect(hwnd)
    name = win32gui.GetWindowText(hwnd)
    ctid, cpid = win32process.GetWindowThreadProcessId(hwnd)
    processed_placement = (hwnd, cpid,  rect)
    return processed_placement

def get_proc_hwnd(procs, timeout=10):
    """ wait for the process to start and find the associated hwnd
        assuming one hwnd per proc
    """
    found = [None for p in procs]
    start = time.time()
    sleep_time = .1
    for i in range(int(timeout/sleep_time+0.5)+1):
        windows = get_visible_window_order()
        window_placements = list(map(get_window_placement, windows))
        #foreground_window = win32gui.GetForegroundWindow()

        #print(windows)
        pids = [x[2] for x in window_placements]
        #print(pids)
        for hwnd, cpid, rect in window_placements:

            for idx, proc in enumerate(procs):
                if cpid == proc.pid:
                    found[idx] = (hwnd, cpid, rect)

        if all([h is not None for h in found]):
            break

        time.sleep(sleep_time)
    end = time.time()
    print(end - start)
    return found

def wait_till_done(procs):
    """
    if one process dies kill the others
    """
    found = [0,0]
    while True:
        for idx, proc in enumerate(procs):
            if proc.poll() is not None:
                found[idx] = 1
        if sum(found) != 0:
            break
        time.sleep(.33)

    for proc in procs:
        if proc.poll() is None:
            proc.kill()

    while any([proc.poll() is None for proc in procs]):
        time.sleep(.33)

args1 =[sys.executable, "-m", "demo.pong2_client", '--id=1']
args2 =[sys.executable, "-m", "demo.pong2_client", '--id=2']

proc1 = subprocess.Popen(args1, stdin=subprocess.DEVNULL)
proc2 = subprocess.Popen(args2, stdin=subprocess.DEVNULL)

procs = [proc1, proc2]

hwnds = get_proc_hwnd(procs)

if hwnds is None or len(hwnds) == 0:
    sys.stderr.write("failed to enumerate child processes\n")

    exit(1)

for idx, (hwnd, cpid, rect) in enumerate(hwnds):
    print(hwnd, cpid, rect)
    x1, y1, x2, y2 = rect
    w = x2 - x1
    h = y2 - y1
    if idx == 0:
        x1 = 0
    else:
        x1 = 1920 - w
    y1 = (1080 - h)//2 #center
    win32gui.SetWindowPos(hwnd, 0, x1, y1, w, h, win32con.SWP_SHOWWINDOW)

    wait_till_done(procs)


