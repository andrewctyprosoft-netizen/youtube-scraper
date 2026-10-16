"""Desktop window (customtkinter). All slow work runs in threads that post
events to a queue; the Tk thread drains it every 100 ms."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from customtkinter import ThemeManager

from . import __version__
from . import settings as settings_mod
from .docx_export import DocOptions
from .engine import Auth, Cancelled, Engine, EngineError, Entry, Tools, oembed_title
from .i18n import CAPTION_LANGUAGES, set_language, t
from .jobs import (
    DownloadJob,
    FileJobOptions,
    JobOptions,
    combine_files,
    format_duration,
    natural_key,
    title_sort_key,
)
from .links import parse_input, search_url

ACCENT = ("#C4302B", "#B3261E")
ACCENT_HOVER = ("#9E2621", "#8C1D18")
_BLUES = {"#3B8ED0": 0, "#1F6AA5": 1, "#36719F": 0, "#144870": 1}
QUALITIES = ["best", "1080", "720", "480", "360"]
LOGIN_BROWSERS = ["", "firefox", "edge", "chrome", "brave", "opera", "vivaldi", "chromium", "file"]
STATUS_TAGS = {"error": "bad", "no_captions": "warn", "working": "busy"}


def resource(name: str) -> Path:
    """Path to a bundled asset (works frozen and in dev)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / "assets" / name


def apply_accent() -> None:
    """Swap customtkinter's blue accent for a YouTube-like red."""
    ctk.set_default_color_theme("blue")
    for widget in ThemeManager.theme.values():
        if not isinstance(widget, dict):
            continue
        for key, value in list(widget.items()):
            if isinstance(value, list) and len(value) == 2 and all(isinstance(v, str) for v in value):
                if value[0] in ("#3B8ED0", "#36719F") or value[1] in ("#1F6AA5", "#144870"):
                    hover = "hover" in key
                    widget[key] = list(ACCENT_HOVER if hover else ACCENT)


def open_path(path: str | Path) -> None:
    """Open a file or folder with its Windows default program.

    The frozen app sets its private ``_internal`` folder as DLL directory, and a
    program started from here inherits it: Word then loaded our VCRUNTIME140.dll
    and kept the app folder locked. Clear it for the launch and restore it.
    """
    path = str(path)
    if os.name == "nt":
        import ctypes

        k32 = ctypes.windll.kernel32
        buf = ctypes.create_unicode_buffer(32768)
        had = k32.GetDllDirectoryW(len(buf), buf)
        k32.SetDllDirectoryW(None)
        try:
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            os.startfile(path, cwd=folder or None)  # noqa: S606 - user-chosen local path
        finally:
            if had:
                k32.SetDllDirectoryW(buf.value)
    else:
        subprocess.Popen(["xdg-open", path])


class App(ctk.CTk):
    """Main window."""

    def __init__(self) -> None:
        self.s = settings_mod.load()
        set_language("en")  # English-only interface
        ctk.set_appearance_mode(self.s.theme)
        apply_accent()
        super().__init__()
        self.title(f"{t('app_title')} {__version__}")
        self._place_window()
        self._set_icon()

        self.events: queue.Queue = queue.Queue()
        self.entries: list[Entry] = []
        self.status_by_id: dict[str, tuple[str, str]] = {}
        self.checked: set[str] = set()
        self.files: list[Path] = []
        self.cancel = threading.Event()
        self.busy = False
        self.last_outputs: list[str] = []
        self.log_lines: list[str] = []
        self._save_after: str | None = None
        self.tools = Tools.discover()
        self.engine = Engine(self.tools, auth=self._auth())

        self.v: dict[str, tk.Variable] = {}
        for name, value in vars(self.s).items():
            if isinstance(value, bool):
                var: tk.Variable = tk.BooleanVar(self, value)
            elif isinstance(value, int):
                var = tk.IntVar(self, value)
            elif isinstance(value, float):
                var = tk.DoubleVar(self, value)
            else:
                var = tk.StringVar(self, value)
            var.trace_add("write", lambda *_: self._schedule_save())
            self.v[name] = var

        self.input_text = ""
        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self._drain)
        self.after(600, self._check_engine_async)

    # ------------------------------------------------------------ helpers

    def _place_window(self) -> None:
        """Fit the window to the screen; maximise on small laptop screens."""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.minsize(min(980, sw - 40), min(600, sh - 100))
        saved = self.s.geometry
        if saved and saved != "zoomed":
            try:
                w, rest = saved.split("x", 1)
                h = rest.split("+", 1)[0]
                if int(w) <= sw and int(h) <= sh - 40:
                    self.geometry(saved)
                    return
            except ValueError:
                pass
        if sh <= 820 or sw <= 1300 or saved == "zoomed":
            self.geometry(f"{sw - 80}x{sh - 120}+20+10")
            self.after(0, lambda: self.state("zoomed"))
        else:
            self.geometry(f"1260x820+{(sw - 1260) // 2}+{max(0, (sh - 860) // 2)}")

    def _menu(self, master, **kwargs) -> ctk.CTkOptionMenu:
        """Neutral (grey) drop-down; red is kept for actions."""
        return ctk.CTkOptionMenu(master, fg_color=("gray82", "gray25"), button_color=("gray74", "gray32"),
                                 button_hover_color=("gray66", "gray38"), text_color=("gray10", "gray90"),
                                 dropdown_font=self.font(12), font=self.font(12), **kwargs)

    def _make_boxes(self) -> None:
        """Draw the tick-box images used in the video list."""
        dark = ctk.get_appearance_mode() == "Dark"
        accent = ACCENT[1] if dark else ACCENT[0]
        border = "#9A9A9A" if dark else "#7A7A7A"
        on, off = tk.PhotoImage(master=self, width=20, height=20), tk.PhotoImage(master=self, width=20, height=20)
        corners = {(3, 3), (3, 16), (16, 3), (16, 16)}
        for x in range(3, 17):
            for y in range(3, 17):
                if (x, y) in corners:
                    continue
                on.put(accent, to=(x, y))
                if x in (3, 4, 15, 16) and y in range(3, 17) or y in (3, 4, 15, 16):
                    off.put(border, to=(x, y))
        tick = [(6, 10), (7, 11), (8, 12), (9, 13), (10, 12), (11, 11), (12, 10), (13, 9), (14, 8)]
        for x, y in tick:
            for dy in (-1, 0):
                on.put("#FFFFFF", to=(x, y + dy))
        self.box_on, self.box_off = on, off

    def _set_icon(self) -> None:
        ico = resource("icon.ico")
        if ico.exists():
            try:
                self.iconbitmap(str(ico))
                self.after(300, lambda: self.iconbitmap(str(ico)))
            except tk.TclError:
                pass

    def _auth(self) -> Auth:
        if self.s.login_browser == "file" and self.s.cookies_file:
            return Auth(cookies_file=self.s.cookies_file)
        if self.s.login_browser and self.s.login_browser != "file":
            return Auth(browser=self.s.login_browser)
        return Auth()

    def _schedule_save(self) -> None:
        if self._save_after:
            self.after_cancel(self._save_after)
        self._save_after = self.after(400, self._save_settings)

    def _save_settings(self) -> None:
        self._save_after = None
        for name, var in self.v.items():
            try:
                setattr(self.s, name, var.get())
            except (tk.TclError, ValueError):
                pass
        self.engine.auth = self._auth()
        settings_mod.save(self.s)

    def int_var(self, name: str, default: int) -> int:
        """Value of a numeric field, or ``default`` when the box holds junk."""
        try:
            return int(self.v[name].get())
        except (tk.TclError, ValueError):
            return default

    def post(self, kind: str, **data: object) -> None:
        """Thread-safe: queue an event for the Tk thread."""
        self.events.put((kind, data))

    def font(self, size: int = 13, weight: str = "normal") -> ctk.CTkFont:
        """Shared font helper."""
        return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)

    # ------------------------------------------------------------ layout

    def build_ui(self) -> None:
        """(Re)build every widget, e.g. after switching the interface language."""
        for child in self.winfo_children():
            child.destroy()
        self.title(f"{t('app_title')} {__version__}")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(8, 0))
        header.grid_columnconfigure(1, weight=1)
        logo = ctk.CTkLabel(header, text="▶", width=40, height=32, corner_radius=8, fg_color=ACCENT,
                            text_color="white", font=self.font(18, "bold"))
        logo.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ctk.CTkLabel(header, text=t("app_title"), font=self.font(20, "bold"), anchor="w").grid(
            row=0, column=1, sticky="w")
        ctk.CTkLabel(header, text=t("app_tagline"), font=self.font(12), text_color=("gray35", "gray70"),
                     anchor="w").grid(row=1, column=1, sticky="w")

        self.tabs = ctk.CTkTabview(self, corner_radius=10)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=12, pady=(4, 0))
        self.tab_names = {k: t(k) for k in ("tab_download", "tab_files", "tab_settings", "tab_help")}
        for name in self.tab_names.values():
            self.tabs.add(name)
        try:
            self.tabs._segmented_button.configure(font=self.font(13, "bold"))
        except AttributeError:
            pass
        self._make_boxes()
        self._build_download(self.tabs.tab(self.tab_names["tab_download"]))
        self._build_files(self.tabs.tab(self.tab_names["tab_files"]))
        self._build_settings(self.tabs.tab(self.tab_names["tab_settings"]))
        self._build_help(self.tabs.tab(self.tab_names["tab_help"]))
        self._build_statusbar()
        self._style_tree()
        self.refresh_tree()
        self.refresh_files()

    def _card(self, master, title: str | None = None) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(master, corner_radius=10)
        if title:
            ctk.CTkLabel(frame, text=title, font=self.font(15, "bold"), anchor="w").pack(
                fill="x", padx=14, pady=(10, 2))
        return frame

    def _check(self, master, key: str, var: str, command=None, indent: int = 0) -> ctk.CTkCheckBox:
        box = ctk.CTkCheckBox(master, text=t(key), variable=self.v[var], font=self.font(13),
                              checkbox_width=20, checkbox_height=20, command=command)
        box.pack(anchor="w", padx=(14 + indent, 10), pady=3)
        return box

    def _section_label(self, master, key: str) -> None:
        ctk.CTkLabel(master, text=t(key), font=self.font(12, "bold"), text_color=("gray30", "gray70"),
                     anchor="w").pack(fill="x", padx=14, pady=(10, 0))

    # ---- download tab

    def _build_download(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=0, minsize=380)
        tab.grid_rowconfigure(1, weight=1)

        # step 1
        step1 = self._card(tab, t("step1"))
        step1.grid(row=0, column=0, sticky="ew", padx=(4, 8), pady=(4, 8))
        ctk.CTkLabel(step1, text=t("step1_hint"), font=self.font(12), text_color=("gray35", "gray70"),
                     anchor="w", justify="left", wraplength=700).pack(fill="x", padx=14)
        self.links_box = ctk.CTkTextbox(step1, height=72, font=self.font(13), wrap="none")
        self.links_box.pack(fill="x", padx=14, pady=(6, 6))
        if self.input_text:
            self.links_box.insert("1.0", self.input_text)
        row = ctk.CTkFrame(step1, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 12))
        self.add_btn = ctk.CTkButton(row, text="＋  " + t("add_to_list"), command=self.on_add_links,
                                     font=self.font(13, "bold"), height=34, width=190)
        self.add_btn.pack(side="left")
        for key, cmd in (("paste", self.on_paste), ("open_txt", self.on_open_txt), ("clear_box", self.on_clear_box)):
            ctk.CTkButton(row, text=t(key), command=cmd, height=34, width=110, fg_color="transparent",
                          border_width=1, text_color=("gray10", "gray90"), font=self.font(13)).pack(
                side="left", padx=(8, 0))
        self.add_status = ctk.CTkLabel(row, text="", font=self.font(12), text_color=("gray35", "gray70"))
        self.add_status.pack(side="left", padx=12)

        # list
        lst = self._card(tab)
        lst.grid(row=1, column=0, sticky="nsew", padx=(4, 8), pady=(0, 4))
        top = ctk.CTkFrame(lst, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(top, text=t("list_title"), font=self.font(15, "bold")).pack(side="left")
        self.count_label = ctk.CTkLabel(top, text="", font=self.font(12), text_color=("gray35", "gray70"))
        self.count_label.pack(side="left", padx=10)
        self.filter_entry = ctk.CTkEntry(top, placeholder_text=t("filter"), width=240, font=self.font(12))
        self.filter_entry.bind("<KeyRelease>", lambda e: self.refresh_tree())
        self.filter_entry.pack(side="right")

        holder = tk.Frame(lst, bd=0, highlightthickness=0)
        holder.pack(fill="both", expand=True, padx=14, pady=4)
        cols = ("n", "title", "length", "from", "status")
        self.tree = ttk.Treeview(holder, columns=cols, show="tree headings", selectmode="extended",
                                 style="YS.Treeview")
        self.tree.heading("#0", text="✓", anchor="center")
        self.tree.column("#0", width=44, minwidth=44, stretch=False, anchor="center")
        heads = {"n": "#", "title": t("col_title"), "length": t("col_length"),
                 "from": t("col_from"), "status": t("col_status")}
        widths = {"n": (40, False), "title": (330, True), "length": (64, False),
                  "from": (120, True), "status": (210, True)}
        for col in cols:
            self.tree.heading(col, text=heads[col], anchor="w" if col in ("title", "from", "status") else "center")
            width, stretch = widths[col]
            self.tree.column(col, width=width, minwidth=30, stretch=stretch,
                             anchor="w" if col in ("title", "from", "status") else "center")
        sb = ctk.CTkScrollbar(holder, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", self.on_tree_double)
        self.tree.bind("<space>", lambda e: self.toggle_rows(self.tree.selection()))
        self.tree.bind("<Delete>", lambda e: self.remove_rows(self.tree.selection()))
        self.tree.bind("<Button-3>", self.on_tree_menu)
        self.empty_hint = ctk.CTkLabel(holder, text=t("list_empty"), font=self.font(13),
                                       text_color=("gray45", "gray60"), fg_color=("#FFFFFF", "#242424"))

        bottom = ctk.CTkFrame(lst, fg_color="transparent")
        bottom.pack(fill="x", padx=14, pady=(4, 12), side="bottom", before=holder)  # never pushed off-screen
        for key, cmd in (("select_all", lambda: self.set_all(True)), ("select_none", lambda: self.set_all(False)),
                         ("tick_failed", self.tick_failed), ("remove_unticked", self.remove_unticked),
                         ("clear_list", self.clear_list),
                         ("export_links", self.export_links)):
            ctk.CTkButton(bottom, text=t(key), command=cmd, height=30, width=10, fg_color="transparent",
                          border_width=1, text_color=("gray10", "gray90"), font=self.font(12)).pack(
                side="left", padx=(0, 8))

        # right column: options + start
        right = ctk.CTkFrame(tab, fg_color="transparent")
        right.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(0, 4), pady=4)
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        opts = ctk.CTkScrollableFrame(right, corner_radius=10, width=360)
        opts.grid(row=0, column=0, sticky="nsew")
        self._build_options(opts)

        start_card = self._card(right)
        start_card.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.start_btn = ctk.CTkButton(start_card, text="▶  " + t("start"), command=self.on_start,
                                       height=46, font=self.font(17, "bold"))
        self.start_btn.pack(fill="x", padx=14, pady=12)

    def _build_options(self, opts) -> None:
        ctk.CTkLabel(opts, text=t("step2"), font=self.font(15, "bold"), anchor="w").pack(
            fill="x", padx=14, pady=(10, 2))
        self._check(opts, "want_transcript", "want_transcript", command=self._sync_option_states)
        vrow = ctk.CTkFrame(opts, fg_color="transparent")
        vrow.pack(fill="x")
        ctk.CTkCheckBox(vrow, text=t("want_video"), variable=self.v["want_video"], font=self.font(13),
                        checkbox_width=20, checkbox_height=20, command=self._sync_option_states).pack(
            side="left", padx=(14, 6), pady=3)
        q_labels = [t("q_best") if q == "best" else f"{q}p" for q in QUALITIES]
        self.quality_menu = self._menu(vrow, values=q_labels, width=130,
                                       command=lambda lab: self.v["video_quality"].set(
                                                  QUALITIES[q_labels.index(lab)]))
        cur = self.s.video_quality if self.s.video_quality in QUALITIES else "720"
        self.quality_menu.set(q_labels[QUALITIES.index(cur)])
        self.quality_menu.pack(side="right", padx=10)
        self._check(opts, "want_audio", "want_audio", command=self._sync_option_states)
        self.thumb_box = self._check(opts, "want_thumbnail", "want_thumbnail")

        self.transcript_frame = ctk.CTkFrame(opts, fg_color="transparent")
        self.transcript_frame.pack(fill="x")
        tf = self.transcript_frame
        self._section_label(tf, "transcript_opts")
        lrow = ctk.CTkFrame(tf, fg_color="transparent")
        lrow.pack(fill="x", pady=3)
        ctk.CTkLabel(lrow, text=t("language"), font=self.font(13)).pack(side="left", padx=(14, 8))
        self.lang_codes = [c for c, _ in CAPTION_LANGUAGES]
        self.lang_labels = [t("lang_orig") if c == "orig" else f"{name} ({c})" for c, name in CAPTION_LANGUAGES]
        if self.s.language not in self.lang_codes:
            self.lang_codes.append(self.s.language)
            self.lang_labels.append(self.s.language)
        self.lang_menu = self._menu(lrow, values=self.lang_labels + [t("lang_other")], width=200,
                                    command=self.on_caption_language,
                                           dynamic_resizing=False)
        self.lang_menu.set(self.lang_labels[self.lang_codes.index(self.s.language)])
        self.lang_menu.pack(side="left")
        self._check(tf, "fallback", "fallback_original")
        ctk.CTkLabel(tf, text=t("fallback_hint"), font=self.font(11), text_color=("gray40", "gray65"),
                     anchor="w", justify="left", wraplength=300).pack(fill="x", padx=(48, 10))
        self._check(tf, "allow_auto", "allow_auto")
        self._transcript_cleaning(tf)

        self._section_label(tf, "save_as")
        self.docx_box = self._check(tf, "save_docx", "save_docx", command=self._sync_option_states)
        self.word_frame = ctk.CTkFrame(tf, fg_color="transparent")
        self.word_frame.pack(fill="x")
        for key in ("doc_contents", "doc_breaks", "doc_info", "doc_numbered"):
            self._check(self.word_frame, key, key, indent=26)
        self._check(tf, "save_txt", "save_txt")
        self._check(tf, "save_srt", "save_srt")
        self._check(tf, "save_combined_txt", "save_combined_txt")
        self._check(opts, "save_csv", "save_csv")

        ctk.CTkLabel(opts, text=t("step3"), font=self.font(15, "bold"), anchor="w").pack(
            fill="x", padx=14, pady=(16, 2))
        frow = ctk.CTkFrame(opts, fg_color="transparent")
        frow.pack(fill="x", padx=14, pady=3)
        ctk.CTkEntry(frow, textvariable=self.v["out_dir"], font=self.font(12)).pack(
            side="left", fill="x", expand=True)
        ctk.CTkButton(frow, text=t("browse"), width=80, command=self.on_browse_out, font=self.font(12)).pack(
            side="left", padx=(6, 0))
        nrow = ctk.CTkFrame(opts, fg_color="transparent")
        nrow.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(nrow, text=t("output_name"), font=self.font(13)).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(nrow, textvariable=self.v["output_name"], font=self.font(12)).pack(
            side="left", fill="x", expand=True)
        orow = ctk.CTkFrame(opts, fg_color="transparent")
        orow.pack(fill="x", padx=14, pady=(6, 3))
        ctk.CTkLabel(orow, text=t("order"), font=self.font(13)).pack(side="left", padx=(0, 8))
        orders = {"list": t("order_list"), "az": t("order_az"), "za": t("order_za")}
        self.order_seg = ctk.CTkSegmentedButton(
            orow, values=list(orders.values()), font=self.font(12),
            command=lambda lab: self.on_order(next(k for k, v in orders.items() if v == lab)))
        self.order_labels = orders
        self.order_seg.set(orders.get(self.v["file_order"].get(), orders["list"]))
        self.order_seg.pack(side="left")
        self._check(opts, "numbered_files", "numbered")
        ctk.CTkLabel(opts, text=t("order_hint"), font=self.font(11), text_color=("gray40", "gray65"),
                     anchor="w", justify="left", wraplength=300).pack(fill="x", padx=(48, 10))
        ctk.CTkButton(opts, text=t("open_folder"), command=lambda: self.open_out_dir(),
                      fg_color="transparent", border_width=1, text_color=("gray10", "gray90"),
                      font=self.font(12), height=28).pack(anchor="w", padx=14, pady=(6, 14))
        self._sync_option_states()

    def _transcript_cleaning(self, master) -> None:
        lay = ctk.CTkFrame(master, fg_color="transparent")
        lay.pack(fill="x", pady=3)
        ctk.CTkLabel(lay, text=t("layout"), font=self.font(13)).pack(side="left", padx=(14, 8))
        labels = {"paragraphs": t("layout_paragraphs"), "lines": t("layout_lines")}
        seg = ctk.CTkSegmentedButton(lay, values=list(labels.values()), font=self.font(12),
                                     command=lambda lab: self.v["layout"].set(
                                         "lines" if lab == labels["lines"] else "paragraphs"))
        seg.set(labels.get(self.v["layout"].get(), labels["paragraphs"]))
        seg.pack(side="left")
        self._check(master, "timestamps", "timestamps")
        self._check(master, "rm_rolling", "remove_rolling")
        self._check(master, "rm_all", "remove_all_repeats")
        self._check(master, "rm_tags", "remove_tags")

    def _sync_option_states(self) -> None:
        """Hide transcript / Word options that do not apply."""
        try:
            if self.v["want_transcript"].get():
                self.transcript_frame.pack(fill="x", after=self.thumb_box)
            else:
                self.transcript_frame.pack_forget()
            if self.v["save_docx"].get():
                self.word_frame.pack(fill="x", after=self.docx_box)
            else:
                self.word_frame.pack_forget()
            self.quality_menu.configure(state="normal" if self.v["want_video"].get() else "disabled")
        except (tk.TclError, AttributeError):
            pass

    # ---- files tab

    def _build_files(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=0, minsize=380)
        tab.grid_rowconfigure(0, weight=1)
        left = self._card(tab, t("files_title"))
        left.grid(row=0, column=0, sticky="nsew", padx=(4, 8), pady=4)
        ctk.CTkLabel(left, text=t("files_hint"), font=self.font(12), text_color=("gray35", "gray70"),
                     anchor="w", justify="left", wraplength=700).pack(fill="x", padx=14)
        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=8)
        ctk.CTkButton(row, text="＋  " + t("add_files"), command=self.on_add_files, height=34,
                      font=self.font(13, "bold")).pack(side="left")
        ctk.CTkButton(row, text=t("add_folder"), command=self.on_add_folder, height=34, width=120,
                      fg_color="transparent", border_width=1, text_color=("gray10", "gray90"),
                      font=self.font(13)).pack(side="left", padx=8)
        ctk.CTkLabel(row, text=t("sort_by"), font=self.font(13)).pack(side="left", padx=(16, 6))
        sorts = {"name": t("sort_name"), "date": t("sort_date"), "added": t("sort_added")}
        sort_menu = self._menu(row, values=list(sorts.values()), width=170,
                               command=lambda lab: self.on_sort_files(
                                          next(k for k, v in sorts.items() if v == lab)))
        sort_menu.set(sorts.get(self.s.files_sort, sorts["name"]))
        sort_menu.pack(side="left")

        holder = tk.Frame(left, bd=0, highlightthickness=0)
        holder.pack(fill="both", expand=True, padx=14, pady=4)
        self.ftree = ttk.Treeview(holder, columns=("n", "file", "folder"), show="headings",
                                  selectmode="extended", style="YS.Treeview")
        for col, head, width, stretch in (("n", "#", 42, False), ("file", t("col_file"), 380, True),
                                          ("folder", t("col_folder"), 260, True)):
            self.ftree.heading(col, text=head, anchor="w" if col != "n" else "center")
            self.ftree.column(col, width=width, stretch=stretch, anchor="w" if col != "n" else "center")
        fsb = ctk.CTkScrollbar(holder, command=self.ftree.yview)
        self.ftree.configure(yscrollcommand=fsb.set)
        self.ftree.pack(side="left", fill="both", expand=True)
        fsb.pack(side="right", fill="y")
        self.ftree.bind("<Delete>", lambda e: self.on_remove_files())
        bottom = ctk.CTkFrame(left, fg_color="transparent")
        bottom.pack(fill="x", padx=14, pady=(4, 12), side="bottom", before=holder)  # never pushed off-screen
        for key, cmd in (("move_up", lambda: self.on_move_files(-1)), ("move_down", lambda: self.on_move_files(1)),
                         ("remove", self.on_remove_files), ("clear_list", self.on_clear_files)):
            ctk.CTkButton(bottom, text=t(key), command=cmd, height=30, width=10, fg_color="transparent",
                          border_width=1, text_color=("gray10", "gray90"), font=self.font(12)).pack(
                side="left", padx=(0, 8))

        right = ctk.CTkFrame(tab, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 4), pady=4)
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        opts = ctk.CTkScrollableFrame(right, corner_radius=10, width=360)
        opts.grid(row=0, column=0, sticky="nsew")
        self._section_label(opts, "transcript_opts")
        self._transcript_cleaning(opts)
        self._section_label(opts, "save_as")
        self._check(opts, "save_docx_files", "save_docx")
        for key in ("doc_contents", "doc_breaks", "doc_numbered"):
            self._check(opts, key, key, indent=26)
        self._check(opts, "files_save_txt", "files_save_txt")
        self._check(opts, "files_save_srt", "files_save_srt")
        self._section_label(opts, "step3")
        frow = ctk.CTkFrame(opts, fg_color="transparent")
        frow.pack(fill="x", padx=14, pady=3)
        ctk.CTkEntry(frow, textvariable=self.v["files_out_dir"], font=self.font(12),
                     placeholder_text=self.s.out_dir).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(frow, text=t("browse"), width=80, font=self.font(12),
                      command=lambda: self._pick_dir("files_out_dir")).pack(side="left", padx=(6, 0))
        nrow = ctk.CTkFrame(opts, fg_color="transparent")
        nrow.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(nrow, text=t("output_name"), font=self.font(13)).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(nrow, textvariable=self.v["files_output_name"], font=self.font(12)).pack(
            side="left", fill="x", expand=True)
        card = self._card(right)
        card.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.combine_btn = ctk.CTkButton(card, text="▶  " + t("combine"), command=self.on_combine,
                                         height=46, font=self.font(17, "bold"))
        self.combine_btn.pack(fill="x", padx=14, pady=12)

    # ---- settings tab

    def _build_settings(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        page = ctk.CTkScrollableFrame(tab, corner_radius=10)
        page.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        def row(label_key: str):
            fr = ctk.CTkFrame(page, fg_color="transparent")
            fr.pack(fill="x", padx=14, pady=5)
            ctk.CTkLabel(fr, text=t(label_key), font=self.font(13), width=330, anchor="w").pack(side="left")
            return fr

        def hint(text: str) -> None:
            ctk.CTkLabel(page, text=text, font=self.font(12), text_color=("gray40", "gray65"), anchor="w",
                         justify="left", wraplength=760).pack(fill="x", padx=(358, 14))

        ctk.CTkLabel(page, text=t("tab_settings"), font=self.font(16, "bold"), anchor="w").pack(
            fill="x", padx=14, pady=(12, 6))
        themes = {"system": t("theme_system"), "light": t("theme_light"), "dark": t("theme_dark")}
        theme = ctk.CTkSegmentedButton(row("appearance"), values=list(themes.values()), font=self.font(12),
                                       command=lambda lab: self.on_theme(next(k for k, v in themes.items() if v == lab)))
        theme.set(themes.get(self.s.theme, themes["system"]))
        theme.pack(side="left")

        ctk.CTkEntry(row("delay"), textvariable=self.v["delay"], width=80, font=self.font(12)).pack(side="left")
        hint(t("delay_hint"))
        ctk.CTkEntry(row("search_count"), textvariable=self.v["search_count"], width=80,
                     font=self.font(12)).pack(side="left")
        workers = self._menu(row("workers"), values=["1", "2", "3", "4"], width=80,
                             command=lambda v: self.v["workers"].set(int(v)))
        workers.set(str(self.int_var("workers", 2)))
        workers.pack(side="left")
        hint(t("workers_hint"))
        ctk.CTkEntry(row("list_limit"), textvariable=self.v["list_limit"], width=80,
                     font=self.font(12)).pack(side="left")
        for key, var in (("reuse_cache", "reuse_cache"),):
            box = ctk.CTkCheckBox(page, text=t(key), variable=self.v[var], font=self.font(13),
                                  checkbox_width=20, checkbox_height=20)
            box.pack(anchor="w", padx=14, pady=5)

        dfr = row("default_folder")
        ctk.CTkEntry(dfr, textvariable=self.v["out_dir"], width=380, font=self.font(12)).pack(side="left")
        ctk.CTkButton(dfr, text=t("browse"), width=80, font=self.font(12),
                      command=self.on_browse_out).pack(side="left", padx=6)

        login_labels = {"": t("login_none"), "file": t("login_file")}
        labels = [login_labels.get(b, b.capitalize()) for b in LOGIN_BROWSERS]
        lfr = row("login")
        menu = self._menu(lfr, values=labels, width=220,
                          command=lambda lab: self.on_login(LOGIN_BROWSERS[labels.index(lab)]))
        cur = self.s.login_browser if self.s.login_browser in LOGIN_BROWSERS else ""
        menu.set(labels[LOGIN_BROWSERS.index(cur)])
        menu.pack(side="left")
        self.cookie_label = ctk.CTkLabel(lfr, text=Path(self.s.cookies_file).name if cur == "file" else "",
                                         font=self.font(12))
        self.cookie_label.pack(side="left", padx=8)
        hint(t("login_hint"))

        ctk.CTkLabel(page, text=t("engine"), font=self.font(16, "bold"), anchor="w").pack(
            fill="x", padx=14, pady=(18, 6))
        efr = ctk.CTkFrame(page, fg_color="transparent")
        efr.pack(fill="x", padx=14, pady=4)
        self.engine_label = ctk.CTkLabel(efr, text=t("engine_version", v="…"), font=self.font(13), anchor="w")
        self.engine_label.pack(side="left")
        self.update_btn = ctk.CTkButton(efr, text=t("update_engine"), command=self.on_update_engine,
                                        width=170, font=self.font(13, "bold"))
        self.update_btn.pack(side="left", padx=16)
        self.engine_age = ctk.CTkLabel(page, text="", font=self.font(12), anchor="w")
        self.engine_age.pack(fill="x", padx=14)
        comps = [("comp_ytdlp", bool(self.tools.ytdlp)), ("comp_deno", bool(self.tools.deno or self.tools.node)),
                 ("comp_ffmpeg", bool(self.tools.ffmpeg_dir))]
        ctk.CTkLabel(page, text=t("components"), font=self.font(13, "bold"), anchor="w").pack(
            fill="x", padx=14, pady=(12, 2))
        for key, ok in comps:
            ctk.CTkLabel(page, text=f"{'✓' if ok else '✗'}  {t(key)} — {t('comp_found' if ok else 'comp_missing')}",
                         font=self.font(12), text_color=("#1E7B34", "#5CC97B") if ok else ("#B3261E", "#FF8A80"),
                         anchor="w").pack(fill="x", padx=24)
        ctk.CTkLabel(page, text=f"{t('save_settings_note')}  ·  v{__version__}", font=self.font(11),
                     text_color=("gray45", "gray60"), anchor="w").pack(fill="x", padx=14, pady=(18, 12))
        if getattr(self, "_engine_text", None):
            self._show_engine(*self._engine_text)

    def _build_help(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        box = ctk.CTkTextbox(tab, font=self.font(14), wrap="word", corner_radius=10)
        box.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        box.insert("1.0", t("help_text"))
        box.configure(state="disabled")

    def _build_statusbar(self) -> None:
        bar = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray86", "gray17"))
        bar.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        bar.grid_columnconfigure(1, weight=1)
        self.progress = ctk.CTkProgressBar(bar, width=220, height=12)
        self.progress.set(0)
        self.progress.grid(row=0, column=0, padx=(16, 0), pady=10)
        if not self.busy:
            self.progress.grid_remove()  # shown only while something runs
        self.status = ctk.CTkLabel(bar, text=t("ready"), font=self.font(12), anchor="w")
        self.status.grid(row=0, column=1, sticky="ew", padx=(16, 8))
        self.result_btn = ctk.CTkButton(bar, text=t("open_result"), width=130, height=28, font=self.font(12, "bold"),
                                        command=self.open_result)
        self.folder_btn = ctk.CTkButton(bar, text=t("open_folder"), width=110, height=28, font=self.font(12),
                                        fg_color="transparent", border_width=1, text_color=("gray10", "gray90"),
                                        command=self.open_out_dir)
        self.folder_btn.grid(row=0, column=3, padx=4)
        self.details_btn = ctk.CTkButton(bar, text=t("details"), width=90, height=28, font=self.font(12),
                                         fg_color="transparent", border_width=1, text_color=("gray10", "gray90"),
                                         command=self.toggle_details)
        self.details_btn.grid(row=0, column=4, padx=(4, 16))
        self.log_box = ctk.CTkTextbox(self, height=150, font=ctk.CTkFont(family="Consolas", size=11),
                                      wrap="none", corner_radius=0)
        self.log_box.insert("end", "\n".join(self.log_lines[-2000:]) + ("\n" if self.log_lines else ""))
        self.log_box.configure(state="disabled")
        self.details_shown = False
        if self.last_outputs and any(p.endswith(".docx") for p in self.last_outputs):
            self.result_btn.grid(row=0, column=2, padx=4)

    def _style_tree(self) -> None:
        dark = ctk.get_appearance_mode() == "Dark"
        style = ttk.Style(self)
        style.theme_use("clam")
        bg, fg, head, line = ("#242424", "#E6E6E6", "#2E2E2E", "#3A3A3A") if dark else (
            "#FFFFFF", "#1A1A1A", "#EDEDED", "#D6D6D6")
        style.configure("YS.Treeview", background=bg, fieldbackground=bg, foreground=fg, rowheight=28,
                        font=("Segoe UI", 10), borderwidth=0, relief="flat")
        style.configure("YS.Treeview.Heading", background=head, foreground=fg, font=("Segoe UI", 10, "bold"),
                        relief="flat", borderwidth=0, padding=(6, 4))
        style.map("YS.Treeview.Heading", background=[("active", line)])
        sel = ACCENT[1] if dark else "#F6D5D3"
        style.map("YS.Treeview", background=[("selected", sel)],
                  foreground=[("selected", "#FFFFFF" if dark else "#1A1A1A")])
        for tree in (getattr(self, "tree", None), getattr(self, "ftree", None)):
            if tree is None:
                continue
            tree.tag_configure("ok", foreground="#5CC97B" if dark else "#1E7B34")
            tree.tag_configure("bad", foreground="#FF8A80" if dark else "#B3261E")
            tree.tag_configure("warn", foreground="#FFB74D" if dark else "#9A5B00")
            tree.tag_configure("busy", foreground="#80B3FF" if dark else "#1A5FB4")
            tree.tag_configure("off", foreground="gray55")
            tree.master.configure(bg=bg)

    # ------------------------------------------------------------ list handling

    def refresh_tree(self) -> None:
        """Redraw the video list (respecting the filter)."""
        tree = getattr(self, "tree", None)
        if tree is None:
            return
        tree.delete(*tree.get_children())
        needle = self.filter_entry.get().strip().casefold() if hasattr(self, "filter_entry") else ""
        for n, e in enumerate(self.entries, 1):
            if needle and needle not in e.title.casefold() and needle not in e.source.casefold():
                continue
            self._insert_row(n, e)
        self._update_count()
        if self.entries:
            self.empty_hint.place_forget()
        else:
            self.empty_hint.place(relx=0.5, rely=0.5, anchor="center")

    def _row_values(self, n: int, e: Entry) -> tuple:
        status, detail = self.status_by_id.get(e.id, ("pending", ""))
        return (n, e.title, format_duration(e.duration), e.source, self._status_text(status, detail))

    def _insert_row(self, n: int, e: Entry) -> None:
        status, _ = self.status_by_id.get(e.id, ("pending", ""))
        tags = [STATUS_TAGS.get(status, "")]
        if e.id not in self.checked:
            tags.append("off")
        self.tree.insert("", "end", iid=e.id, values=self._row_values(n, e), tags=tags,
                         image=self.box_on if e.id in self.checked else self.box_off)

    def _update_row(self, vid: str) -> None:
        if not self.tree.exists(vid):
            return
        n = next((i for i, e in enumerate(self.entries, 1) if e.id == vid), 0)
        e = self.entries[n - 1]
        status, _ = self.status_by_id.get(vid, ("pending", ""))
        tags = [STATUS_TAGS.get(status, "")]
        if vid not in self.checked:
            tags.append("off")
        self.tree.item(vid, values=self._row_values(n, e), tags=tags,
                       image=self.box_on if vid in self.checked else self.box_off)

    def _status_text(self, status: str, detail) -> str:
        if status == "pending":
            return ""
        if status == "done":
            return t("st_done") + (f" ({detail})" if detail else "")
        if status == "error":
            return f"{t('st_error')}: {t('err_' + str(detail or 'unknown'))}"
        if status == "no_captions":
            langs = ", ".join(detail) if isinstance(detail, list) else ""
            return t("st_no_captions") + (f" · {t('available_langs', langs=langs)}" if langs else "")
        if status == "working":
            return f"{t('st_working')} {detail or ''}".strip()
        return t(f"st_{status}")

    def _update_count(self) -> None:
        self.count_label.configure(text=t("n_selected", sel=len(self.checked & {e.id for e in self.entries}),
                                          n=len(self.entries)))

    def on_tree_click(self, event) -> str | None:
        if self.tree.identify_region(event.x, event.y) == "heading":
            if self.tree.identify_column(event.x) == "#0":
                all_on = all(e.id in self.checked for e in self.entries)
                self.set_all(not all_on)
            return None
        if self.tree.identify_column(event.x) == "#0":
            row = self.tree.identify_row(event.y)
            if row:
                self.toggle_rows([row])
                return "break"
        return None

    def on_tree_double(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if row and self.tree.identify_column(event.x) != "#0":
            webbrowser.open(f"https://www.youtube.com/watch?v={row}")

    def on_tree_menu(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if not row:
            return
        if row not in self.tree.selection():
            self.tree.selection_set(row)
        rows = list(self.tree.selection())
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=t("menu_open"), command=lambda: webbrowser.open(
            f"https://www.youtube.com/watch?v={row}"))
        menu.add_command(label=t("menu_copy"), command=lambda: self._copy(
            "\n".join(f"https://www.youtube.com/watch?v={r}" for r in rows)))
        menu.add_separator()
        menu.add_command(label=t("menu_tick_sel"), command=lambda: self._set_rows(rows, True))
        menu.add_command(label=t("menu_untick_sel"), command=lambda: self._set_rows(rows, False))
        menu.add_separator()
        menu.add_command(label=t("menu_remove"), command=lambda: self.remove_rows(rows))
        menu.tk_popup(event.x_root, event.y_root)

    def _copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)

    def toggle_rows(self, rows) -> None:
        for r in rows:
            if r in self.checked:
                self.checked.discard(r)
            else:
                self.checked.add(r)
            self._update_row(r)
        self._update_count()

    def _set_rows(self, rows, on: bool) -> None:
        for r in rows:
            (self.checked.add if on else self.checked.discard)(r)
            self._update_row(r)
        self._update_count()

    def set_all(self, on: bool) -> None:
        """Tick or untick every visible row."""
        self._set_rows(list(self.tree.get_children()), on)

    def remove_rows(self, rows) -> None:
        if self.busy:
            return
        drop = set(rows)
        self.entries = [e for e in self.entries if e.id not in drop]
        self.checked -= drop
        self.refresh_tree()

    def tick_failed(self) -> None:
        """Tick only the videos that failed or were not reached, to run them again."""
        retry = {e.id for e in self.entries
                 if self.status_by_id.get(e.id, ("pending", ""))[0] in ("error", "pending", "working")}
        if retry:
            self.checked = retry
            self.refresh_tree()

    def remove_unticked(self) -> None:
        if self.busy:
            return
        self.entries = [e for e in self.entries if e.id in self.checked]
        self.refresh_tree()

    def clear_list(self) -> None:
        if self.busy or not self.entries:
            return
        if messagebox.askyesno(t("app_title"), t("confirm_clear"), parent=self):
            self.entries.clear()
            self.checked.clear()
            self.status_by_id.clear()
            self.refresh_tree()

    def export_links(self) -> None:
        if not self.entries:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".txt", initialfile="links.txt",
                                            filetypes=[("Text", "*.txt")])
        if path:
            ticked = [e for e in self.entries if e.id in self.checked] or self.entries
            Path(path).write_text("\n".join(f"{e.url}  # {e.title}" for e in ticked) + "\n", encoding="utf-8")

    def add_entries(self, new: list[Entry]) -> int:
        """Append entries that are not in the list yet; returns how many were skipped."""
        have = {e.id for e in self.entries}
        skipped = 0
        for e in new:
            if e.id in have:
                skipped += 1
                continue
            have.add(e.id)
            self._seq = getattr(self, "_seq", 0) + 1
            e.extra["seq"] = self._seq  # remembers the original list order
            self.entries.append(e)
            self.checked.add(e.id)
        self.apply_order()
        return skipped

    def apply_order(self) -> None:
        """Show the list in the file order chosen in step 3 (same rule as the job)."""
        how = self.v["file_order"].get() if "file_order" in self.v else "list"
        if how in ("az", "za"):
            self.entries.sort(key=lambda e: title_sort_key(e.title), reverse=(how == "za"))
        else:
            self.entries.sort(key=lambda e: e.extra.get("seq", 0))
        self.refresh_tree()

    def on_order(self, how: str) -> None:
        if self.busy:
            self.set_status(t("busy"))
            return
        self.v["file_order"].set(how)
        self.order_seg.set(self.order_labels.get(how, self.order_labels["list"]))
        self.apply_order()

    # ------------------------------------------------------------ step 1 actions

    def on_paste(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        current = self.links_box.get("1.0", "end").strip()
        self.links_box.insert("end", ("\n" if current else "") + text.strip() + "\n")

    def on_open_txt(self) -> None:
        path = filedialog.askopenfilename(parent=self, title=t("pick_txt"),
                                          filetypes=[("Text", "*.txt *.csv *.md"), ("All", "*.*")])
        if path:
            text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
            current = self.links_box.get("1.0", "end").strip()
            self.links_box.insert("end", ("\n" if current else "") + text.strip() + "\n")

    def on_clear_box(self) -> None:
        self.links_box.delete("1.0", "end")

    def on_add_links(self) -> None:
        if self.busy:
            self.set_status(t("busy"))
            return
        text = self.links_box.get("1.0", "end")
        targets, searches = parse_input(text)
        if not targets and not searches:
            self.add_status.configure(text=t("nothing_found"))
            return
        self.busy = True
        self.add_btn.configure(state="disabled")
        self.progress.grid()
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.set_status(t("loading_links"))
        count = max(1, self.int_var("search_count", 20))
        limit = max(0, self.int_var("list_limit", 0))
        threading.Thread(target=self._resolve_links, args=(targets, searches, count, limit), daemon=True).start()

    def _resolve_links(self, targets, searches, count: int, limit: int) -> None:
        jobs = [("target", tg) for tg in targets] + [("search", q) for q in searches]
        results: list[list[Entry]] = [[] for _ in jobs]
        failures: list[str] = []

        def work(i: int, job) -> None:
            kind, item = job
            try:
                if kind == "target" and item.is_video:
                    found = oembed_title(item.label)
                    title, channel = found if found else (item.label, "")
                    results[i] = [Entry(item.label, title, item.url, channel=channel)]
                elif kind == "target":
                    self.post("status", text=t("loading_one", what=item.url))
                    results[i] = self.engine.list_entries(item.url, limit=limit)
                else:
                    self.post("status", text=t("loading_one", what=f"🔍 {item}"))
                    results[i] = self.engine.list_entries(search_url(item, count), source=f"🔍 {item}")
            except (EngineError, Cancelled, OSError) as exc:
                what = item.url if kind == "target" else item
                failures.append(t("list_failed", what=what, why=t("err_" + str(exc)) if str(exc) else ""))
                self.post("log", line=f"list failed: {what}: {exc}")

        with ThreadPoolExecutor(max_workers=6) as pool:
            for i, job in enumerate(jobs):
                pool.submit(work, i, job)
        flat = [e for group in results for e in group]
        self.post("entries", entries=flat, failures=failures)

    # ------------------------------------------------------------ download

    def _job_options(self) -> JobOptions:
        self._save_settings()
        s = self.s
        labels = {
            "contents": t("doc_label_contents"), "created": t("doc_label_created"),
            "videos": t("doc_label_videos"), "empty": t("doc_label_empty"),
            "reason_no_captions": t("reason_no_captions"), "reason_error": t("reason_error"),
        }
        doc = DocOptions(contents=s.doc_contents, page_breaks=s.doc_breaks, show_info=s.doc_info,
                         numbered=s.doc_numbered, labels=labels)
        return JobOptions(
            out_dir=Path(s.out_dir or settings_mod.default_out_dir()),
            want_transcript=s.want_transcript, want_video=s.want_video, want_audio=s.want_audio,
            want_thumbnail=s.want_thumbnail, language=s.language, fallback_original=s.fallback_original,
            allow_auto=s.allow_auto, layout=s.layout, timestamps=s.timestamps, remove_rolling=s.remove_rolling,
            remove_all_repeats=s.remove_all_repeats, remove_tags=s.remove_tags, save_docx=s.save_docx,
            save_txt=s.save_txt, save_srt=s.save_srt, save_combined_txt=s.save_combined_txt, save_csv=s.save_csv,
            output_name=s.output_name, docx=doc, video_quality=s.video_quality, numbered=s.numbered,
            order=s.file_order if s.file_order in ("list", "az", "za") else "list",
            reuse_cache=s.reuse_cache, delay=max(0.0, float(s.delay)), workers=max(1, min(4, int(s.workers))),
        )

    def on_start(self) -> None:
        if self.busy:
            if messagebox.askyesno(t("app_title"), t("confirm_stop"), parent=self):
                self.cancel.set()
                self.start_btn.configure(state="disabled")
            return
        chosen = [e for e in self.entries if e.id in self.checked]
        if not chosen:
            if self.links_box.get("1.0", "end").strip():
                self.on_add_links()
                return
            messagebox.showinfo(t("app_title"), t("nothing_ticked"), parent=self)
            return
        opt = self._job_options()
        if not (opt.want_transcript or opt.want_video or opt.want_audio or opt.want_thumbnail):
            messagebox.showinfo(t("app_title"), t("nothing_wanted"), parent=self)
            return
        if opt.want_transcript and not (opt.save_docx or opt.save_txt or opt.save_srt or opt.save_combined_txt):
            messagebox.showinfo(t("app_title"), t("no_output_format"), parent=self)
            return
        if (opt.want_video or opt.want_audio) and not self.tools.ffmpeg_dir:
            messagebox.showwarning(t("app_title"), t("need_ffmpeg"), parent=self)
            return
        for e in chosen:
            self.status_by_id[e.id] = ("pending", "")
        self.refresh_tree()
        self.result_btn.grid_forget()
        self.busy = True
        self.cancel.clear()
        self.start_btn.configure(text="■  " + t("stop"), fg_color=("gray40", "gray30"),
                                 hover_color=("gray30", "gray20"))
        self.progress.grid()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.set_status(t("working"))
        self.job_entries = chosen
        self.job_started = time.monotonic()

        def emit(kind: str, **data) -> None:
            self.post(f"job_{kind}", **data)

        def worker() -> None:
            job = DownloadJob(self.engine, chosen, opt, emit, self.cancel)
            try:
                job.run()
            except Cancelled:
                pass
            except Exception as exc:  # noqa: BLE001
                self.post("log", line=f"{type(exc).__name__}: {exc}")
                self.post("job_done", counts={}, outputs=[], total=0, cancelled=True, out_dir=str(opt.out_dir))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------ files tab actions

    def refresh_files(self) -> None:
        tree = getattr(self, "ftree", None)
        if tree is None:
            return
        tree.delete(*tree.get_children())
        for n, p in enumerate(self.files, 1):
            tree.insert("", "end", iid=str(n - 1), values=(n, p.name, str(p.parent)))

    def _add_paths(self, paths: list[Path]) -> None:
        have = {p.resolve() for p in self.files}
        for p in paths:
            if p.suffix.lower() in (".srt", ".vtt", ".txt") and p.resolve() not in have:
                self.files.append(p)
                have.add(p.resolve())
        self.on_sort_files(self.s.files_sort, save=False)

    def on_add_files(self) -> None:
        names = filedialog.askopenfilenames(parent=self, filetypes=[("Captions", "*.srt *.vtt *.txt"), ("All", "*.*")])
        self._add_paths([Path(n) for n in names])

    def on_add_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self)
        if folder:
            self._add_paths(sorted(Path(folder).iterdir()))

    def on_sort_files(self, how: str, save: bool = True) -> None:
        if save:
            self.v["files_sort"].set(how)
        if how == "name":
            self.files.sort(key=lambda p: natural_key(p.name))
        elif how == "date":
            self.files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0)
        self.refresh_files()

    def on_move_files(self, step: int) -> None:
        sel = sorted(int(i) for i in self.ftree.selection())
        if not sel:
            return
        order = sel if step < 0 else list(reversed(sel))
        for i in order:
            j = i + step
            if 0 <= j < len(self.files):
                self.files[i], self.files[j] = self.files[j], self.files[i]
        self.refresh_files()
        self.ftree.selection_set([str(min(max(i + step, 0), len(self.files) - 1)) for i in sel])

    def on_remove_files(self) -> None:
        drop = {int(i) for i in self.ftree.selection()}
        self.files = [p for n, p in enumerate(self.files) if n not in drop]
        self.refresh_files()

    def on_clear_files(self) -> None:
        self.files.clear()
        self.refresh_files()

    def on_combine(self) -> None:
        if self.busy:
            self.set_status(t("busy"))
            return
        if not self.files:
            messagebox.showinfo(t("app_title"), t("no_files"), parent=self)
            return
        self._save_settings()
        s = self.s
        if not (s.save_docx or s.files_save_txt or s.files_save_srt):
            messagebox.showinfo(t("app_title"), t("no_output_format"), parent=self)
            return
        out = Path(s.files_out_dir or s.out_dir or settings_mod.default_out_dir())
        labels = {"contents": t("doc_label_contents"), "created": t("doc_label_created"),
                  "videos": t("doc_label_videos"), "empty": t("doc_label_empty")}
        opt = FileJobOptions(out_dir=out, layout=s.layout, timestamps=s.timestamps, remove_rolling=s.remove_rolling,
                             remove_all_repeats=s.remove_all_repeats, remove_tags=s.remove_tags,
                             save_docx=s.save_docx, save_txt=s.files_save_txt, save_srt=s.files_save_srt,
                             output_name=s.files_output_name or "Combined transcripts",
                             docx=DocOptions(contents=s.doc_contents, page_breaks=s.doc_breaks,
                                             numbered=s.doc_numbered, show_info=False, labels=labels))
        self.busy = True
        self.combine_btn.configure(state="disabled")
        self.progress.grid()
        self.progress.set(0)
        self.result_btn.grid_forget()
        files = list(self.files)

        def emit(kind: str, **data) -> None:
            self.post(f"job_{kind}", **data)

        def worker() -> None:
            try:
                out.mkdir(parents=True, exist_ok=True)
                combine_files(files, opt, emit)
            except Exception as exc:  # noqa: BLE001
                self.post("log", line=f"{type(exc).__name__}: {exc}")
                self.post("job_done", counts={}, outputs=[], total=0, cancelled=True, out_dir=str(out))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------ settings actions

    def on_theme(self, mode: str) -> None:
        self.v["theme"].set(mode)
        ctk.set_appearance_mode(mode)
        self.after(50, self._restyle)

    def _restyle(self) -> None:
        self._make_boxes()
        self._style_tree()
        self.refresh_tree()

    def on_login(self, browser: str) -> None:
        if browser == "file":
            path = filedialog.askopenfilename(parent=self, filetypes=[("cookies.txt", "*.txt"), ("All", "*.*")])
            if not path:
                return
            self.v["cookies_file"].set(path)
            self.cookie_label.configure(text=Path(path).name)
        else:
            self.cookie_label.configure(text="")
        self.v["login_browser"].set(browser)
        self._schedule_save()

    def on_caption_language(self, label: str) -> None:
        if label == t("lang_other"):
            dialog = ctk.CTkInputDialog(text=t("lang_other_prompt"), title=t("language"))
            code = (dialog.get_input() or "").strip()
            if not code:
                self.lang_menu.set(self.lang_labels[self.lang_codes.index(self.v["language"].get())])
                return
            if code not in self.lang_codes:
                self.lang_codes.append(code)
                self.lang_labels.append(code)
                self.lang_menu.configure(values=self.lang_labels + [t("lang_other")])
            self.lang_menu.set(self.lang_labels[self.lang_codes.index(code)])
            self.v["language"].set(code)
            return
        self.v["language"].set(self.lang_codes[self.lang_labels.index(label)])

    def _pick_dir(self, var: str) -> None:
        folder = filedialog.askdirectory(parent=self, title=t("pick_folder"),
                                         initialdir=self.v[var].get() or self.s.out_dir)
        if folder:
            self.v[var].set(str(Path(folder)))

    def on_browse_out(self) -> None:
        self._pick_dir("out_dir")

    def open_out_dir(self) -> None:
        folder = Path(self.v["out_dir"].get() or settings_mod.default_out_dir())
        if self.tabs.get() == self.tab_names["tab_files"] and self.v["files_out_dir"].get():
            folder = Path(self.v["files_out_dir"].get())
        folder.mkdir(parents=True, exist_ok=True)
        open_path(folder)

    def open_result(self) -> None:
        docs = [p for p in self.last_outputs if p.endswith(".docx")]
        if docs and Path(docs[-1]).exists():
            open_path(docs[-1])

    def _check_engine_async(self) -> None:
        def work() -> None:
            version = self.engine.version()
            self.post("engine", version=version)

        threading.Thread(target=work, daemon=True).start()

    def _show_engine(self, version: str, age: int | None) -> None:
        self._engine_text = (version, age)
        try:
            self.engine_label.configure(text=t("engine_version", v=version or "?"))
            if age is not None and age > 60:
                self.engine_age.configure(text=t("engine_old", days=age), text_color=("#9A5B00", "#FFB74D"))
            elif age is not None:
                self.engine_age.configure(text=t("engine_ok"), text_color=("#1E7B34", "#5CC97B"))
        except tk.TclError:
            pass

    def on_update_engine(self) -> None:
        if self.busy:
            self.set_status(t("busy"))
            return
        self.busy = True
        self.update_btn.configure(state="disabled", text=t("updating"))
        self.progress.grid()
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.set_status(t("updating"))

        def work() -> None:
            ok, _ = self.engine.update(lambda ln: self.post("log", line=ln))
            version = self.engine.version()
            self.post("updated", ok=ok, version=version)

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ events

    def set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def log(self, line: str) -> None:
        self.log_lines.append(line)
        if len(self.log_lines) > 5000:
            self.log_lines = self.log_lines[-4000:]
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line + "\n")
        if int(self.log_box.index("end-1c").split(".")[0]) > 3000:
            self.log_box.delete("1.0", "500.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def toggle_details(self) -> None:
        if self.details_shown:
            self.log_box.grid_forget()
            self.details_btn.configure(text=t("details"))
        else:
            self.log_box.grid(row=3, column=0, sticky="ew")
            self.details_btn.configure(text=t("hide_details"))
        self.details_shown = not self.details_shown

    def _drain(self) -> None:
        try:
            for _ in range(400):
                kind, data = self.events.get_nowait()
                self._handle(kind, data)
        except queue.Empty:
            pass
        self.after(100, self._drain)

    def _end_busy(self) -> None:
        self.busy = False
        self.progress.stop()
        self.progress.configure(mode="determinate")
        try:
            self.add_btn.configure(state="normal")
            self.start_btn.configure(text="▶  " + t("start"), state="normal", fg_color=ACCENT,
                                     hover_color=ACCENT_HOVER)
            self.combine_btn.configure(state="normal")
            self.update_btn.configure(state="normal", text=t("update_engine"))
        except tk.TclError:
            pass

    def _handle(self, kind: str, data: dict) -> None:
        if kind in ("log", "job_log"):
            self.log(str(data.get("line", "")))
        elif kind == "status":
            self.set_status(str(data["text"]))
        elif kind == "entries":
            skipped = self.add_entries(data["entries"])
            self._end_busy()
            self.progress.grid_remove()
            msg = t("added_n", n=len(data["entries"]) - skipped)
            if skipped:
                msg += " " + t("already_in_list", n=skipped)
            if data["failures"]:
                msg += "  " + " · ".join(data["failures"][:2])
            self.add_status.configure(text="")
            self.set_status(msg)
            if data["entries"] and not data["failures"]:
                self.links_box.delete("1.0", "end")
        elif kind == "job_row":
            entries = getattr(self, "job_entries", [])
            idx = int(data["index"])
            if idx < len(entries):
                vid = entries[idx].id
                detail = data.get("detail")
                if data["status"] == "no_captions":
                    detail = data.get("available") or []
                self.status_by_id[vid] = (str(data["status"]), detail)
                self._update_row(vid)
                if data["status"] == "working" and self.tree.exists(vid) and not detail:
                    self.tree.see(vid)
        elif kind == "job_progress":
            if data.get("value") is not None:
                self.progress.set(float(data["value"]))
            text = data.get("text")
            if text in ("rate_limited_wait", "retry_wait"):
                self.set_status(t(text))
            elif text:
                self.set_status(str(text))
            elif data.get("done"):
                self.set_status(self._eta_text(int(data["done"]), int(data["total"])))
        elif kind == "job_done":
            self._end_busy()
            counts = data.get("counts", {})
            self.last_outputs = list(data.get("outputs", []))
            if data.get("cancelled"):
                text = t("stopped")
            else:
                text = t("finished", done=counts.get("done", 0), nocap=counts.get("no_captions", 0),
                         err=counts.get("error", 0))
            if self.last_outputs:
                text += "  " + t("files_saved") + " " + ", ".join(Path(p).name for p in self.last_outputs)
                for p in self.last_outputs:
                    self.log(f"saved: {p}")
            self.set_status(text)
            if any(p.endswith(".docx") for p in self.last_outputs):
                self.result_btn.grid(row=0, column=2, padx=4)
            for e in getattr(self, "job_entries", []):
                if self.status_by_id.get(e.id, ("",))[0] == "working":
                    self.status_by_id[e.id] = ("pending", "")
                    self._update_row(e.id)
        elif kind == "engine":
            version = str(data.get("version") or "")
            self._show_engine(version, Engine.version_age_days(version))
        elif kind == "updated":
            self._end_busy()
            version = str(data.get("version") or "")
            self._show_engine(version, Engine.version_age_days(version))
            self.set_status(t("update_ok", v=version) if data.get("ok") else t("update_fail"))

    def _eta_text(self, done: int, total: int) -> str:
        """``120/428 · 3.1 s per video · about 16 min left``."""
        elapsed = time.monotonic() - getattr(self, "job_started", time.monotonic())
        text = f"{done}/{total}"
        if done >= 3 and elapsed > 1:
            per = elapsed / done
            left = per * (total - done)
            text += " · " + t("eta", per=f"{per:.1f}", left=f"{max(1, round(left / 60))}")
        return text

    def on_close(self) -> None:
        if self.busy and not messagebox.askyesno(t("app_title"), t("confirm_stop"), parent=self):
            return
        self.cancel.set()
        self.v["geometry"].set("zoomed" if self.state() == "zoomed" else self.geometry())
        self._save_settings()
        self.destroy()


def main() -> None:
    """Start the app."""
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ThriveLab.YouTubeScraper")
        except Exception:  # noqa: BLE001
            pass
    app = App()
    app.mainloop()
