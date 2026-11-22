#!/usr/bin/env python3
"""
ROAST GUARD — PySide6 edition.
Catches you slacking on banned sites and roasts you for it.

Install:  pip install PySide6
Run:      python roastguard_qt.py
Build:    pyinstaller --onefile --noconsole roastguard_qt.py

Features: escalating roasts · insult workshop · hardcore mode · system tray
          roast packs (import/export/drag-drop/clipboard) · roast stats 📊
          per-roast win rate ✅ · idle detection 😴 · Pomodoro mode 🍅
          (focus blocks with faster roasts + strict break-on-slack,
           breaks where slacking is fully sanctioned)
          work hours schedule · auto-start pomodoro · CSV stats export
          repeat offender roasts · praise on quick exit · Ctrl+C graceful exit

Windows works out of the box.
macOS: grant Accessibility to your terminal/app (Privacy & Security).
Linux X11: sudo apt install xdotool xprintidle
           (Wayland blocks window titles & idle time).
"""

import ctypes, csv, json, os, platform, random, re, signal, subprocess, sys, time
from datetime import date, datetime

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow, QMenu,
    QMessageBox, QProgressBar, QPushButton, QRadioButton, QScrollArea,
    QSpinBox, QSystemTrayIcon, QTextEdit, QVBoxLayout, QWidget,
)

APP = "RoastGuard"
DATA_FILE = os.path.join(os.path.expanduser("~"), ".roastguard.json")
CHECK = 3                                   # seconds between window checks
HARDCORE_PHRASE = "i will focus now"
PACK_VERSION = 1
MAX_ROAST_LEN = 250
WIN_SECS = 60                               # roast "wins" if you leave within this
MAX_LINGER = 900                            # cap measured linger (15 min)
DEFAULT_IDLE_AFTER = 300                    # 5 min without input = idle
POM_STRICT_GRACE = 15                       # secs on a banned site before strict kill

BG, CARD, FG, DIM = "#101018", "#1a1a26", "#eaeaf2", "#8b8b9e"
RED, GREEN, YELLOW, ACCENT = "#ff5c5c", "#3ddc84", "#ffd166", "#7c5cff"
IDLE_C = "#6ec3ff"                          # idle / long-break color
SHELL = "#1c0e12"                           # roast popup background

DEFAULT_SITES = [
    "youtube", "reddit", "twitter", "instagram", "facebook", "tiktok",
    "netflix", "twitch", "discord", "pinterest", "imgur", "9gag",
    "spotify", "hulu", "prime video", "disney", "steam", "roblox",
]

TIER1 = [
    "Oh, {site}. What a surprise. Said no productivity guru ever.",
    "“Just a quick look,” you said. We both know how this ends.",
    "Your to-do list is watching this happen. It's losing hope.",
    "Work was RIGHT THERE. And yet, {site} happened.",
    "Your brain said 'quick break.' Your brain is a liar with no calendar.",
    "Fascinating strategy: fail faster by scrolling sooner.",
]
TIER2 = [
    "{mins} minutes on {site}. Your deadline is laughing. Audibly.",
    "At this point just put '{site} enjoyer' at the top of your résumé.",
    "Fun fact: {mins} minutes ago, you were still a person with goals.",
    "Imagine if this energy went into your actual work. Terrifying, I know.",
    "{mins} minutes. That's a full gym session. That you're also not doing.",
    "Your future self just texted one word: 'why?' — with 47 question marks.",
    "This isn't a break anymore. This is a career pivot — to nothing.",
]
TIER3 = [
    "{mins} MINUTES on {site}. Your ambitions just filed a missing persons report.",
    "Somewhere, a focused version of you felt a disturbance and quietly wept.",
    "Your goals didn't die. They left. While you scrolled. {mins} minutes ago.",
    "The bar was on the floor. You brought a shovel and kept digging.",
    "If procrastination were an Olympic sport, you'd get distracted during the finals.",
    "Official diagnosis: chronic {site} dependency, zero shame, incurable.",
    "Your productivity called from far away. It's not coming back tonight.",
]
FOCUS_BROKEN = [
    "The block was {mins} minutes. You lasted until {site} showed up. {site} 1 — you 0.",
    "{mins} minutes of potential, undone by one tab. {site} sends its regards.",
    "That was a {mins}-minute focus block. Now it's a {mins}-minute cautionary tale.",
    "You broke the block for {site}. The block remembers. So do I.",
    "Pomodoro speedrun any%: quit after {mins} minutes. {site} awaits your return.",
]
REPEAT_OFFENDER = [
    "Back on {site}? We JUST talked about this. {mins} minutes ago.",
    "Are you stuck in a loop? {site} again. Your brain called, it's filing for divorce.",
    "Déjà vu. {site}. {mins} minutes. I'm running out of ways to say 'stop'.",
    "Groundhog Day, but with {site} and even less personal growth.",
]
BUILTIN = {1: TIER1, 2: TIER2, 3: TIER3}
TIER_NAMES = {1: "Mild", 2: "Mean", 3: "Brutal"}
TIPS = [
    "Tip: 'Open in a new tab and forget' is not a productivity system.",
    "Remember: Netflix is not a second monitor for your work.",
    "Tip: Ctrl+W is the most honest shortcut you'll press all day.",
    "Remember: every tab you open is a tiny promise you're about to break.",
    "Tip: YouTube 'research' only counts if you take notes. You don't take notes.",
    "Remember: the algorithm doesn't love you back. Your deadline doesn't either.",
    "Tip: coffee breaks no longer count as focus. The system knows. 😴",
    "🍅 Tip: a Pomodoro break is sanctioned slacking — guilt-free, roast-free.",
    "🍅 Tip: during a focus block the roasts come faster. It's not personal. It's schedule.",
]

QSS = f"""
* {{ font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; font-size: 10pt; }}
QMainWindow, QDialog {{ background-color: {BG}; }}
QLabel {{ color: {FG}; background: transparent; }}
QFrame#card {{ background-color: {CARD}; border-radius: 10px; }}
QPushButton {{
    background-color: {CARD}; color: {FG}; border: none; border-radius: 6px;
    padding: 8px 14px; font-weight: 600;
}}
QPushButton:hover {{ background-color: #2c2c40; }}
QPushButton:pressed {{ background-color: #22223a; }}
QPushButton:disabled {{ color: #55556a; }}
QPushButton[variant="primary"] {{ background-color: {GREEN}; color: #101018; }}
QPushButton[variant="primary"]:hover {{ background-color: #55e795; }}
QPushButton[variant="danger"]  {{ background-color: {RED};   color: #ffffff; }}
QPushButton[variant="danger"]:hover  {{ background-color: #ff7575; }}
QPushButton[variant="accent"]  {{ background-color: {ACCENT}; color: #ffffff; }}
QPushButton[variant="accent"]:hover  {{ background-color: #927cff; }}
QPushButton[variant="warn"]    {{ background-color: {YELLOW}; color: #101018; }}
QPushButton[variant="warn"]:hover    {{ background-color: #ffdd85; }}
QPushButton[variant="ghost"]   {{ background-color: transparent; color: {DIM}; }}
QPushButton[variant="ghost"]:hover {{ background-color: {CARD}; color: {FG}; }}
QListWidget {{
    background-color: {CARD}; border: none; border-radius: 8px; padding: 4px;
}}
QListWidget::item {{ padding: 4px 6px; border-radius: 4px; }}
QListWidget::item:selected {{ background-color: {ACCENT}; color: #ffffff; }}
QLineEdit, QTextEdit, QSpinBox {{
    background-color: {CARD}; color: {FG}; border: 1px solid #2c2c40;
    border-radius: 6px; padding: 6px; selection-background-color: {ACCENT};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 16px; border: none; background: #2c2c40;
}}
QCheckBox, QRadioButton {{ color: {FG}; spacing: 6px; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3a3a52; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QProgressBar {{ background: #2a2a38; border: none; border-radius: 4px; }}
QProgressBar::chunk {{ background: {GREEN}; border-radius: 4px; }}
QMenu {{ background-color: {CARD}; color: {FG}; border: 1px solid #2c2c40; }}
QMenu::item {{ padding: 6px 22px; }}
QMenu::item:selected {{ background-color: {ACCENT}; }}
QToolTip {{ background-color: {CARD}; color: {FG}; border: 1px solid #3a3a52; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
"""


# ------------------------------------------------------------------ helpers

def fill(text: str, site: str, mins: int) -> str:
    """Safe placeholder substitution — survives stray braces like ':-{'."""
    return text.replace("{site}", site).replace("{mins}", str(mins))


def pool_for(tier: int, data: dict) -> list:
    """Your custom roasts + built-ins for a tier."""
    return list(data["custom_insults"].get(str(tier), [])) + BUILTIN[tier]


def stat_entry(data: dict, tier, template: str) -> dict:
    """Get (or create) the stats record for a roast, ensuring all keys."""
    store = data.setdefault("roast_stats", {}).setdefault(str(tier), {})
    e = store.setdefault(template, {})
    e.setdefault("count", 0)
    e.setdefault("last", 0.0)
    e.setdefault("wins", 0)
    e.setdefault("losses", 0)
    e.setdefault("linger_total", 0.0)
    e.setdefault("linger_n", 0)
    return e


def record_fire(data: dict, tier: int, template: str):
    """Count one firing of a roast template."""
    e = stat_entry(data, tier, template)
    e["count"] += 1
    e["last"] = time.time()


def record_result(data: dict, tier: int, template: str, linger: float):
    """Record how long the user stayed on the site after a roast fired."""
    e = stat_entry(data, tier, template)
    linger = min(linger, MAX_LINGER)
    if linger <= WIN_SECS:
        e["wins"] += 1
    else:
        e["losses"] += 1
    e["linger_total"] += linger
    e["linger_n"] += 1


def make_pack(data: dict, tiers=(1, 2, 3), name="My custom roasts",
              author="anonymous slacker") -> dict:
    """Build a shareable roast-pack dict from the current custom insults."""
    return {
        "roastpack": PACK_VERSION,
        "name": name,
        "author": author,
        "exported": date.today().isoformat(),
        "tiers": {str(t): list(data["custom_insults"].get(str(t), []))
                  for t in tiers},
    }


def validate_pack(raw):
    """Parse & sanitize an imported pack.
    Returns (meta, tiers, skipped). Raises ValueError with a human reason."""
    if not isinstance(raw, dict):
        raise ValueError("a pack should be a JSON object, e.g. "
                         '{"tiers": {"1": ["..."]}}')

    tiers_in = raw.get("tiers")
    if not isinstance(tiers_in, dict):
        if any(k in raw for k in ("1", "2", "3")):
            tiers_in = {k: raw[k] for k in ("1", "2", "3") if k in raw}
        else:
            raise ValueError("no 'tiers' object found — expected "
                             '{"tiers": {"1": ["..."]}}')

    builtin_all = {r for pool in BUILTIN.values() for r in pool}
    tiers_out, skipped = {}, 0
    for key, val in tiers_in.items():
        if key not in ("1", "2", "3"):
            continue
        if not isinstance(val, list):
            raise ValueError(f"tier {key} should be a list of strings")
        clean = []
        for item in val:
            t = item.strip() if isinstance(item, str) else None
            if (not t or len(t) > MAX_ROAST_LEN or t in builtin_all
                    or t in clean):
                skipped += 1
                continue
            clean.append(t)
        if clean:
            tiers_out[key] = clean

    if not tiers_out:
        raise ValueError("no usable roasts found (empty, too long, or all "
                         "duplicates of built-ins)")
    meta = {"name": str(raw.get("name") or "Untitled pack"),
            "author": str(raw.get("author") or "unknown")}
    return meta, tiers_out, skipped


def active_window_title() -> str:
    """Title of the current foreground window (cross-platform)."""
    sysname = platform.system()
    try:
        if sysname == "Windows":
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            return buf.value or ""
        if sysname == "Darwin":
            script = (
                'tell application "System Events"\n'
                'set frontApp to name of first application process whose frontmost is true\n'
                'set winTitle to ""\n'
                'try\n'
                'set winTitle to name of front window of (first application process whose frontmost is true)\n'
                'end try\n'
                'return winTitle & " | " & frontApp\n'
                'end tell'
            )
            out = subprocess.run(["osascript", "-e", script],
                                 capture_output=True, text=True, timeout=3)
            return out.stdout.strip()
        if sysname == "Linux":
            out = subprocess.run(["xdotool", "getactivewindow", "getwindowname"],
                                 capture_output=True, text=True, timeout=3)
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def suggest_site_from_title(title: str):
    """Try to extract a useful ban keyword from a window title."""
    if not title:
        return None
    t = title.lower()
    known = ["youtube", "reddit", "twitter", "x.com", "instagram",
             "facebook", "tiktok", "netflix", "twitch", "discord",
             "pinterest", "imgur", "9gag", "spotify", "hulu",
             "prime video", "disney", "steam", "roblox", "tumblr",
             "linkedin", "whatsapp", "telegram", "slack", "gmail",
             "amazon", "ebay", "wikipedia"]
    for k in known:
        if k in t:
            return k
    m = re.search(r'([\w-]+)\.(com|net|org|io|tv|co|app|dev|me)\b', t)
    if m:
        return m.group(1)
    return None


def idle_seconds() -> float:
    """Seconds since last keyboard/mouse input (cross-platform)."""
    sysname = platform.system()
    try:
        if sysname == "Windows":
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint),
                            ("dwTime", ctypes.c_uint)]
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                return max(0, ctypes.windll.kernel32.GetTickCount()
                           - lii.dwTime) / 1000.0
        elif sysname == "Darwin":
            out = subprocess.run(["ioreg", "-c", "IOHIDSystem"],
                                 capture_output=True, text=True, timeout=3)
            for line in out.stdout.splitlines():
                if "HIDIdleTime" in line and "=" in line:
                    try:
                        return int(line.split("=")[-1].strip().strip('"')) / 1e9
                    except ValueError:
                        continue
        elif sysname == "Linux":
            out = subprocess.run(["xprintidle"],
                                 capture_output=True, text=True, timeout=3)
            if out.returncode == 0 and out.stdout.strip().isdigit():
                return int(out.stdout.strip()) / 1000.0
    except Exception:
        pass
    return 0.0


def fmt(secs: float) -> str:
    s = int(secs)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {sec:02d}s"


def secs_short(secs: float) -> str:
    s = int(secs)
    if s < 60:
        return f"{s}s"
    m, sec = divmod(s, 60)
    if m < 60:
        return f"{m}m{sec:02d}s" if sec else f"{m}m"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def mmss(secs: float) -> str:
    s = max(0, int(round(secs)))
    return f"{s // 60:02d}:{s % 60:02d}"


def ago(ts: float) -> str:
    if not ts:
        return "never"
    d = max(0, time.time() - ts)
    if d < 60:
        return "just now"
    if d < 3600:
        return f"{int(d // 60)}m ago"
    if d < 86400:
        return f"{int(d // 3600)}h ago"
    return f"{int(d // 86400)}d ago"


def pick_tier(streak: float) -> int:
    return 1 if streak < 180 else (2 if streak < 600 else 3)


def win_rate(e: dict):
    w, l = e.get("wins", 0), e.get("losses", 0)
    n = w + l
    return (w / n * 100.0, n) if n else (None, 0)


def avg_linger(e: dict):
    n = e.get("linger_n", 0)
    return (e.get("linger_total", 0.0) / n) if n else None


def fresh_daily() -> dict:
    today = date.today().isoformat()
    return {"date": today, "focus": 0, "distraction": 0, "insults": 0,
            "break": 0, "pomodoros": 0, "broken": 0}


def load_data() -> dict:
    base = {
        "sites": list(DEFAULT_SITES),
        "hardcore": False,
        "sound": True,
        "first_roast": 40,
        "idle_after": DEFAULT_IDLE_AFTER,
        "pom_focus_len": 25, "pom_break_len": 5,
        "pom_long_len": 15, "pom_long_every": 4, "pom_strict": True,
        "pom_auto_break": False, "pom_auto_focus": False,
        "work_hours_enabled": False, "work_start": "09:00", "work_end": "17:00",
        "force_focus": True,
        "total_insults": 0,
        "custom_insults": {"1": [], "2": [], "3": []},
        "roast_stats": {"1": {}, "2": {}, "3": {}},
        "daily": fresh_daily(),
    }
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        base.update({k: v for k, v in saved.items() if k in base})
        try:
            ia = int(base.get("idle_after", DEFAULT_IDLE_AFTER))
        except (TypeError, ValueError):
            ia = DEFAULT_IDLE_AFTER
        base["idle_after"] = max(60, min(1800, ia))

        def clampi(val, lo, hi, dflt):
            try:
                return max(lo, min(hi, int(val)))
            except (TypeError, ValueError):
                return dflt
        base["pom_focus_len"] = clampi(base.get("pom_focus_len"), 5, 90, 25)
        base["pom_break_len"] = clampi(base.get("pom_break_len"), 1, 30, 5)
        base["pom_long_len"] = clampi(base.get("pom_long_len"), 5, 45, 15)
        base["pom_long_every"] = clampi(base.get("pom_long_every"), 2, 8, 4)
        base["pom_strict"] = bool(base.get("pom_strict", True))

        ci = base.get("custom_insults")
        if not isinstance(ci, dict):
            ci = {}
        base["custom_insults"] = {
            str(t): [str(x) for x in ci.get(str(t), []) if str(x).strip()]
            for t in (1, 2, 3)}
        
        rs = base.get("roast_stats")
        if not isinstance(rs, dict):
            rs = {}
        norm = {}
        for t in ("1", "2", "3"):
            inner = rs.get(t) if isinstance(rs.get(t), dict) else {}
            clean = {}
            for k, v in inner.items():
                if not isinstance(k, str) or not k.strip():
                    continue
                if isinstance(v, dict):
                    try:
                        c, l = int(v.get("count", 0)), float(v.get("last", 0.0))
                        w, lo = int(v.get("wins", 0)), int(v.get("losses", 0))
                        lt = float(v.get("linger_total", 0.0))
                        ln = int(v.get("linger_n", 0))
                    except (TypeError, ValueError):
                        c, l, w, lo, lt, ln = 0, 0.0, 0, 0, 0.0, 0
                elif isinstance(v, (int, float)):
                    c, l, w, lo, lt, ln = int(v), 0.0, 0, 0, 0.0, 0
                else:
                    continue
                clean[k] = {"count": max(0, c), "last": l,
                            "wins": max(0, w), "losses": max(0, lo),
                            "linger_total": max(0.0, lt), "linger_n": max(0, ln)}
            norm[t] = clean
        base["roast_stats"] = norm

        dl = base.get("daily") if isinstance(base.get("daily"), dict) else {}
        today = date.today().isoformat()
        base["daily"] = {
            "date": today,
            "focus": int(dl.get("focus", 0) or 0),
            "distraction": int(dl.get("distraction", 0) or 0),
            "insults": int(dl.get("insults", 0) or 0),
            "break": int(dl.get("break", 0) or 0),
            "pomodoros": int(dl.get("pomodoros", 0) or 0),
            "broken": int(dl.get("broken", 0) or 0),
        }
        if dl.get("date") != today:
            base["daily"] = fresh_daily()
    except Exception:
        pass
    return base


def save_data(data: dict):
    # Retry loop prevents 'dictionary changed size during iteration'
    for _ in range(3):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return
        except RuntimeError:
            time.sleep(0.1)
        except Exception:
            return


def play_sound(tier: int = 1):
    """Play a sound that escalates with the roast tier."""
    sysname = platform.system()
    try:
        if sysname == "Windows":
            import winsound
            freq = {1: 600, 2: 800, 3: 1000}.get(tier, 600)
            winsound.Beep(freq, 300)
        elif sysname == "Darwin":
            sound = {1: "Pop", 2: "Purr", 3: "Basso"}.get(tier, "Pop")
            subprocess.Popen(["afplay", f"/System/Library/Sounds/{sound}.aiff"])
        elif sysname == "Linux":
            subprocess.Popen(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"])
        else:
            QApplication.beep()
    except Exception:
        QApplication.beep()


def make_app_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(RED))
    p.drawRoundedRect(4, 4, 56, 56, 14, 14)
    f = QFont()
    f.setBold(True)
    f.setPixelSize(26)
    p.setFont(f)
    p.setPen(QColor("#ffffff"))
    p.drawText(pm.rect(), Qt.AlignCenter, "RG")
    p.end()
    return QIcon(pm)


def btn(text: str, variant: str = None, slot=None) -> QPushButton:
    b = QPushButton(text)
    if variant:
        b.setProperty("variant", variant)
    if slot:
        b.clicked.connect(slot)
    b.setCursor(Qt.PointingHandCursor)
    return b


# ------------------------------------------------------------------ monitor

class MonitorThread(QThread):
    roast_ready = Signal(dict)
    phase_changed = Signal(dict)
    praise_ready = Signal(str)

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = data
        self.current_site = None
        self.streak = 0.0
        self.next_roast_at = data["first_roast"]
        self.paused_until = 0.0
        self.popup_open = False
        self.perm_warning = False
        self.fire = None
        self.idle = False
        self.idle_since = 0.0
        self.pom_phase = "off"
        self.pom_len = 0.0
        self.pom_remaining = 0.0
        self.pom_paused = False
        self.recent_offenses = {}
        self._active = True

    def stop(self):
        self._active = False

    def toggle_pause(self):
        self.paused_until = (0 if time.time() < self.paused_until
                             else time.time() + 15 * 60)

    def extend_grace(self, secs: float):
        self.next_roast_at = self.streak + secs

    def reset_timer(self):
        self.next_roast_at = self.data["first_roast"]

    def _fire_linger(self) -> float:
        f = self.fire
        raw = time.time() - f["at"] - f.get("idle_acc", 0.0)
        return min(max(raw, 0.0), MAX_LINGER)

    def _settle_fire(self):
        if not self.fire:
            return
        linger = self._fire_linger()
        record_result(self.data, self.fire["tier"], self.fire["template"], linger)
        if linger <= 10:
            self.praise_ready.emit(self.fire.get("site", "the site"))
        self.fire = None

    def _fall_asleep(self):
        self.idle = True
        self.idle_since = time.time()

    def _wake(self):
        gone = min(time.time() - self.idle_since, MAX_LINGER)
        self.idle = False
        self.idle_since = 0.0
        if self.fire:
            self.fire["idle_acc"] = min(
                self.fire.get("idle_acc", 0.0) + gone, MAX_LINGER)

    def _arm_focus_timer(self):
        self.current_site = None
        self.streak = 0.0
        self.next_roast_at = min(self.data["first_roast"], 45)

    def _enter_break(self, dur: float):
        if self.fire:
            self._settle_fire()
        self.current_site = None
        self.streak = 0.0
        self.next_roast_at = self.data["first_roast"]
        self.pom_phase = "break" if dur <= self.data["pom_break_len"] * 60 + 1 \
            else "long"
        self.pom_len = self.pom_remaining = dur

    def pom_start(self):
        if self.pom_phase != "off" and not self.pom_paused:
            return
        if self.pom_phase == "off":
            dur = self.data["pom_focus_len"] * 60
            self.pom_phase, self.pom_len, self.pom_remaining = "focus", dur, dur
            self._arm_focus_timer()
            self.pom_paused = False
            self.phase_changed.emit({
                "phase": "focus",
                "msg": f"🍅 Focus block started — {self.data['pom_focus_len']} min. "
                       f"Roasts sharpen.{' Strict mode: one banned tab breaks it.' if self.data['pom_strict'] else ''}"})
        elif self.pom_paused:
            self.pom_paused = False
            self.phase_changed.emit({"phase": self.pom_phase, "msg": "Resumed."})

    def pom_skip(self):
        if self.pom_phase == "off":
            return
        self.pom_paused = False
        if self.pom_phase == "focus":
            self._enter_break(self.data["pom_break_len"] * 60)
            msg = "Focus skipped — no 🍅 credit. Take the break anyway."
        else:
            dur = self.data["pom_focus_len"] * 60
            self.pom_phase, self.pom_len, self.pom_remaining = "focus", dur, dur
            self._arm_focus_timer()
            msg = "Break cut short. Back in the arena."
        self.phase_changed.emit({"phase": self.pom_phase, "msg": msg})

    def pom_stop(self):
        if self.pom_phase == "off" and not self.pom_paused:
            return
        if self.fire:
            self._settle_fire()
        self.pom_phase, self.pom_len, self.pom_remaining = "off", 0.0, 0.0
        self.pom_paused = False
        self.streak = 0.0
        self.next_roast_at = self.data["first_roast"]
        self.phase_changed.emit({"phase": "off", "msg": "Session stopped."})

    def _pom_tick(self) -> dict | None:
        if self.pom_phase == "off" or self.pom_paused:
            return None
        self.pom_remaining -= CHECK
        if self.pom_remaining > 0:
            return None

        if self.pom_phase == "focus":
            self.data["daily"]["pomodoros"] += 1
            n = self.data["daily"]["pomodoros"]
            if n % max(2, self.data["pom_long_every"]) == 0:
                dur = self.data["pom_long_len"] * 60
                self._enter_break(dur)
                msg = (f"🍅 Block {n} complete. Long break — "
                       f"{self.data['pom_long_len']} min. You've earned it.")
            else:
                dur = self.data["pom_break_len"] * 60
                self._enter_break(dur)
                msg = (f"🍅 Block {n} complete. "
                       f"{self.data['pom_break_len']} min break — sanctioned "
                       f"slacking. Roasts stand down.")
            if not self.data.get("pom_auto_break", False):
                self.pom_paused = True
        else:
            dur = self.data["pom_focus_len"] * 60
            self.pom_phase, self.pom_len, self.pom_remaining = "focus", dur, dur
            self._arm_focus_timer()
            msg = "Break's over. Back in the arena."
            if not self.data.get("pom_auto_focus", False):
                self.pom_paused = True
        return {"phase": self.pom_phase, "msg": msg, "len": dur}

    def _pom_broken(self, site: str):
        self.data["daily"]["broken"] += 1
        elapsed_min = max(1, int((self.pom_len - self.pom_remaining) // 60))
        if self.fire:
            self._settle_fire()
        text = "💔 FOCUS BROKEN\n\n" + fill(random.choice(FOCUS_BROKEN),
                                            site, elapsed_min)
        self.data["daily"]["insults"] += 1
        self.data["total_insults"] += 1
        self.pom_phase, self.pom_len, self.pom_remaining = "off", 0.0, 0.0
        self.pom_paused = False
        self.current_site, self.streak = None, 0.0
        self.next_roast_at = self.data["first_roast"]
        self.phase_changed.emit({"phase": "off",
                                 "msg": "💔 Focus block broken — banned site "
                                        f"detected ({site})."})
        self.roast_ready.emit({"text": text, "site": site,
                               "streak": elapsed_min * 60, "tier": 3})

    def run(self):
        fails = 0
        while self._active:
            time.sleep(CHECK)
            if time.time() < self.paused_until:
                if self.fire:
                    self._settle_fire()
                self.current_site, self.streak = None, 0.0
                self.idle = False
                continue

            self._rollover()

            # ---- work hours check -----------------------------------------
            if self.data.get("work_hours_enabled"):
                now = datetime.now()
                try:
                    sh, sm = map(int, self.data.get("work_start", "09:00").split(':'))
                    eh, em = map(int, self.data.get("work_end", "17:00").split(':'))
                    start_t = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
                    end_t = now.replace(hour=eh, minute=em, second=0, microsecond=0)
                    if start_t < end_t:
                        is_work_time = start_t <= now < end_t
                    else:
                        is_work_time = now >= start_t or now < end_t
                    if not is_work_time:
                        if self.fire:
                            self._settle_fire()
                        self.current_site = None
                        self.streak = 0.0
                        continue
                except Exception:
                    pass
            # ----------------------------------------------------------------

            idle_for = idle_seconds()
            if self.idle:
                if idle_for >= self.data["idle_after"]:
                    continue
                self._wake()
            elif idle_for >= self.data["idle_after"]:
                self._fall_asleep()
                continue

            tr = self._pom_tick()
            if tr:
                self.phase_changed.emit(tr)

            if self.pom_phase in ("break", "long") and not self.pom_paused:
                self.data["daily"]["break"] += CHECK
                self.current_site, self.streak = None, 0.0
                continue

            title = active_window_title()
            if not title:
                fails += 1
                if fails == 10:
                    self.perm_warning = True
                continue
            fails, self.perm_warning = 0, False

            site = next((s for s in self.data["sites"]
                         if s.lower() in title.lower()), None)

            if site:
                if site != self.current_site:
                    if self.fire:
                        self._settle_fire()
                    self.current_site, self.streak = site, 0.0
                    base = (min(self.data["first_roast"], 45)
                            if self.pom_phase == "focus"
                            else self.data["first_roast"])
                    self.next_roast_at = base
                self.streak += CHECK
                self.data["daily"]["distraction"] += CHECK

                if (self.pom_phase == "focus" and not self.pom_paused
                        and self.data["pom_strict"]
                        and self.streak >= POM_STRICT_GRACE):
                    self._pom_broken(site)
                    continue

                if not self.popup_open and self.streak >= self.next_roast_at:
                    tier = pick_tier(self.streak)
                    roast = self._make_roast(site, self.streak, tier)
                    gaps = ({1: 120, 2: 210, 3: 420} if self.pom_phase == "focus"
                            else {1: 150, 2: 300, 3: 600})
                    self.next_roast_at = self.streak + gaps[tier]
                    self.roast_ready.emit(roast)
            else:
                if self.fire:
                    self._settle_fire()
                self.current_site, self.streak = None, 0.0
                self.data["daily"]["focus"] += CHECK
                if self.pom_phase == "off":
                    self.next_roast_at = self.data["first_roast"]

    def _rollover(self):
        today = date.today().isoformat()
        if self.data["daily"]["date"] != today:
            self.data["daily"] = fresh_daily()

    def _make_roast(self, site, streak, tier):
        mins = max(1, int(streak // 60))
        
        now = time.time()
        last_offense = self.recent_offenses.get(site, 0)
        is_repeat = (now - last_offense) < 600
        self.recent_offenses[site] = now
        
        if is_repeat:
            template = random.choice(REPEAT_OFFENDER + pool_for(tier, self.data))
        else:
            template = random.choice(pool_for(tier, self.data))

        if self.fire:
            self._settle_fire()
        record_fire(self.data, tier, template)
        self.fire = {"template": template, "tier": tier,
                     "at": time.time(), "idle_acc": 0.0, "site": site}
        text = fill(template, site, mins)
        self.data["daily"]["insults"] += 1
        self.data["total_insults"] += 1
        return {"text": text, "site": site, "streak": streak, "tier": tier}


# ------------------------------------------------------------------ roast popup

class RoastDialog(QDialog):
    def __init__(self, roast: dict, hardcore: bool, sound: bool,
                 monitor: MonitorThread, parent=None):
        super().__init__(parent, Qt.Dialog | Qt.WindowStaysOnTopHint
                         | Qt.FramelessWindowHint)
        self.roast = roast
        self.hardcore = hardcore
        self.monitor = monitor
        self.entry = None

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle(APP)

        shell = QFrame(self)
        shell.setObjectName("shell")
        shell.setStyleSheet(
            f"#shell {{ background: {SHELL}; border: 2px solid {RED};"
            f" border-radius: 12px; }}")
        v = QVBoxLayout(shell)
        v.setContentsMargins(26, 18, 26, 18)
        v.setSpacing(8)

        emoji = QLabel(random.choice(["🔥", "👀", "🚨", "💀", "🙃", "🍅"]))
        emoji.setAlignment(Qt.AlignCenter)
        emoji.setStyleSheet("font-size: 30pt;")
        v.addWidget(emoji)

        self.msg = QLabel(roast["text"])
        self.msg.setWordWrap(True)
        self.msg.setAlignment(Qt.AlignCenter)
        self.msg.setStyleSheet("color: #ffe9e9; font-size: 13pt; font-weight: bold;")
        v.addWidget(self.msg)

        lost = QLabel(f"time lost to {roast['site']}: {fmt(roast['streak'])}")
        lost.setAlignment(Qt.AlignCenter)
        lost.setStyleSheet(f"color: {DIM}; font-size: 9pt;")
        v.addWidget(lost)

        if hardcore:
            hint = QLabel("To leave, type:  I will focus now")
            hint.setAlignment(Qt.AlignCenter)
            hint.setStyleSheet(f"color: {YELLOW}; font-size: 10pt;")
            v.addWidget(hint)

            self.entry = QLineEdit()
            self.entry.setPlaceholderText("confess here…")
            self.entry.setAlignment(Qt.AlignCenter)
            self.entry.returnPressed.connect(self.redeem)
            v.addWidget(self.entry)

            v.addWidget(btn("Redeem yourself", "danger", self.redeem))
        else:
            v.addWidget(btn("Fine. Back to work. 😤", "primary", self.dismiss))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(shell)

        if sound:
            play_sound(roast.get("tier", 1))

    def reject(self):
        if self.hardcore:
            self.redeem()
        else:
            self.dismiss()

    def dismiss(self):
        self.monitor.popup_open = False
        self.monitor.extend_grace(240)
        self.done(QDialog.Accepted)

    def redeem(self):
        if self.entry.text().strip().lower() == HARDCORE_PHRASE:
            self.dismiss()
            return
        mins = max(1, int(self.roast["streak"] // 60))
        template = random.choice(pool_for(3, self.monitor.data))
        record_fire(self.monitor.data, 3, template)
        worse = fill(template, self.roast["site"], mins)
        self.msg.setText("Wrong. And now you've made it worse:\n\n" + worse)
        self.entry.clear()
        play_sound(3)
        self.reposition()

    def showEvent(self, e):
        super().showEvent(e)
        if self.entry:
            self.entry.setFocus()
        self.reposition()

    def reposition(self):
        self.adjustSize()
        g = QApplication.primaryScreen().availableGeometry()
        self.move(g.right() - self.width() - 40,
                  g.bottom() - self.height() - 40)


# ------------------------------------------------------------------ pack dialogs

class ImportPackDialog(QDialog):
    def __init__(self, meta: dict, tiers: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import roast pack")
        self.setMinimumWidth(400)
        self.mode = "merge"

        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 12)
        v.setSpacing(8)

        head = QLabel(f"📦 {meta['name']}")
        head.setStyleSheet("font-size: 13pt; font-weight: bold;")
        v.addWidget(head)
        by = QLabel(f"by {meta['author']}")
        by.setStyleSheet(f"color: {DIM};")
        v.addWidget(by)

        lines = []
        for key in ("1", "2", "3"):
            if key in tiers:
                lines.append(f"Tier {key} · {TIER_NAMES[int(key)]}: "
                             f"{len(tiers[key])} roast{'s' if len(tiers[key]) != 1 else ''}")
        box = QLabel("\n".join(lines))
        box.setStyleSheet(f"color: {FG};")
        v.addWidget(box)

        v.addSpacing(4)
        merge = QRadioButton("Merge — add alongside my roasts (duplicates skipped)")
        merge.setChecked(True)
        merge.toggled.connect(lambda on: on and setattr(self, "mode", "merge"))
        replace = QRadioButton("Replace — wipe my customs in the pack's tiers first")
        replace.toggled.connect(lambda on: on and setattr(self, "mode", "replace"))
        v.addWidget(merge)
        v.addWidget(replace)
        note = QLabel("Replace only affects tiers included in the pack.")
        note.setStyleSheet(f"color: {DIM}; font-size: 8pt;")
        v.addWidget(note)

        v.addSpacing(4)
        v.addWidget(btn("Import", "primary", self.accept))
        v.addWidget(btn("Cancel", "ghost", self.reject))


class ExportDialog(QDialog):
    def __init__(self, workshop, parent=None):
        super().__init__(parent)
        self.workshop = workshop
        self.setWindowTitle("Export roast pack")
        self.setMinimumWidth(400)
        self.result_name = ""
        self.result_author = ""
        self.result_tiers = (1, 2, 3)

        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 12)
        v.setSpacing(8)

        h = QLabel("⬆ Export your custom roasts")
        h.setStyleSheet("font-size: 13pt; font-weight: bold;")
        v.addWidget(h)

        v.addWidget(QLabel("Pack name"))
        self.name = QLineEdit("My custom roasts")
        v.addWidget(self.name)

        v.addWidget(QLabel("Author (shown to whoever imports it)"))
        self.author = QLineEdit("anonymous slacker")
        v.addWidget(self.author)

        v.addSpacing(4)
        self.rb_all = QRadioButton("All tiers")
        self.rb_all.setChecked(True)
        self.rb_one = QRadioButton(f"Current tier only (Tier {workshop.tier} · "
                                   f"{TIER_NAMES[workshop.tier]})")
        v.addWidget(self.rb_all)
        v.addWidget(self.rb_one)
        note = QLabel("Only your ★ custom roasts are exported — built-ins "
                      "come with the app. Performance stats stay private.")
        note.setStyleSheet(f"color: {DIM}; font-size: 8pt;")
        note.setWordWrap(True)
        v.addWidget(note)

        v.addSpacing(4)
        v.addWidget(btn("Choose file & export", "primary", self.collect))
        v.addWidget(btn("Cancel", "ghost", self.reject))

    def collect(self):
        self.result_name = self.name.text().strip() or "Untitled pack"
        self.result_author = self.author.text().strip() or "unknown"
        self.result_tiers = ((1, 2, 3) if self.rb_all.isChecked()
                             else (self.workshop.tier,))
        self.accept()


# ------------------------------------------------------------------ roast stats

class RoastStatsDialog(QDialog):
    SORTS = [("🔥 by fires", "fires"), ("✅ by win rate", "win"),
             ("⏱ by fastest exit", "linger")]

    def __init__(self, main_win):
        super().__init__(main_win)
        self.main = main_win
        self.setWindowTitle("Roast stats — leaderboard of shame")
        self.resize(660, 720)
        self.setMinimumSize(540, 500)
        self.filter = 0
        self.sort_mode = "fires"

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)
        root.setSpacing(8)

        title = QLabel("📊 ROAST STATS")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {YELLOW}; font-size: 16pt; font-weight: bold;")
        sub = QLabel("which roasts actually get you off the site — a win means "
                     f"you left within {WIN_SECS}s of the roast (idle excluded)")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color: {DIM}; font-size: 9pt;")
        root.addWidget(title)
        root.addWidget(sub)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(f"color: {FG}; font-size: 10pt;")
        root.addWidget(self.summary)

        tiers = QHBoxLayout()
        for val, lbl in [(0, "All tiers"), (1, "T1 · Mild"),
                         (2, "T2 · Mean"), (3, "T3 · Brutal")]:
            rb = QRadioButton(lbl)
            rb.setChecked(val == 0)
            rb.toggled.connect(lambda on, v=val: on and self.set_filter(v))
            tiers.addWidget(rb)
        root.addLayout(tiers)

        sorts = QHBoxLayout()
        for lbl, mode in self.SORTS:
            rb = QRadioButton(lbl)
            rb.setChecked(mode == self.sort_mode)
            rb.toggled.connect(lambda on, m=mode: on and self.set_sort(m))
            sorts.addWidget(rb)
        root.addLayout(sorts)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        self.rows_v = QVBoxLayout(host)
        self.rows_v.setContentsMargins(0, 0, 0, 0)
        self.rows_v.setSpacing(6)
        self.area.setWidget(host)
        root.addWidget(self.area, 1)

        legend = QLabel(f"win = left the banned site within {WIN_SECS}s · "
                        "avg = average time still wasted after it fired · "
                        "— = not enough data yet")
        legend.setStyleSheet(f"color: {DIM}; font-size: 8pt;")
        legend.setWordWrap(True)
        root.addWidget(legend)

        bottom = QHBoxLayout()
        bottom.addWidget(btn("Reset stats", "danger", self.reset_stats))
        bottom.addWidget(btn("Export CSV", "ghost", self.export_csv))
        bottom.addStretch(1)
        bottom.addWidget(btn("Close", "ghost", self.accept))
        root.addLayout(bottom)

        self.rebuild()

    def set_filter(self, tier: int):
        self.filter = tier
        self.rebuild()

    def set_sort(self, mode: str):
        self.sort_mode = mode
        self.rebuild()

    def collect(self):
        stats = self.main.data.get("roast_stats", {})
        tiers = range(1, 4) if self.filter == 0 else (self.filter,)
        out = []
        for t in tiers:
            customs = set(self.main.data["custom_insults"].get(str(t), []))
            ts = stats.get(str(t), {})
            for text in set(BUILTIN[t]) | customs:
                e = ts.get(text, {})
                wr, resolves = win_rate(e)
                out.append({
                    "tier": t, "text": text,
                    "count": int(e.get("count", 0)),
                    "last": float(e.get("last", 0.0)),
                    "is_custom": text in customs,
                    "wr": wr, "resolves": resolves,
                    "avg": avg_linger(e),
                    "wins": int(e.get("wins", 0)),
                    "losses": int(e.get("losses", 0)),
                })
        out.sort(key=self._sort_key)
        return out

    def _sort_key(self, r):
        if self.sort_mode == "win":
            return (-(r["wr"] if r["wr"] is not None else -1.0),
                    -r["count"], r["tier"], r["text"].lower())
        if self.sort_mode == "linger":
            return (r["avg"] if r["avg"] is not None else 1e9,
                    -r["count"], r["tier"], r["text"].lower())
        return (-r["count"], r["tier"], r["text"].lower())

    def rebuild(self):
        while self.rows_v.count():
            item = self.rows_v.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = self.collect()
        total = sum(r["count"] for r in rows)
        mine = sum(r["count"] for r in rows if r["is_custom"])
        resolves = sum(r["resolves"] for r in rows)
        wins = 0
        for r in rows:
            e = self.main.data.get("roast_stats", {}) \
                .get(str(r["tier"]), {}).get(r["text"], {})
            wins += e.get("wins", 0)
        overall = (wins / resolves * 100.0) if resolves else None

        s = (f"All-time fires: {total}   ·   yours: {mine}   ·   "
             f"built-ins: {total - mine}")
        if overall is not None:
            s += f"\nRoasts that made you leave: {overall:.0f}% " \
                 f"({resolves} measured)"
        top = next((r for r in rows if r["is_custom"] and r["count"] > 0), None)
        if top:
            s += f"\nMost fired 🏆 ({top['count']}×) “{top['text']}”"

        closer = self._best(rows, key=lambda r: r["wr"], at_least=2)
        if closer:
            s += (f"\nBest closer 🥇 {closer['wr']:.0f}% win · "
                  f"{closer['resolves']} tries · “{closer['text']}”")
        slowest = self._best(rows, key=lambda r: r["avg"], at_least=2)
        if slowest and slowest["avg"] is not None:
            s += (f"\nLeast effective 🐌 {secs_short(slowest['avg'])} avg before "
                  f"you left · “{slowest['text']}”")
        if not total:
            s = ("No roasts have fired yet. Open a banned site and take one "
                 "for the data. 📉")
        self.summary.setText(s)

        max_count = max((r["count"] for r in rows), default=0) or 1
        for i, r in enumerate(rows):
            self.rows_v.addWidget(self._row(i, r, max_count))
        self.rows_v.addStretch(1)

    @staticmethod
    def _best(rows, key, at_least):
        cands = [r for r in rows if r["resolves"] >= at_least
                 and key(r) is not None]
        return max(cands, key=key) if cands else None

    def _wr_color(self, wr):
        if wr is None:
            return DIM
        if wr >= 60:
            return GREEN
        if wr >= 40:
            return YELLOW
        return RED

    def _row(self, rank, r, max_count):
        row = QFrame()
        row.setObjectName("srow")
        row.setStyleSheet("#srow { background: #1a1a26; border-radius: 8px; }")
        v = QVBoxLayout(row)
        v.setContentsMargins(10, 7, 10, 8)
        v.setSpacing(3)

        h = QHBoxLayout()
        h.setSpacing(6)
        medal = QLabel("🏆" if (rank == 0 and r["count"] > 0
                                and self.sort_mode == "fires") else "")
        medal.setFixedWidth(18)
        medal.setStyleSheet("font-size: 11pt;")
        h.addWidget(medal)

        star = QLabel("★" if r["is_custom"] else "·")
        star.setFixedWidth(14)
        star.setStyleSheet(
            f"color: {ACCENT if r['is_custom'] else DIM}; font-weight: bold;")
        h.addWidget(star)

        cnt = QLabel(f"{r['count']}×")
        cnt.setFixedWidth(44)
        cnt.setStyleSheet(f"color: {GREEN if r['count'] else DIM}; font-weight: bold;")
        h.addWidget(cnt)

        if r["wr"] is not None:
            wr_lbl = QLabel(f"✅ {r['wr']:.0f}%")
            wr_lbl.setToolTip(f"{r['resolves']} measured (wins within "
                              f"{WIN_SECS}s of the roast)")
            wr_lbl.setStyleSheet(
                f"color: {self._wr_color(r['wr'])}; font-weight: bold;")
        else:
            wr_lbl = QLabel("✅ —")
            wr_lbl.setStyleSheet(f"color: {DIM};")
        h.addWidget(wr_lbl)

        if r["avg"] is not None:
            avg_lbl = QLabel(f"⏱ avg {secs_short(r['avg'])}")
            avg_lbl.setStyleSheet(f"color: {DIM}; font-size: 9pt;")
            h.addWidget(avg_lbl)

        tag = QLabel(f"T{r['tier']}")
        tag.setStyleSheet(f"color: {DIM}; font-size: 8pt;")
        h.addWidget(tag)
        h.addStretch(1)

        when = QLabel(ago(r["last"]))
        when.setStyleSheet(f"color: {DIM}; font-size: 8pt; font-style: italic;")
        h.addWidget(when)
        v.addLayout(h)

        txt = QLabel(r["text"])
        txt.setWordWrap(True)
        txt.setStyleSheet(f"color: {FG if r['count'] else DIM}; font-size: 9pt;")
        v.addWidget(txt)

        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setRange(0, max_count)
        bar.setValue(r["count"])
        bar.setFixedHeight(6)
        if rank == 0 and r["count"] > 0 and self.sort_mode == "fires":
            color = GREEN
        elif r["count"] == 0:
            color = "#2a2a38"
        else:
            color = ACCENT if r["is_custom"] else "#4a4a66"
        bar.setStyleSheet(
            "QProgressBar { background: #2a2a38; border: none; border-radius: 3px; }"
            f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}")
        v.addWidget(bar)
        return row

    def reset_stats(self):
        if QMessageBox.question(
                self, APP,
                "Reset all roast stats (fires, win rates, exit times)?\n"
                "Your roasts stay — only the stats are wiped.") == QMessageBox.Yes:
            self.main.data["roast_stats"] = {"1": {}, "2": {}, "3": {}}
            self.main.save_data()
            w = self.main.workshop
            if w is not None and w.isVisible():
                w.refresh()
            self.rebuild()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Roast Stats", "roastguard_stats.csv",
            "CSV Files (*.csv);;All Files (*.*)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Tier", "Roast Text", "Custom?", "Fires", "Wins", 
                            "Losses", "Win Rate (%)", "Avg Linger (s)", "Last Fired"])
                for r in self.collect():
                    avg = f"{r['avg']:.1f}" if r['avg'] is not None else "N/A"
                    wr = f"{r['wr']:.1f}" if r['wr'] is not None else "N/A"
                    w.writerow([r['tier'], r['text'], "Yes" if r['is_custom'] else "No",
                                r['count'], r['wins'], r['losses'], wr, avg, ago(r['last'])])
            QMessageBox.information(self, APP, f"Exported stats to:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, APP, f"Failed to export CSV:\n{e}")


# ------------------------------------------------------------------ insult workshop

class InsultWorkshop(QDialog):
    def __init__(self, main_win):
        super().__init__(main_win)
        self.main = main_win
        self.setWindowTitle("Insult workshop — write your own medicine")
        self.resize(640, 800)
        self.setMinimumSize(560, 660)
        self.setAcceptDrops(True)
        self.tier = 1
        self.edit_row = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)
        root.setSpacing(8)

        title = QLabel("✍️ INSULT WORKSHOP")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {ACCENT}; font-size: 16pt; font-weight: bold;")
        sub = QLabel("Write roasts for each tier. Use {site} for the caught site "
                     "and {mins} for minutes wasted.")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color: {DIM}; font-size: 9pt;")
        root.addWidget(title)
        root.addWidget(sub)

        tiers = QHBoxLayout()
        for val, lbl in [(1, "Tier 1 · Mild"), (2, "Tier 2 · Mean"),
                         (3, "Tier 3 · Brutal")]:
            rb = QRadioButton(lbl)
            rb.setChecked(val == 1)
            rb.toggled.connect(lambda on, v=val: on and self.set_tier(v))
            tiers.addWidget(rb)
        root.addLayout(tiers)

        self.listw = QListWidget()
        self.listw.itemDoubleClicked.connect(self.load_for_edit)
        root.addWidget(self.listw, 1)

        self.pool_lbl = QLabel("")
        self.pool_lbl.setStyleSheet(f"color: {DIM}; font-size: 8pt;")
        root.addWidget(self.pool_lbl)

        self.editor = QTextEdit()
        self.editor.setFixedHeight(76)
        self.editor.setPlaceholderText("Write a roast… e.g.  "
                                       "{mins} minutes of {site}? Bold choice.")
        root.addWidget(self.editor)

        ph = QHBoxLayout()
        ph.addWidget(QLabel("insert at cursor:"))
        for token in ("{site}", "{mins}"):
            b = btn("+" + token, None,
                    lambda _=False, t=token: self.editor.insertPlainText(t))
            b.setStyleSheet(f"color: {ACCENT}; font-weight: bold; padding: 4px 8px;")
            ph.addWidget(b)
        ph.addStretch(1)
        root.addLayout(ph)

        row = QHBoxLayout()
        row.addWidget(btn("Add roast", "primary", self.add_insult))
        row.addWidget(btn("Update selected ★", "accent", self.update_insult))
        row.addWidget(btn("Remove ★", "danger", self.remove_insult))
        row.addWidget(btn("Preview", None, self.preview))
        root.addLayout(row)

        grow = QHBoxLayout()
        grow.addWidget(btn("Reset this tier to built-ins only", "ghost",
                           self.reset_tier))
        grow.addStretch(1)
        grow.addWidget(btn("📊 Roast stats", "accent", self.open_stats))
        root.addLayout(grow)

        share = QLabel("🔗 share the pain — roast packs")
        share.setStyleSheet(f"color: {DIM}; font-size: 9pt; font-weight: bold;")
        root.addWidget(share)
        srow = QHBoxLayout()
        srow.addWidget(btn("⬇ Import pack…", "accent", self.import_pack))
        srow.addWidget(btn("⬆ Export…", "accent", self.export_pack))
        srow.addWidget(btn("Copy pack", "ghost", self.copy_pack))
        srow.addWidget(btn("Paste pack", "ghost", self.paste_pack))
        root.addLayout(srow)
        dnd = QLabel("tip: you can also drag a .json pack file onto this window, "
                     "or copy/paste pack JSON straight from a chat")
        dnd.setStyleSheet(f"color: {DIM}; font-size: 8pt;")
        root.addWidget(dnd)

        self.flash_lbl = QLabel("")
        self.flash_lbl.setWordWrap(True)
        root.addWidget(self.flash_lbl)

        self.refresh()

    def customs(self) -> list:
        return self.main.data["custom_insults"].setdefault(str(self.tier), [])

    def fire_counts(self) -> dict:
        return self.main.data.get("roast_stats", {}).get(str(self.tier), {})

    @staticmethod
    def _inline_tag(e: dict) -> str:
        c = e.get("count", 0)
        wr, _n = win_rate(e)
        if wr is None:
            return f"{c}×"
        return f"{c}× · {wr:.0f}%"

    def set_tier(self, tier: int):
        self.tier = tier
        self.refresh()

    def refresh(self):
        customs, builtin = self.customs(), BUILTIN[self.tier]
        counts = self.fire_counts()

        self.listw.clear()
        for t in customs:
            self.listw.addItem(f"★ {self._inline_tag(counts.get(t, {}))}  {t}")
        for t in builtin:
            self.listw.addItem(f"· {self._inline_tag(counts.get(t, {}))}  {t}")
        self.pool_lbl.setText(
            f"Tier {self.tier}: {len(customs)} of yours + {len(builtin)} built-in. "
            f"N× = fires · % = win rate (left within {WIN_SECS}s). "
            f"★ = yours (double-click to edit).")
        self.edit_row = None
        self.editor.clear()

    def flash(self, msg, color=YELLOW):
        self.flash_lbl.setText(msg)
        self.flash_lbl.setStyleSheet(f"color: {color};")
        QTimer.singleShot(8000, lambda: self.flash_lbl.setText(""))

    def load_for_edit(self, item):
        row = self.listw.row(item)
        customs = self.customs()
        if row < len(customs):
            self.edit_row = row
            self.editor.setPlainText(customs[row])
            self.editor.setFocus()
            self.flash("Editing your roast — press “Update selected ★” to save.")
        else:
            self.flash("Built-ins can't be edited — double-click a ★ roast (yours).",
                       DIM)

    def add_insult(self):
        text = self.editor.toPlainText().strip()
        if not text:
            self.flash("Write a roast first. The site isn't going to insult itself.",
                       RED)
            return
        if len(text) > MAX_ROAST_LEN:
            self.flash(f"Too long — keep it under {MAX_ROAST_LEN} characters so "
                       f"the popup stays punchy.", RED)
            return
        if text in self.customs():
            self.flash("You already added that exact roast to this tier.", RED)
            return
        self.customs().append(text)
        self.main.save_data()
        self.refresh()
        self.flash(f"Roast added to tier {self.tier} — it fires in the wild "
                   f"immediately.", GREEN)

    def update_insult(self):
        if self.edit_row is None:
            self.flash("Double-click one of your ★ roasts first, edit, then Update.",
                       RED)
            return
        text = self.editor.toPlainText().strip()
        if not text:
            self.flash("Nothing to save — the box is empty.", RED)
            return
        self.customs()[self.edit_row] = text
        self.main.save_data()
        self.refresh()
        self.flash("Roast updated. (Its stats restart — it's a new roast now.)",
                   GREEN)

    def remove_insult(self):
        row = self.listw.currentRow()
        if row < 0:
            self.flash("Select one of your ★ roasts to remove.", RED)
            return
        customs = self.customs()
        if row >= len(customs):
            self.flash("Built-in roasts can't be removed — only your ★ ones.", RED)
            return
        del customs[row]
        self.main.save_data()
        self.refresh()
        self.flash("Roast removed.", GREEN)

    def preview(self):
        text = self.editor.toPlainText().strip()
        if not text:
            self.flash("Type (or double-click-load) a roast first.", RED)
            return
        self.flash("Preview → " + fill(text, "youtube", 7), ACCENT)

    def reset_tier(self):
        if QMessageBox.question(
                self, APP,
                f"Delete all your custom Tier {self.tier} roasts?\nBuilt-ins stay."
                ) == QMessageBox.Yes:
            self.main.data["custom_insults"][str(self.tier)] = []
            self.main.save_data()
            self.refresh()
            self.flash("Tier reset to built-ins only.", YELLOW)

    def open_stats(self):
        RoastStatsDialog(self.main).exec()
        self.refresh()

    def import_pack(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import roast pack", "",
            "Roast packs (*.json);;All files (*.*)")
        if path:
            self.import_from_file(path)

    def import_from_file(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except OSError as e:
            self.flash(f"Couldn't read that file: {e}", RED)
            return
        except json.JSONDecodeError:
            self.flash("That file isn't valid JSON. Even our roasts are more "
                       "structured than that.", RED)
            return
        self.offer_import(raw)

    def offer_import(self, raw):
        try:
            meta, tiers, skipped = validate_pack(raw)
        except ValueError as e:
            self.flash(f"Import failed: {e}", RED)
            return
        dlg = ImportPackDialog(meta, tiers, self)
        if dlg.exec() != QDialog.Accepted:
            return
        added = self.apply_pack(tiers, dlg.mode)
        msg = (f"Imported {added} roast{'s' if added != 1 else ''} from "
               f"“{meta['name']}” — armed and operational.")
        if skipped:
            msg += f" ({skipped} skipped: empty, too long, or already built-in.)"
        self.flash(msg, GREEN)

    def apply_pack(self, tiers: dict, mode: str) -> int:
        added = 0
        for key, roasts in tiers.items():
            store = self.main.data["custom_insults"].setdefault(key, [])
            if mode == "replace":
                store.clear()
            for r in roasts:
                if r not in store:
                    store.append(r)
                    added += 1
        self.main.save_data()
        self.refresh()
        return added

    def export_pack(self):
        dlg = ExportDialog(self, self)
        if dlg.exec() != QDialog.Accepted:
            return
        tiers = dlg.result_tiers
        roasts = [r for t in tiers
                  for r in self.main.data["custom_insults"].get(str(t), [])]
        if not roasts:
            self.flash("Nothing to export — that scope has no custom roasts. "
                       "Write some first!", RED)
            return
        default = ("roastguard_pack.json" if len(tiers) == 3
                   else f"roastguard_pack_tier{tiers[0]}.json")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export roast pack", default,
            "Roast packs (*.json);;All files (*.*)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        pack = make_pack(self.main.data, tiers, dlg.result_name, dlg.result_author)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(pack, f, indent=2, ensure_ascii=False)
        except OSError as e:
            self.flash(f"Couldn't write the file: {e}", RED)
            return
        self.flash(f"Exported {len(roasts)} roast{'s' if len(roasts) != 1 else ''} "
                   f"→ {os.path.basename(path)}. Go ruin someone else's focus.",
                   GREEN)

    def copy_pack(self):
        total = sum(len(v) for v in self.main.data["custom_insults"].values())
        if not total:
            self.flash("Nothing to copy — write some roasts first.", RED)
            return
        QApplication.clipboard().setText(
            json.dumps(make_pack(self.main.data), indent=2, ensure_ascii=False))
        self.flash(f"Copied all {total} custom roasts as a pack — paste it into "
                   f"any chat to share.", GREEN)

    def paste_pack(self):
        text = QApplication.clipboard().text().strip()
        if not text:
            self.flash("Clipboard is empty.", RED)
            return
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            self.flash("Clipboard isn't valid JSON — copy a roast pack first.",
                       RED)
            return
        self.offer_import(raw)

    def dragEnterEvent(self, e):
        urls = e.mimeData().urls()
        if any(u.toLocalFile().lower().endswith(".json") for u in urls):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            path = u.toLocalFile()
            if path.lower().endswith(".json"):
                self.import_from_file(path)
                break


# ------------------------------------------------------------------ settings

class SettingsDialog(QDialog):
    def __init__(self, main_win):
        super().__init__(main_win)
        self.main = main_win
        self.setWindowTitle("RoastGuard settings")
        self.resize(460, 860)
        self.setMinimumSize(440, 740)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)
        root.setSpacing(8)

        # ---- BANNED SITES (enhanced) ------------------------------------
        h = QLabel("Banned sites")
        h.setStyleSheet("font-size: 13pt; font-weight: bold;")
        root.addWidget(h)

        self.sites_count_lbl = QLabel("")
        self.sites_count_lbl.setStyleSheet(f"color: {DIM}; font-size: 9pt;")
        root.addWidget(self.sites_count_lbl)

        sub = QLabel("Matched against your browser tab / window titles. "
                     "Short keywords work best (e.g. 'youtube' not "
                     "'https://www.youtube.com').")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {DIM}; font-size: 9pt;")
        root.addWidget(sub)

        frow = QHBoxLayout()
        self.filter_entry = QLineEdit()
        self.filter_entry.setPlaceholderText("🔍 filter sites…")
        self.filter_entry.textChanged.connect(self.apply_filter)
        frow.addWidget(self.filter_entry, 1)
        frow.addWidget(btn("Clear", "ghost", lambda: self.filter_entry.clear()))
        root.addLayout(frow)

        self.listw = QListWidget()
        self.listw.setSelectionMode(QListWidget.ExtendedSelection)
        for s in self.main.data["sites"]:
            self.listw.addItem(s)
        root.addWidget(self.listw, 1)

        addrow = QHBoxLayout()
        self.site_entry = QLineEdit()
        self.site_entry.setPlaceholderText("add a site, e.g.  netflix")
        self.site_entry.returnPressed.connect(self.add_site)
        addrow.addWidget(self.site_entry, 1)
        addrow.addWidget(btn("Add", "accent", self.add_site))
        root.addLayout(addrow)

        currow = QHBoxLayout()
        currow.addWidget(btn("🎯 Ban current window", "accent", self.ban_current))
        currow.addWidget(btn("✏️ Edit selected", None, self.edit_site))
        root.addLayout(currow)

        brow = QHBoxLayout()
        brow.addWidget(btn("📋 Paste bulk", "ghost", self.paste_bulk))
        brow.addWidget(btn("📤 Copy all", "ghost", self.copy_all))
        brow.addWidget(btn("Remove selected", "danger", self.remove_site))
        root.addLayout(brow)

        rsrow = QHBoxLayout()
        rsrow.addWidget(btn("🗑 Clear all", "danger", self.clear_all))
        rsrow.addWidget(btn("↩ Restore defaults", "ghost", self.restore_defaults))
        root.addLayout(rsrow)

        self.update_sites_count()

        # ---- UI Options -------------------------------------------------
        uo = QLabel("Roast Behavior")
        uo.setStyleSheet("font-size: 13pt; font-weight: bold;")
        root.addWidget(uo)

        self.hardcore = QCheckBox("Hardcore mode (must type to dismiss roasts)")
        self.hardcore.setChecked(self.main.data["hardcore"])
        self.sound = QCheckBox("Play a sound with each roast")
        self.sound.setChecked(self.main.data["sound"])
        root.addWidget(self.hardcore)
        root.addWidget(self.sound)

        drow = QHBoxLayout()
        drow.addWidget(QLabel("First roast after (seconds):"))
        self.delay = QSpinBox()
        self.delay.setRange(10, 300)
        self.delay.setSingleStep(5)
        self.delay.setValue(int(self.main.data["first_roast"]))
        drow.addWidget(self.delay)
        drow.addStretch(1)
        root.addLayout(drow)

        irow = QHBoxLayout()
        irow.addWidget(QLabel("Mark me idle after (minutes):"))
        self.idle_min = QSpinBox()
        self.idle_min.setRange(2, 20)
        self.idle_min.setValue(max(1, int(self.main.data["idle_after"]) // 60))
        self.idle_min.setToolTip("No keyboard/mouse for this long → clocks freeze.")
        irow.addWidget(self.idle_min)
        irow.addStretch(1)
        root.addLayout(irow)

        uib = QLabel("UI Behavior")
        uib.setStyleSheet("font-size: 13pt; font-weight: bold;")
        root.addWidget(uib)
        self.force_focus = QCheckBox("Force roast window to front (steal focus)")
        self.force_focus.setChecked(self.main.data.get("force_focus", True))
        root.addWidget(self.force_focus)

        # ---- pomodoro ---------------------------------------------------
        ph = QLabel("🍅 Pomodoro")
        ph.setStyleSheet("font-size: 13pt; font-weight: bold;")
        root.addWidget(ph)

        prow = QHBoxLayout()
        prow.addWidget(QLabel("Focus"))
        self.p_focus = QSpinBox()
        self.p_focus.setRange(5, 90)
        self.p_focus.setValue(int(self.main.data["pom_focus_len"]))
        self.p_focus.setSuffix(" min")
        prow.addWidget(self.p_focus)
        prow.addWidget(QLabel("Break"))
        self.p_break = QSpinBox()
        self.p_break.setRange(1, 30)
        self.p_break.setValue(int(self.main.data["pom_break_len"]))
        self.p_break.setSuffix(" min")
        prow.addWidget(self.p_break)
        root.addLayout(prow)

        lrow = QHBoxLayout()
        lrow.addWidget(QLabel("Long break"))
        self.p_long = QSpinBox()
        self.p_long.setRange(5, 45)
        self.p_long.setValue(int(self.main.data["pom_long_len"]))
        self.p_long.setSuffix(" min")
        lrow.addWidget(self.p_long)
        lrow.addWidget(QLabel("after"))
        self.p_every = QSpinBox()
        self.p_every.setRange(2, 8)
        self.p_every.setValue(int(self.main.data["pom_long_every"]))
        self.p_every.setSuffix(" blocks")
        lrow.addWidget(self.p_every)
        lrow.addStretch(1)
        root.addLayout(lrow)

        self.p_strict = QCheckBox("Strict — a banned site breaks the focus block")
        self.p_strict.setChecked(bool(self.main.data["pom_strict"]))
        root.addWidget(self.p_strict)
        
        self.p_auto_break = QCheckBox("Auto-start breaks after focus ends")
        self.p_auto_break.setChecked(bool(self.main.data.get("pom_auto_break", False)))
        root.addWidget(self.p_auto_break)
        
        self.p_auto_focus = QCheckBox("Auto-start next focus after break ends")
        self.p_auto_focus.setChecked(bool(self.main.data.get("pom_auto_focus", False)))
        root.addWidget(self.p_auto_focus)

        pnote = QLabel("During focus: first roast after ~45s, follow-ups faster. "
                       "During breaks: roasts fully off, time counts as sanctioned "
                       "break — not slacking. Pause/idle freeze the countdown.")
        pnote.setStyleSheet(f"color: {DIM}; font-size: 8pt;")
        pnote.setWordWrap(True)
        root.addWidget(pnote)

        # ---- work hours -------------------------------------------------
        wh = QLabel("Work Hours")
        wh.setStyleSheet("font-size: 13pt; font-weight: bold;")
        root.addWidget(wh)

        self.work_hours = QCheckBox("Only monitor during work hours")
        self.work_hours.setChecked(self.main.data.get("work_hours_enabled", False))
        root.addWidget(self.work_hours)

        wh_row = QHBoxLayout()
        wh_row.addWidget(QLabel("Start:"))
        self.wh_start = QLineEdit(self.main.data.get("work_start", "09:00"))
        self.wh_start.setInputMask("00:00;_")
        wh_row.addWidget(self.wh_start)
        wh_row.addWidget(QLabel("End:"))
        self.wh_end = QLineEdit(self.main.data.get("work_end", "17:00"))
        self.wh_end.setInputMask("00:00;_")
        wh_row.addWidget(self.wh_end)
        root.addLayout(wh_row)

        root.addStretch(1)
        root.addWidget(btn("Save", "primary", self.save))
        root.addWidget(btn("✍️ Open insult workshop", "ghost",
                           self.main.open_workshop))

    # ---- banned-sites management --------------------------------------

    def update_sites_count(self):
        n = len(self.main.data["sites"])
        self.sites_count_lbl.setText(
            f"{n} site{'s' if n != 1 else ''} banned")

    def apply_filter(self):
        needle = self.filter_entry.text().strip().lower()
        for i in range(self.listw.count()):
            item = self.listw.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def add_site(self, site: str = None):
        if site is None:
            s = self.site_entry.text().strip().lower()
        else:
            s = site.strip().lower()
        if not s:
            return
        if s in self.main.data["sites"]:
            self.site_entry.clear()
            return
        self.main.data["sites"].append(s)
        self.listw.addItem(s)
        self.site_entry.clear()
        self.update_sites_count()

    def ban_current(self):
        title = active_window_title()
        if not title:
            QMessageBox.information(self, APP,
                "Couldn't read the current window title.\n"
                "macOS: grant Accessibility. Linux: install xdotool.")
            return
        suggested = suggest_site_from_title(title)
        if not suggested:
            QMessageBox.information(self, APP,
                f"Couldn't auto-detect a site from:\n\n"
                f"  “{title[:80]}”\n\n"
                "Type the keyword manually in the box above.")
            return
        if suggested in self.main.data["sites"]:
            QMessageBox.information(self, APP,
                f"“{suggested}” is already banned.")
            return
        reply = QMessageBox.question(
            self, APP,
            f"Detected current window:\n\n  “{title[:80]}”\n\n"
            f"Add “{suggested}” to your banned sites?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            self.add_site(suggested)

    def edit_site(self):
        item = self.listw.currentItem()
        if not item:
            QMessageBox.information(self, APP, "Select a site to edit first.")
            return
        old = item.text()
        new, ok = QInputDialog.getText(
            self, "Edit site", "Edit banned keyword:", text=old)
        if not (ok and new.strip()):
            return
        new = new.strip().lower()
        if new == old:
            return
        if new in self.main.data["sites"]:
            QMessageBox.warning(self, APP, f"“{new}” is already in the list.")
            return
        idx = self.listw.currentRow()
        self.main.data["sites"][idx] = new
        item.setText(new)

    def remove_site(self):
        removed = 0
        for item in self.listw.selectedItems():
            self.main.data["sites"].remove(item.text())
            self.listw.takeItem(self.listw.row(item))
            removed += 1
        if removed:
            self.update_sites_count()

    def clear_all(self):
        if not self.main.data["sites"]:
            return
        if QMessageBox.question(
                self, APP,
                f"Remove all {len(self.main.data['sites'])} banned sites?\n"
                "You'll need to re-add them manually afterwards."
                ) == QMessageBox.Yes:
            self.main.data["sites"].clear()
            self.listw.clear()
            self.update_sites_count()

    def restore_defaults(self):
        if QMessageBox.question(
                self, APP,
                "Restore the default banned-sites list?\n"
                "Your custom additions will be lost."
                ) == QMessageBox.Yes:
            self.main.data["sites"] = list(DEFAULT_SITES)
            self.listw.clear()
            for s in DEFAULT_SITES:
                self.listw.addItem(s)
            self.update_sites_count()

    def paste_bulk(self):
        text, ok = QInputDialog.getMultiLineText(
            self, "Paste sites",
            "Paste sites below (one per line, or comma/space separated):",
            "")
        if not (ok and text.strip()):
            return
        parts = re.split(r'[\n,;\s]+', text.lower())
        added = 0
        for p in parts:
            p = p.strip()
            if p and p not in self.main.data["sites"]:
                self.main.data["sites"].append(p)
                self.listw.addItem(p)
                added += 1
        self.update_sites_count()
        QMessageBox.information(
            self, APP,
            f"Added {added} new site{'s' if added != 1 else ''}. "
            f"{len(self.main.data['sites'])} total.")

    def copy_all(self):
        if not self.main.data["sites"]:
            QMessageBox.information(self, APP, "No sites to copy.")
            return
        QApplication.clipboard().setText("\n".join(self.main.data["sites"]))
        QMessageBox.information(
            self, APP,
            f"Copied {len(self.main.data['sites'])} sites to clipboard.")

    def save(self):
        self.main.data["hardcore"] = self.hardcore.isChecked()
        self.main.data["sound"] = self.sound.isChecked()
        self.main.data["first_roast"] = self.delay.value()
        self.main.data["idle_after"] = self.idle_min.value() * 60
        self.main.data["pom_focus_len"] = self.p_focus.value()
        self.main.data["pom_break_len"] = self.p_break.value()
        self.main.data["pom_long_len"] = self.p_long.value()
        self.main.data["pom_long_every"] = self.p_every.value()
        self.main.data["pom_strict"] = self.p_strict.isChecked()
        self.main.data["pom_auto_break"] = self.p_auto_break.isChecked()
        self.main.data["pom_auto_focus"] = self.p_auto_focus.isChecked()
        self.main.data["work_hours_enabled"] = self.work_hours.isChecked()
        self.main.data["work_start"] = self.wh_start.text() or "09:00"
        self.main.data["work_end"] = self.wh_end.text() or "17:00"
        self.main.data["force_focus"] = self.force_focus.isChecked()
        self.main.monitor.reset_timer()
        self.main.save_data()
        self.accept()


# ------------------------------------------------------------------ main window

class MainWindow(QMainWindow):
    def __init__(self, icon: QIcon):
        super().__init__()
        self.icon = icon
        self.data = load_data()
        self.monitor = MonitorThread(self.data, self)
        self.monitor.roast_ready.connect(self.on_roast)
        self.monitor.phase_changed.connect(self.on_phase_changed)
        self.monitor.praise_ready.connect(self.on_praise)

        self.roast_dialog = None
        self.settings_win = None
        self.workshop = None
        self.stats_win = None
        self.tray = None
        self._tick_n = 0
        self._hinted = False
        self._quitting = False

        self.build_ui()
        self.build_tray()
        self.monitor.start()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(500)

    def build_ui(self):
        self.setWindowTitle(APP + " — your disappointed productivity guardian")
        self.setWindowIcon(self.icon)
        self.setFixedSize(560, 700)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 12)
        root.setSpacing(10)

        t = QLabel("ROAST GUARD")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(f"color: {RED}; font-size: 22pt; font-weight: bold;")
        s = QLabel("catching you slacking since you installed it")
        s.setAlignment(Qt.AlignCenter)
        s.setStyleSheet(f"color: {DIM};")
        root.addWidget(t)
        root.addWidget(s)

        card = QFrame()
        card.setObjectName("card")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(14, 10, 14, 10)
        self.status = QLabel("…")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {GREEN}; font-size: 12pt; font-weight: bold;")
        cv.addWidget(self.status)
        root.addWidget(card)

        stats = QHBoxLayout()
        stats.setSpacing(8)
        focus_card, self.stat_focus = self._stat_card(stats, "FOCUSED TODAY", GREEN)
        slack_card, self.stat_slack = self._stat_card(stats, "SLACKED TODAY", RED)
        _, self.stat_roast = self._stat_card(stats, "ROASTS SERVED", YELLOW)
        focus_card.setToolTip("Active time only — idle is frozen, breaks are ☕.")
        slack_card.setToolTip("Active time only — breaks don't count as slacking.")
        root.addLayout(stats)

        # ---- pomodoro panel -------------------------------------------
        pom = QFrame()
        pom.setObjectName("card")
        pv = QVBoxLayout(pom)
        pv.setContentsMargins(14, 10, 14, 10)
        pv.setSpacing(5)

        prow = QHBoxLayout()
        self.pom_phase_lbl = QLabel("🍅 Pomodoro")
        self.pom_phase_lbl.setStyleSheet(f"color: {DIM}; font-size: 12pt; font-weight: bold;")
        self.pom_time_lbl = QLabel("—")
        self.pom_time_lbl.setAlignment(Qt.AlignRight)
        self.pom_time_lbl.setStyleSheet(f"color: {DIM}; font-size: 18pt; font-weight: bold;")
        prow.addWidget(self.pom_phase_lbl)
        prow.addStretch(1)
        prow.addWidget(self.pom_time_lbl)
        pv.addLayout(prow)

        self.pom_bar = QProgressBar()
        self.pom_bar.setTextVisible(False)
        self.pom_bar.setRange(0, 100)
        self.pom_bar.setFixedHeight(6)
        pv.addWidget(self.pom_bar)

        pbrow = QHBoxLayout()
        self.pom_start_btn = btn("▶ Start focus", "primary", self.monitor.pom_start)
        self.pom_start_btn.setToolTip("25-min focus block — roasts sharpen, "
                                      "strict mode armed")
        self.pom_skip_btn = btn("⏭ Skip", "ghost", self.monitor.pom_skip)
        self.pom_skip_btn.setToolTip("Abandon current phase (focus skip = no 🍅 credit)")
        self.pom_stop_btn = btn("⏹ Stop session", "ghost", self.monitor.pom_stop)
        self.pom_skip_btn.setEnabled(False)
        self.pom_stop_btn.setEnabled(False)
        pbrow.addWidget(self.pom_start_btn)
        pbrow.addWidget(self.pom_skip_btn)
        pbrow.addWidget(self.pom_stop_btn)
        pbrow.addStretch(1)
        pv.addLayout(pbrow)

        self.pom_sess_lbl = QLabel("")
        self.pom_sess_lbl.setStyleSheet(f"color: {DIM}; font-size: 8pt;")
        pv.addWidget(self.pom_sess_lbl)
        root.addWidget(pom)

        barcard = QFrame()
        barcard.setObjectName("card")
        bv = QVBoxLayout(barcard)
        bv.setContentsMargins(12, 8, 12, 10)
        bv.setSpacing(4)
        self.ratio_lbl = QLabel("focus ratio today: —")
        self.ratio_lbl.setStyleSheet(f"color: {DIM}; font-size: 9pt;")
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 100)
        self.bar.setFixedHeight(8)
        bv.addWidget(self.ratio_lbl)
        bv.addWidget(self.bar)
        root.addWidget(barcard)

        row = QHBoxLayout()
        row.addStretch(1)
        self.pause_btn = btn("Pause 15 min", "warn", self.monitor.toggle_pause)
        row.addWidget(self.pause_btn)
        row.addWidget(btn("Settings", "accent", self.open_settings))
        row.addWidget(btn("✍️ Insults", "accent", self.open_workshop))
        
        self.hardcore_btn = btn("Hardcore: OFF", "ghost", self.toggle_hardcore)
        row.addWidget(self.hardcore_btn)
        
        test = btn("Test roast", "danger", self.test_roast)
        test.setToolTip("Fires a sample roast right now (doesn't count toward stats)")
        row.addWidget(test)
        row.addStretch(1)
        root.addLayout(row)

        self.tip_lbl = QLabel(random.choice(TIPS))
        self.tip_lbl.setAlignment(Qt.AlignCenter)
        self.tip_lbl.setWordWrap(True)
        self.tip_lbl.setStyleSheet(f"color: {DIM}; font-style: italic; font-size: 9pt;")
        root.addWidget(self.tip_lbl, 1)

    def _stat_card(self, layout, title, color):
        card = QFrame()
        card.setObjectName("card")
        v = QVBoxLayout(card)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(2)
        lab = QLabel(title)
        lab.setAlignment(Qt.AlignCenter)
        lab.setStyleSheet(f"color: {DIM}; font-size: 8pt; font-weight: bold;")
        val = QLabel("0m 00s")
        val.setAlignment(Qt.AlignCenter)
        val.setStyleSheet(f"color: {color}; font-size: 14pt; font-weight: bold;")
        v.addWidget(lab)
        v.addWidget(val)
        layout.addWidget(card, 1)
        return card, val

    def build_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        QApplication.instance().setQuitOnLastWindowClosed(False)
        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setToolTip(APP + " — still watching")
        menu = QMenu()
        menu.addAction("Show RoastGuard", self.show_and_raise)
        menu.addAction("🍅 Start focus block", self.monitor.pom_start)
        self.act_pause = menu.addAction("Pause 15 min", self.monitor.toggle_pause)
        menu.addAction("Test roast", self.test_roast)
        menu.addAction("📊 Roast stats", self.open_stats)
        menu.addSeparator()
        menu.addAction("Quit", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: r == QSystemTrayIcon.Trigger and self.show_and_raise())
        self.tray.show()

    def show_and_raise(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def tick(self):
        self._tick_n += 1
        m = self.monitor
        now = time.time()

        # ---- pomodoro panel -----------------------------------------
        ph = m.pom_phase
        if ph == "off":
            self.pom_phase_lbl.setText("🍅 Pomodoro")
            self.pom_phase_lbl.setStyleSheet(f"color: {DIM}; font-size: 12pt; font-weight: bold;")
            self.pom_time_lbl.setText("—")
            self.pom_time_lbl.setStyleSheet(f"color: {DIM}; font-size: 18pt; font-weight: bold;")
            self.pom_bar.setValue(0)
            self.pom_bar.setStyleSheet(
                "QProgressBar { background: #2a2a38; border: none; border-radius: 3px; }"
                f"QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}")
            self.pom_start_btn.setText("▶ Start focus")
            self.pom_start_btn.setEnabled(True)
            self.pom_skip_btn.setEnabled(False)
            self.pom_stop_btn.setEnabled(False)
        else:
            name, color = {"focus": ("🍅 FOCUS", ACCENT),
                           "break": ("☕ BREAK", YELLOW),
                           "long": ("🛌 LONG BREAK", IDLE_C)}[ph]
            self.pom_phase_lbl.setText(name)
            self.pom_phase_lbl.setStyleSheet(f"color: {color}; font-size: 12pt; font-weight: bold;")
            
            if m.pom_paused:
                self.pom_time_lbl.setText(f"⏸ {mmss(m.pom_remaining)}")
            else:
                self.pom_time_lbl.setText(mmss(m.pom_remaining))
                
            self.pom_time_lbl.setStyleSheet(f"color: {color}; font-size: 18pt; font-weight: bold;")
            frac = (1 - m.pom_remaining / m.pom_len) if m.pom_len else 0
            self.pom_bar.setValue(int(frac * 100))
            self.pom_bar.setStyleSheet(
                "QProgressBar { background: #2a2a38; border: none; border-radius: 3px; }"
                f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}")
            
            try: self.pom_start_btn.clicked.disconnect()
            except RuntimeError: pass
            
            if m.pom_paused:
                self.pom_start_btn.setText("▶ Start break" if ph in ("break", "long") else "▶ Resume focus")
                self.pom_start_btn.setEnabled(True)
                self.pom_start_btn.clicked.connect(m.pom_start)
            else:
                self.pom_start_btn.setText("Running...")
                self.pom_start_btn.setEnabled(False)
            
            self.pom_skip_btn.setEnabled(True)
            self.pom_stop_btn.setEnabled(True)

        d = self.data["daily"]
        self.pom_sess_lbl.setText(
            f"🍅 {d['pomodoros']} done · 💔 {d['broken']} broken · "
            f"☕ {fmt(d['break'])} of sanctioned break today")

        # ---- hardcore toggle button state ----
        self.hardcore_btn.setText(f"Hardcore: {'ON' if self.data['hardcore'] else 'OFF'}")
        self.hardcore_btn.setProperty("variant", "danger" if self.data["hardcore"] else "ghost")
        self.hardcore_btn.style().unpolish(self.hardcore_btn)
        self.hardcore_btn.style().polish(self.hardcore_btn)

        # ---- work hours status check ----
        is_off_clock = False
        if self.data.get("work_hours_enabled"):
            now_dt = datetime.now()
            try:
                sh, sm = map(int, self.data.get("work_start", "09:00").split(':'))
                eh, em = map(int, self.data.get("work_end", "17:00").split(':'))
                start_t = now_dt.replace(hour=sh, minute=sm, second=0, microsecond=0)
                end_t = now_dt.replace(hour=eh, minute=em, second=0, microsecond=0)
                if start_t < end_t:
                    is_off_clock = not (start_t <= now_dt < end_t)
                else:
                    is_off_clock = not (now_dt >= start_t or now_dt < end_t)
            except Exception:
                pass

        if is_off_clock:
            self.status.setText(f"🛌  OFF THE CLOCK — work hours are {self.data['work_start']} to {self.data['work_end']}. Enjoy your break!")
            self.status.setStyleSheet(f"color: {IDLE_C}; font-size: 12pt; font-weight: bold;")
        elif now < m.paused_until:
            self.status.setText(f"⏸  Paused — shame suspended "
                                f"({int(m.paused_until - now)}s left); "
                                f"pomodoro clock frozen too")
            self.status.setStyleSheet(f"color: {YELLOW}; font-size: 12pt; font-weight: bold;")
        elif m.idle:
            mins = int((time.time() - m.idle_since) // 60) + 1
            self.status.setText(f"😴  IDLE — clock frozen "
                                f"(~{mins} min away; nothing counts)")
            self.status.setStyleSheet(f"color: {IDLE_C}; font-size: 12pt; font-weight: bold;")
        elif ph == "focus":
            if m.current_site:
                self.status.setText(f"🍅 {mmss(m.pom_remaining)} left — 🚨 CAUGHT: "
                                    f"{m.current_site} ({fmt(m.streak)})"
                                    + (" — strict will break this block!"
                                       if self.data["pom_strict"] else ""))
                self.status.setStyleSheet(f"color: {RED}; font-size: 12pt; font-weight: bold;")
            elif m.perm_warning:
                self.status.setText("⚠  Can't read window titles. macOS: allow "
                                    "Accessibility. Linux: install xdotool.")
                self.status.setStyleSheet(f"color: {YELLOW}; font-size: 12pt; font-weight: bold;")
            else:
                self.status.setText(f"🍅 FOCUS — {mmss(m.pom_remaining)} left, "
                                    f"clean so far")
                self.status.setStyleSheet(f"color: {ACCENT}; font-size: 12pt; font-weight: bold;")
        elif ph in ("break", "long"):
            label = "☕ BREAK" if ph == "break" else "🛌 LONG BREAK"
            self.status.setText(f"{label} — {mmss(m.pom_remaining)} of sanctioned "
                                f"slacking. Roasts stand down.")
            self.status.setStyleSheet(
                f"color: {YELLOW if ph == 'break' else IDLE_C}; font-size: 12pt; font-weight: bold;")
        elif m.perm_warning:
            self.status.setText("⚠  Can't read window titles. macOS: allow "
                                "Accessibility. Linux: install xdotool.")
            self.status.setStyleSheet(f"color: {YELLOW}; font-size: 12pt; font-weight: bold;")
        elif m.current_site:
            self.status.setText(f"🚨  CAUGHT: {m.current_site} — "
                                f"{fmt(m.streak)} and counting")
            self.status.setStyleSheet(f"color: {RED}; font-size: 12pt; font-weight: bold;")
        else:
            self.status.setText("✅  FOCUSED — suspicious, but I'll allow it")
            self.status.setStyleSheet(f"color: {GREEN}; font-size: 12pt; font-weight: bold;")

        paused = now < m.paused_until
        self.pause_btn.setText("End pause early" if paused else "Pause 15 min")
        if self.tray:
            self.act_pause.setText("End pause early" if paused else "Pause 15 min")

        self.stat_focus.setText(fmt(d["focus"]))
        self.stat_slack.setText(fmt(d["distraction"]))
        self.stat_roast.setText(str(d["insults"]))

        total = d["focus"] + d["distraction"]
        ratio = d["focus"] / total if total else 0
        self.ratio_lbl.setText(f"focus ratio today: {ratio*100:.0f}%"
                               + (" (active time)" if total else "")
                               if total else "focus ratio today: —")
        self.bar.setValue(int(ratio * 100))

        if self._tick_n % 30 == 0:
            self.tip_lbl.setText(random.choice(TIPS))
        if self._tick_n % 240 == 0:
            self.save_data()

    def on_phase_changed(self, info: dict):
        if self.data["sound"]:
            play_sound(3)
        if self.tray:
            self.tray.showMessage(APP, info.get("msg", ""),
                                  QSystemTrayIcon.Information, 4000)

    def save_data(self):
        save_data(self.data)

    def on_roast(self, roast: dict):
        if self.roast_dialog is not None:
            return
        self.monitor.popup_open = True
        dlg = RoastDialog(roast, self.data["hardcore"], self.data["sound"],
                          self.monitor, self)
        self.roast_dialog = dlg
        dlg.finished.connect(lambda _: setattr(self, "roast_dialog", None))
        dlg.show()
        if self.data.get("force_focus", True):
            dlg.raise_()
            dlg.activateWindow()

    def on_praise(self, site: str):
        if self.tray:
            self.tray.showMessage(APP, f"Left {site} within 10s. I'm proud. 👏", 
                                  QSystemTrayIcon.Information, 3000)

    def toggle_hardcore(self):
        self.data["hardcore"] = not self.data["hardcore"]
        self.save_data()

    def test_roast(self):
        if self.monitor.popup_open:
            return
        sample = fill(random.choice(pool_for(2, self.data)), "the test chamber", 7)
        self.on_roast({"text": "Testing the pain? Brave.\n\n" + sample,
                       "site": "test mode", "streak": 0, "tier": 2})

    def open_settings(self):
        if self.settings_win is not None and self.settings_win.isVisible():
            self.settings_win.raise_()
            return
        self.settings_win = SettingsDialog(self)
        self.settings_win.show()

    def open_workshop(self):
        if self.workshop is not None and self.workshop.isVisible():
            self.workshop.raise_()
            return
        self.workshop = InsultWorkshop(self)
        self.workshop.show()

    def open_stats(self):
        if self.stats_win is not None and self.stats_win.isVisible():
            self.stats_win.raise_()
            self.stats_win.rebuild()
            return
        self.stats_win = RoastStatsDialog(self)
        self.stats_win.show()

    def quit_app(self):
        self._quitting = True
        self.close()

    def closeEvent(self, e):
        if self.tray is not None and not self._quitting:
            e.ignore()
            self.hide()
            if not self._hinted:
                self._hinted = True
                self.tray.showMessage(APP,
                    "Minimized to tray — still watching. 👀",
                    QSystemTrayIcon.Information, 3000)
            return
        if self._quitting or QMessageBox.question(
                self, APP,
                "Quitting already? Your procrastination thanks you.\n\n"
                "Stats are saved either way. See you soon. 😏"
                ) == QMessageBox.Yes:
            self.save_data()
            self.monitor.stop()
            self.monitor.wait(3000)
            e.accept()
        else:
            e.ignore()


# ------------------------------------------------------------------ entry

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setStyleSheet(QSS)
    icon = make_app_icon()
    app.setWindowIcon(icon)
    win = MainWindow(icon)
    win.show()

    # ---- graceful Ctrl+C (SIGINT) -------------------------------------
    def _on_sigint(signum, frame):
        QTimer.singleShot(0, win.quit_app)

    signal.signal(signal.SIGINT, _on_sigint)
    wakeup = QTimer()
    wakeup.timeout.connect(lambda: None)
    wakeup.start(200)
    app._sigint_wakeup = wakeup
    # --------------------------------------------------------------------

    sys.exit(app.exec())


if __name__ == "__main__":
    main()