import os
import sys
import psutil

def kill_other_jarvis():
    current_pid = os.getpid()
    killed = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Check if process is Python
            if proc.info['name'] and proc.info['name'].lower() in ('python.exe', 'pythonw.exe'):
                cmdline = proc.info['cmdline'] or []
                # Check if it is running jarvis.py
                if any('jarvis.py' in arg.lower() for arg in cmdline):
                    pid = proc.info['pid']
                    if pid != current_pid:
                        print(f"[KILL] Stopping background Jarvis process (PID: {pid})...")
                        proc.kill()
                        killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    if killed == 0:
        print("[INFO] No other running Jarvis processes were found.")
    else:
        print(f"[OK] Successfully terminated {killed} other Jarvis process(es).")

if __name__ == "__main__":
    kill_other_jarvis()
