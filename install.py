#!/usr/bin/env python3
"""Install or erase skeletor.

Puts the runner in a dot-folder and one login autostart entry.
Erase deletes both and stops the runner. Nothing else.
"""
import os
import sys
import json
import shutil
import signal
import subprocess
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ("install.py", "skeletor.py", "skeleton.mp4")
if sys.platform.startswith("win"):
    FILES += ("skeleton.frames", "skeleton.wav")


def dest():
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, ".skeletor")
    return os.path.join(os.path.expanduser("~"), ".local", "share", ".skeletor")


def autostart():
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(
            base, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "skeletor.cmd"
        )
    return os.path.join(os.path.expanduser("~"), ".config", "autostart", "skeletor.desktop")


def python_exe():
    if sys.platform.startswith("win"):
        exe = sys.executable
        sibling = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(sibling):
            return sibling
        return exe
    return shutil.which("python3") or sys.executable


def ask(prompt, default, valid, rule):
    """Ask until the answer fits the rule. Enter, or no terminal, takes the default."""
    while True:
        try:
            answer = input("%s [%s]: " % (prompt, default)).strip() or default
        except EOFError:
            return float(Fraction(default))
        try:
            value = Fraction(answer)
            if valid(value):
                return float(value)
        except (ValueError, ZeroDivisionError):
            pass
        print(rule)


def ask_timings():
    """(check_every, chance), where Enter keeps what's saved, or the defaults if nothing is."""
    import skeletor
    every, chance = skeletor.load_settings(dest())
    show = lambda x: str(Fraction(x).limit_denominator(10 ** 6))
    return (
        ask(
            "seconds between rolls", show(every),
            lambda v: 1 <= v <= 86400, "use a number from 1 to 86400",
        ),
        ask(
            "chance of a strike on each roll, like 1/60 or 0.02", show(chance),
            lambda v: 0 <= v <= 1, "use a number from 0 to 1, like 1/60 or 0.02",
        ),
    )


def save_timings(every, chance):
    with open(os.path.join(dest(), "settings.json"), "w") as f:
        json.dump({"check_every": every, "chance": chance}, f)
    if chance:
        print("averages one strike every %.1f minutes" % (every / chance / 60))
    else:
        print("chance is 0, so it never strikes")


def is_installed():
    # Needs both: if one is gone, a normal install puts it back.
    return os.path.exists(os.path.join(dest(), "skeletor.py")) and os.path.exists(autostart())


def already_installed():
    print("skeletor is already installed")
    print("  1  change timings")
    print("  2  erase")
    print("  3  leave it as it is")
    try:
        choice = input("> ").strip().lower()
    except EOFError:
        choice = ""
    if choice in ("1", "change", "timings"):
        save_timings(*ask_timings())
        print("the runner picks this up after its next roll")
    elif choice in ("2", "erase", "remove"):
        erase()
    else:
        print("nothing done")


def install():
    if is_installed():
        already_installed()
        return
    missing = [n for n in FILES if not os.path.exists(os.path.join(HERE, n))]
    if missing:
        sys.exit("missing next to install.py: " + ", ".join(missing))
    every, chance = ask_timings()
    folder = dest()
    os.makedirs(folder, exist_ok=True)
    # Re-running the installed copy: the files are already there.
    if not os.path.samefile(HERE, folder):
        for name in FILES:
            shutil.copy2(os.path.join(HERE, name), os.path.join(folder, name))
    runner = os.path.join(folder, "skeletor.py")
    py = python_exe()
    link = autostart()
    os.makedirs(os.path.dirname(link), exist_ok=True)
    if sys.platform.startswith("win"):
        with open(link, "w", newline="\r\n") as f:
            f.write('@echo off\r\nstart "" "%s" "%s"\r\n' % (py, runner))
        subprocess_hide(folder)
    else:
        with open(link, "w") as f:
            f.write(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=skeletor\n"
                "Exec=%s %s\n"
                "Terminal=false\n"
                "NoDisplay=true\n" % (py, runner)
            )
    with open(os.path.join(folder, "REMOVE.txt"), "w") as f:
        f.write("delete this folder and delete:\n%s\n" % link)
    print("installed")
    print(folder)
    print(link)
    save_timings(every, chance)
    if not sys.platform.startswith("win") and not shutil.which("mpv"):
        print("no mpv found, so it will show a green background. install mpv to make it see-through")
    me = os.path.join(folder, "install.py")
    print("starts at next login")
    print('test now: "%s" "%s" run' % (sys.executable, me))
    print('erase: "%s" "%s" erase' % (sys.executable, me))


def subprocess_hide(folder):
    if shutil.which("attrib"):
        subprocess.run(["attrib", "+h", folder], check=False)


def runner_path():
    installed = os.path.join(dest(), "skeletor.py")
    if os.path.exists(os.path.join(dest(), "skeleton.mp4")):
        return installed
    local = os.path.join(HERE, "skeletor.py")
    if os.path.exists(os.path.join(HERE, "skeleton.mp4")):
        return local
    sys.exit("nothing to run. install first.")


def run():
    py = sys.executable
    if os.path.basename(py).lower() == "pythonw.exe":
        py = os.path.join(os.path.dirname(py), "python.exe")
    subprocess.run([py, runner_path(), "--once"], check=False)


def erase():
    folder = dest()
    pid_path = os.path.join(folder, "skeletor.pid")
    try:
        pid = int(open(pid_path).read().strip())
    except (OSError, ValueError):
        pid = None
    if pid and pid != os.getpid():
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    shutil.rmtree(folder, ignore_errors=True)
    link = autostart()
    try:
        os.remove(link)
    except OSError:
        pass
    print("erased")
    print(folder)
    print(link)


def menu():
    print("skeletor")
    print("  1  install")
    print("  2  erase")
    print("  3  run")
    try:
        choice = input("> ").strip().lower()
    except EOFError:
        print("python3 install.py install")
        print("python3 install.py erase")
        print("python3 install.py run")
        return
    if choice in ("1", "install"):
        install()
    elif choice in ("2", "erase", "remove"):
        erase()
    elif choice in ("3", "run", "test"):
        run()
    else:
        print("nothing done")


def main():
    # ponytail: one hidden folder, one autostart file. both paths are printed.
    assert dest().endswith(".skeletor")
    assert os.path.basename(autostart()).startswith("skeletor.")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "install":
        install()
    elif cmd in ("erase", "remove"):
        erase()
    elif cmd in ("run", "test"):
        run()
    elif cmd in ("-h", "--help"):
        print("python3 install.py install")
        print("python3 install.py erase")
        print("python3 install.py run")
    else:
        menu()


if __name__ == "__main__":
    main()
