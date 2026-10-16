"""Open the real window with sample data and save screenshots of each tab.

Usage::

    python dev/tools/gui_shots.py OUT_DIR [--lang vi] [--theme dark] [--size 1240x820]

Screens are captured with PowerShell (System.Drawing), so no extra packages.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))

from ytscraper import gui, settings as settings_mod  # noqa: E402
from ytscraper.engine import Entry  # noqa: E402
from ytscraper.i18n import set_language  # noqa: E402

PS = r"""
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public class DPI { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
'@
[DPI]::SetProcessDPIAware() | Out-Null
$bmp = New-Object System.Drawing.Bitmap @W, @H
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(@X, @Y, 0, 0, $bmp.Size)
$bmp.Save('@OUT', [System.Drawing.Imaging.ImageFormat]::Png)
"""


def shot(app: gui.App, out: Path) -> None:
    """Capture the window to ``out``."""
    app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    script = PS.replace("@W", str(w)).replace("@H", str(h)).replace("@X", str(x)).replace("@Y", str(y)).replace("@OUT", str(out))
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True)
    print("saved", out)


def main() -> None:
    """Entry point."""
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--theme", default="light")
    ap.add_argument("--size", default="1240x820")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    # Keep the user's settings untouched: use a throwaway settings file.
    tmp = args.out / "settings.json"
    tmp.write_text(f'{{"ui_language": "{args.lang}", "theme": "{args.theme}", "geometry": "{args.size}"}}',
                   encoding="utf-8")
    settings_mod.settings_path = lambda: tmp  # type: ignore[assignment]
    set_language(args.lang)

    app = gui.App()
    app.attributes("-topmost", True)
    sample = [
        Entry("4QEDPfuQfCQ", "Bản tin Thời sự sáng 15/10 | Tin tức thời sự cập nhật 24h", "u", 640,
              "Đài PT-TH Hải Phòng", "🔍 bản tin thời sự"),
        Entry("Y0fbpRGVDKo", "Bản tin Thời sự sáng 16/10 | Tin tức thời sự cập nhật 24h", "u", 621,
              "Đài PT-TH Hải Phòng", "🔍 bản tin thời sự"),
        Entry("B3G9oTQ3a-k", "Free Relaxing Piano Music | No Attribution | No Copyright", "u", 3720, "", ""),
        Entry("dQw4w9WgXcQ", "Rick Astley - Never Gonna Give You Up (Official Video)", "u", 213, "", "Playlist: 80s"),
        Entry("aaaaaaaaaaa", "A private video", "u", None, "", "Playlist: 80s"),
    ]
    app.add_entries(sample)
    app.checked.discard("aaaaaaaaaaa")
    app.status_by_id.update({
        "4QEDPfuQfCQ": ("done", "vi"),
        "Y0fbpRGVDKo": ("working", "video 42%"),
        "B3G9oTQ3a-k": ("no_captions", ["en", "sq-orig"]),
        "aaaaaaaaaaa": ("error", "private"),
    })
    app.refresh_tree()
    app.links_box.insert("1.0", "https://www.youtube.com/playlist?list=PL590L5WQmH8fJ54F369BLDSqIwcs-TCfs\n"
                                "https://youtu.be/dQw4w9WgXcQ\nbản tin thời sự\n")
    app.progress.set(0.42)
    app.set_status("2/5 · Bản tin Thời sự sáng 16/10")
    app.after(800, lambda: None)
    for _ in range(10):
        app.update()
    shot(app, args.out / f"1-download-{args.lang}-{args.theme}.png")
    names = list(app.tab_names.values())
    app._add_paths([ROOT / "legacy" / "urls.txt"] if (ROOT / "legacy" / "urls.txt").exists() else [])
    for i, name in enumerate(names[1:], 2):
        app.tabs.set(name)
        for _ in range(5):
            app.update()
        shot(app, args.out / f"{i}-{name.split()[0].lower()}-{args.lang}-{args.theme}.png")
    app.tabs.set(names[0])
    app.toggle_details()
    app.log("[youtube] Extracting URL: https://www.youtube.com/watch?v=Y0fbpRGVDKo")
    for _ in range(5):
        app.update()
    shot(app, args.out / f"5-details-{args.lang}-{args.theme}.png")
    app.destroy()


if __name__ == "__main__":
    main()
