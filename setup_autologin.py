r"""
setup_autologin.py
------------------
Sets up auto-login so Windows boots directly to your desktop
without asking for a password.

Also lets you set a voice unlock code in .env:
    VOICE_UNLOCK_CODE=sunshine

When Jarvis hears "unlock <code>" it will send the Windows+L
key then type the password — bypassing the lock screen.

Run ONCE as Administrator:
    .venv\Scripts\python.exe setup_autologin.py
"""
import ctypes
import os
import subprocess
import sys
import winreg
from pathlib import Path

HERE   = Path(__file__).resolve().parent
DOTENV = HERE / ".env"


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def set_auto_login(username: str, password: str = "") -> bool:
    """Write auto-login keys to the Windows Registry."""
    try:
        # Also disable passwordless login requirement (Windows Hello) so AutoAdminLogon works on Windows 10/11
        try:
            pwdless_key = winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\PasswordLess\Device",
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(pwdless_key, "DevicePasswordLessBuildVersion", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(pwdless_key)
            print("[OK] Disabled passwordless Windows Hello enforcement in Registry.")
        except Exception as e:
            print(f"[WARN] Could not disable passwordless boot requirement in registry: {e}")

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon",
            0, winreg.KEY_SET_VALUE | winreg.KEY_READ
        )
        winreg.SetValueEx(key, "AutoAdminLogon",  0, winreg.REG_SZ, "1")
        winreg.SetValueEx(key, "DefaultUserName",  0, winreg.REG_SZ, username)
        winreg.SetValueEx(key, "DefaultDomainName", 0, winreg.REG_SZ,
                          os.environ.get("USERDOMAIN", ""))
        if password:
            winreg.SetValueEx(key, "DefaultPassword", 0, winreg.REG_SZ, password)
        else:
            # Remove password key if blank (for accounts without a password)
            try:
                winreg.DeleteValue(key, "DefaultPassword")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except PermissionError:
        return False
    except Exception as e:
        print(f"[ERROR] Registry write failed: {e}")
        return False


def disable_lock_on_sleep() -> None:
    """Stop Windows from asking for password after sleep."""
    try:
        # Set require password on wakeup = 0
        subprocess.run(
            ["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", "SUB_NONE",
             "0e796bdb-100d-47d6-a2d5-f7d2daa51f51", "0"],
            capture_output=True
        )
        subprocess.run(
            ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", "SUB_NONE",
             "0e796bdb-100d-47d6-a2d5-f7d2daa51f51", "0"],
            capture_output=True
        )
        subprocess.run(["powercfg", "/apply"], capture_output=True)
    except Exception as e:
        print(f"[WARN] Could not disable lock-on-sleep: {e}")


def set_voice_unlock_code(code: str) -> None:
    """Add VOICE_UNLOCK_CODE to .env file."""
    lines = DOTENV.read_text().splitlines() if DOTENV.exists() else []
    updated = False
    for i, line in enumerate(lines):
        if line.startswith("VOICE_UNLOCK_CODE="):
            lines[i] = f"VOICE_UNLOCK_CODE={code}"
            updated = True
            break
    if not updated:
        lines.append(f"VOICE_UNLOCK_CODE={code}")
    DOTENV.write_text("\n".join(lines) + "\n")


def main():
    if not is_admin():
        print("[INFO] Requesting administrator privileges...")
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{sys.argv[0]}" {params}', None, 1
        )
        sys.exit(0)

    print("=" * 55)
    print("  JARVIS — Auto-Login & Voice Unlock Setup")
    print("=" * 55)

    username = os.environ.get("USERNAME", "")
    print(f"\nWindows user: {username}")

    print("\n--- AUTO-LOGIN (no password on boot) ---")
    print("WARNING: This means anyone who opens your laptop will get in.")
    print("Only do this if your laptop is for personal use at home.")
    confirm = input("Set up auto-login? (yes/no): ").strip().lower()

    if confirm == "yes":
        password = input("Enter your Windows password (leave blank if none): ").strip()
        if set_auto_login(username, password):
            print("[OK] Auto-login configured. Next boot will skip the password screen.")
            disable_lock_on_sleep()
            print("[OK] Lock-on-sleep disabled (no password after wake from sleep).")
        else:
            print("[FAIL] Could not set auto-login. Registry write failed.")

    print("\n--- VOICE UNLOCK CODE ---")
    print("Set a code word that Jarvis recognizes to unlock/wake your laptop.")
    print("Example: say 'unlock sunshine' and Jarvis will dismiss the lock screen.")
    code = input("Enter your voice unlock code (e.g. sunshine): ").strip()
    if code:
        set_voice_unlock_code(code)
        print(f"[OK] Voice unlock code set: '{code}'")
        print(f"     Say 'unlock {code}' to unlock your laptop via Jarvis.")
    else:
        print("[SKIP] No voice unlock code set.")

    print("\n" + "=" * 55)
    print("  Done! Restart your laptop to see the changes.")
    print("=" * 55)


if __name__ == "__main__":
    main()
