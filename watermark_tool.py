"""
Watermark Tool v1.1
Nakłada powtarzający się znak wodny (45° CCW) i eksportuje do zadanej rozdzielczości.
Obsługuje zdjęcia i filmy wideo (wideo wymaga FFmpeg).
"""
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import threading
import subprocess
import tempfile
import shutil
from PIL import Image, ImageDraw, ImageFont, ImageTk

VERSION = "v1.1"

SUPPORTED_EXT       = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
SUPPORTED_VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".mts", ".m2ts", ".wmv", ".flv"}
WIN_FONTS           = "C:/Windows/Fonts/"
PROFILES_FILE       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.json")

# Suppress console window on Windows when calling FFmpeg
_PROC_FLAGS = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

_FONT_CATALOG = [
    ("Arial",           {"r": "arial.ttf",    "b": "arialbd.ttf",  "i": "ariali.ttf",   "bi": "arialbi.ttf"}),
    ("Arial Narrow",    {"r": "ARIALN.TTF",   "b": "ARIALNB.TTF",  "i": "ARIALNI.TTF",  "bi": "ARIALNBI.TTF"}),
    ("Calibri",         {"r": "calibri.ttf",  "b": "calibrib.ttf", "i": "calibrii.ttf", "bi": "calibriz.ttf"}),
    ("Cambria",         {"r": "cambria.ttc",  "b": "cambriab.ttf", "i": "cambriai.ttf", "bi": "cambriaz.ttf"}),
    ("Comic Sans MS",   {"r": "comic.ttf",    "b": "comicbd.ttf",  "i": "comic.ttf",    "bi": "comicbd.ttf"}),
    ("Courier New",     {"r": "cour.ttf",     "b": "courbd.ttf",   "i": "couri.ttf",    "bi": "courbi.ttf"}),
    ("Georgia",         {"r": "georgia.ttf",  "b": "georgiab.ttf", "i": "georgiai.ttf", "bi": "georgiaz.ttf"}),
    ("Impact",          {"r": "impact.ttf",   "b": "impact.ttf",   "i": "impact.ttf",   "bi": "impact.ttf"}),
    ("Segoe UI",        {"r": "segoeui.ttf",  "b": "segoeuib.ttf", "i": "segoeuii.ttf", "bi": "segoeuiz.ttf"}),
    ("Tahoma",          {"r": "tahoma.ttf",   "b": "tahomabd.ttf", "i": "tahoma.ttf",   "bi": "tahomabd.ttf"}),
    ("Times New Roman", {"r": "times.ttf",    "b": "timesbd.ttf",  "i": "timesi.ttf",   "bi": "timesbi.ttf"}),
    ("Trebuchet MS",    {"r": "trebuc.ttf",   "b": "trebucbd.ttf", "i": "trebucit.ttf", "bi": "trebucbi.ttf"}),
    ("Verdana",         {"r": "verdana.ttf",  "b": "verdanab.ttf", "i": "verdanai.ttf", "bi": "verdanaz.ttf"}),
]

_FALLBACK_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _build_available_fonts() -> dict:
    available = {}
    for name, variants in _FONT_CATALOG:
        regular = os.path.join(WIN_FONTS, variants["r"])
        if os.path.exists(regular):
            resolved = {}
            for key, fname in variants.items():
                path = os.path.join(WIN_FONTS, fname)
                resolved[key] = path if os.path.exists(path) else regular
            available[name] = resolved
    return available


AVAILABLE_FONTS: dict = _build_available_fonts()
FONT_NAMES: list = list(AVAILABLE_FONTS.keys()) or ["Arial"]


def _resolve_font_path(family: str, bold: bool, italic: bool) -> str:
    if family in AVAILABLE_FONTS:
        key = "bi" if bold and italic else "b" if bold else "i" if italic else "r"
        return AVAILABLE_FONTS[family][key]
    for p in _FALLBACK_PATHS:
        if os.path.exists(p):
            return p
    return ""


def load_font(family: str, size: int, bold: bool, italic: bool) -> ImageFont.FreeTypeFont:
    path = _resolve_font_path(family, bold, italic)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


# ─────────────────────────────────── profile helpers ─────────────────────────

def _load_profiles() -> dict:
    try:
        with open(PROFILES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_profiles(profiles: dict) -> None:
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────── ffmpeg helpers ──────────────────────────

def _find_ffmpeg() -> tuple:
    """Return (ffmpeg_path, ffprobe_path) or (None, None) if not found."""
    import glob

    ffmpeg  = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe

    # Explicit common install paths
    common = [
        r"C:\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin",
        r"C:\Program Files (x86)\ffmpeg\bin",
    ]
    for base in common:
        ff = os.path.join(base, "ffmpeg.exe")
        fp = os.path.join(base, "ffprobe.exe")
        if os.path.exists(ff) and os.path.exists(fp):
            return ff, fp

    # Glob search — catches versioned sub-folders (e.g. pic-time, winget packages)
    search_roots = [
        r"C:\Program Files\*\ffmpeg.exe",
        r"C:\Program Files\*\*\ffmpeg.exe",
        r"C:\Program Files\*\*\*\ffmpeg.exe",
        r"C:\Program Files (x86)\*\ffmpeg.exe",
        r"C:\Program Files (x86)\*\*\ffmpeg.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*\ffmpeg.exe"),
    ]
    for pattern in search_roots:
        for ff in glob.glob(pattern):
            fp = os.path.join(os.path.dirname(ff), "ffprobe.exe")
            if os.path.exists(fp):
                return ff, fp

    return None, None


def _get_video_dimensions(ffprobe: str, path: str) -> tuple:
    """Return (width, height) of the first video stream."""
    r = subprocess.run(
        [ffprobe, "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", path],
        capture_output=True, text=True, creationflags=_PROC_FLAGS,
    )
    parts = r.stdout.strip().split("x")
    if len(parts) != 2:
        raise ValueError(f"Nie można odczytać wymiarów wideo. ffprobe: {r.stderr.strip()}")
    return int(parts[0]), int(parts[1])


# ─────────────────────────────────── image helpers ───────────────────────────

def _draw_text_line(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    color: tuple,
    underline: bool,
) -> None:
    draw.text((x, y), text, font=font, fill=color)
    if underline:
        bb = draw.textbbox((x, y), text, font=font)
        h = bb[3] - bb[1]
        gap = max(1, h // 12)
        thickness = max(1, h // 14)
        uy = bb[3] + gap
        draw.rectangle([bb[0], uy, bb[2], uy + thickness - 1], fill=color)


def _create_stamp(
    line1: str,
    line2: str,
    font_size: int,
    opacity: int,
    font_family: str,
    bold: bool,
    italic: bool,
    underline: bool,
) -> Image.Image:
    font = load_font(font_family, font_size, bold, italic)
    pad = max(8, font_size // 4)

    dummy = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(dummy)

    def measure(text):
        bb = d.textbbox((0, 0), text, font=font)
        extra = max(2, (bb[3] - bb[1]) // 10) if underline else 0
        return bb[2] - bb[0], bb[3] - bb[1] + extra

    tw1, th1 = measure(line1)
    tw2, th2 = measure(line2)

    stamp_w = max(tw1, tw2) + pad * 2
    stamp_h = th1 + th2 + pad * 3

    tile = Image.new("RGBA", (stamp_w, stamp_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)
    color = (255, 255, 255, opacity)

    _draw_text_line(draw, pad, pad,             line1, font, color, underline)
    _draw_text_line(draw, pad, pad + th1 + pad, line2, font, color, underline)

    return tile.rotate(45, expand=True, resample=Image.BICUBIC)


def create_watermark_overlay(
    width: int,
    height: int,
    line1: str,
    line2: str,
    font_size: int,
    opacity: int,
    spacing_h: int,
    spacing_v: int,
    font_family: str = "Arial",
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
) -> Image.Image:
    stamp = _create_stamp(line1, line2, font_size, opacity, font_family, bold, italic, underline)
    sw, sh = stamp.size

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    row = 0
    y = -sh
    while y < height + sh:
        x_offset = (spacing_h // 2) * (row % 2)
        x = -sw - spacing_h + x_offset
        while x < width + sw + spacing_h:
            overlay.paste(stamp, (x, y), stamp)
            x += spacing_h
        y += spacing_v
        row += 1

    return overlay


def _calc_output_size(w: int, h: int, target: int) -> tuple:
    """Return (nw, nh) so long side equals target; both values are even."""
    if w >= h:
        nw = target
        nh = max(1, round(h * target / w))
    else:
        nh = target
        nw = max(1, round(w * target / h))
    nw = nw if nw % 2 == 0 else nw - 1
    nh = nh if nh % 2 == 0 else nh - 1
    return max(2, nw), max(2, nh)


def process_image(
    in_path: str,
    out_path: str,
    line1: str,
    line2: str,
    font_size: int,
    opacity: int,
    spacing_h: int,
    spacing_v: int,
    target_long_side: int,
    font_family: str = "Arial",
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
) -> None:
    with Image.open(in_path) as img:
        img.load()
        img_rgba = img.convert("RGBA")

    w, h = img_rgba.size
    overlay = create_watermark_overlay(
        w, h, line1, line2, font_size, opacity,
        spacing_h, spacing_v, font_family, bold, italic, underline,
    )
    watermarked = Image.alpha_composite(img_rgba, overlay)
    result = watermarked.convert("RGB")

    nw, nh = _calc_output_size(w, h, target_long_side)
    result = result.resize((nw, nh), Image.LANCZOS)
    result.save(out_path, "JPEG", quality=90, optimize=True)


def process_video(
    in_path: str,
    out_path: str,
    line1: str,
    line2: str,
    font_size: int,
    opacity: int,
    spacing_h: int,
    spacing_v: int,
    target_long_side: int,
    ffmpeg_path: str,
    ffprobe_path: str,
    font_family: str = "Arial",
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
) -> None:
    w, h = _get_video_dimensions(ffprobe_path, in_path)
    nw, nh = _calc_output_size(w, h, target_long_side)

    overlay = create_watermark_overlay(
        nw, nh, line1, line2, font_size, opacity,
        spacing_h, spacing_v, font_family, bold, italic, underline,
    )

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(tmp_fd)
    try:
        overlay.save(tmp_path, "PNG")

        cmd = [
            ffmpeg_path, "-y",
            "-i", in_path,
            "-i", tmp_path,
            "-filter_complex",
            f"[0:v]scale={nw}:{nh}:flags=lanczos[s];[s][1:v]overlay=0:0[out]",
            "-map", "[out]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-crf", "22",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            out_path,
        ]
        r = subprocess.run(
            cmd, capture_output=True, text=True, creationflags=_PROC_FLAGS,
        )
        if r.returncode != 0:
            raise RuntimeError(f"FFmpeg zakończył z błędem:\n{r.stderr[-600:]}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ─────────────────────────────────────── GUI ─────────────────────────────────

def _pct_to_alpha(pct: int) -> int:
    return max(0, min(255, int(255 * (1 - pct / 100))))


class WatermarkApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"Watermark Tool {VERSION}")
        self.root.resizable(True, False)

        self._ffmpeg  = None
        self._ffprobe = None

        self.source_path   = tk.StringVar()
        self.output_path   = tk.StringVar()
        self.wm_line1      = tk.StringVar(value="VISUALMODE")
        self.wm_line2      = tk.StringVar(value="nie do publikacji")
        self.font_size_var = tk.IntVar(value=36)
        self.spacing_h_var = tk.IntVar(value=260)
        self.spacing_v_var = tk.IntVar(value=260)
        self.opacity_pct   = tk.IntVar(value=70)
        self.export_size   = tk.IntVar(value=800)

        default_font = "Arial" if "Arial" in FONT_NAMES else (FONT_NAMES[0] if FONT_NAMES else "")
        self.font_family_var = tk.StringVar(value=default_font)
        self.bold_var        = tk.BooleanVar(value=False)
        self.italic_var      = tk.BooleanVar(value=False)
        self.underline_var   = tk.BooleanVar(value=False)

        self.profile_var  = tk.StringVar()

        self._processing = False
        self._build_ui()
        self._refresh_profile_list()

        self.status_lbl.configure(text="Szukam FFmpeg…")
        threading.Thread(target=self._detect_ffmpeg, daemon=True).start()

    def _detect_ffmpeg(self) -> None:
        self._ffmpeg, self._ffprobe = _find_ffmpeg()
        if self._ffmpeg:
            msg = "Gotowy. FFmpeg dostępny — obsługa wideo włączona."
        else:
            msg = "Gotowy. FFmpeg niedostępny — przetwarzanie wideo wyłączone."
        self.root.after(0, lambda: self.status_lbl.configure(text=msg))

    # ──────────────────────────────── UI construction ────────────────────────

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)

        # ── Profile ──
        prf = ttk.LabelFrame(self.root, text="Profile", padding=10)
        prf.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        prf.columnconfigure(0, weight=1)

        self.profile_cb = ttk.Combobox(
            prf, textvariable=self.profile_var, state="readonly"
        )
        self.profile_cb.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        btn_frame = ttk.Frame(prf)
        btn_frame.grid(row=0, column=1)
        ttk.Button(btn_frame, text="Wczytaj",      width=10, command=self._load_profile).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Zapisz jako…", width=12, command=self._save_profile).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Usuń",          width=6,  command=self._delete_profile).pack(side="left", padx=2)

        # ── Foldery ──
        ff = ttk.LabelFrame(self.root, text="Foldery", padding=10)
        ff.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        ff.columnconfigure(1, weight=1)
        self._folder_row(ff, 0, "Folder źródłowy:", self.source_path)
        self._folder_row(ff, 1, "Folder docelowy:", self.output_path)

        # ── Tekst znaku wodnego ──
        wf = ttk.LabelFrame(self.root, text="Tekst znaku wodnego", padding=10)
        wf.grid(row=2, column=0, sticky="ew", padx=12, pady=4)
        wf.columnconfigure(1, weight=1)
        ttk.Label(wf, text="Linia 1:").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(wf, textvariable=self.wm_line1).grid(row=0, column=1, columnspan=3, sticky="ew", padx=8)
        ttk.Label(wf, text="Linia 2:").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(wf, textvariable=self.wm_line2).grid(row=1, column=1, columnspan=3, sticky="ew", padx=8)

        # ── Czcionka ──
        tf = ttk.LabelFrame(self.root, text="Czcionka", padding=10)
        tf.grid(row=3, column=0, sticky="ew", padx=12, pady=4)
        tf.columnconfigure(1, weight=1)
        ttk.Label(tf, text="Rodzina:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(
            tf, textvariable=self.font_family_var,
            values=FONT_NAMES, state="readonly", width=22,
        ).grid(row=0, column=1, sticky="w", padx=8)
        style_frame = ttk.Frame(tf)
        style_frame.grid(row=0, column=2, sticky="e", padx=(12, 0))
        ttk.Checkbutton(style_frame, text="Pogrubienie",  variable=self.bold_var).pack(side="left", padx=4)
        ttk.Checkbutton(style_frame, text="Kursywa",      variable=self.italic_var).pack(side="left", padx=4)
        ttk.Checkbutton(style_frame, text="Podkreślenie", variable=self.underline_var).pack(side="left", padx=4)

        # ── Ustawienia znaku wodnego ──
        sf = ttk.LabelFrame(self.root, text="Ustawienia znaku wodnego", padding=10)
        sf.grid(row=4, column=0, sticky="ew", padx=12, pady=4)
        sf.columnconfigure(1, weight=1)
        self._slider_row(sf, 0, "Rozmiar czcionki:",  self.font_size_var,   8,  300, suffix="px")
        self._slider_row(sf, 1, "Odstęp poziomy:",    self.spacing_h_var,  80, 2000, suffix="px")
        self._slider_row(sf, 2, "Odstęp pionowy:",    self.spacing_v_var,  80, 2000, suffix="px")
        self._slider_row(sf, 3, "Przezroczystość:",   self.opacity_pct,     0,  100, suffix="%")

        # ── Eksport ──
        ef = ttk.LabelFrame(self.root, text="Eksport", padding=10)
        ef.grid(row=5, column=0, sticky="ew", padx=12, pady=4)
        ef.columnconfigure(1, weight=1)
        ttk.Label(ef, text="Długi bok (px):").grid(row=0, column=0, sticky="w")
        ttk.Entry(ef, textvariable=self.export_size, width=7).grid(
            row=0, column=1, sticky="w", padx=8
        )

        # ── Przyciski ──
        bf = ttk.Frame(self.root)
        bf.grid(row=6, column=0, sticky="w", padx=12, pady=8)
        self.process_btn = ttk.Button(
            bf, text="▶  Przetwórz pliki", command=self.start_processing
        )
        self.process_btn.pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="Podgląd znaku wodnego", command=self.show_preview).pack(side="left")

        # ── Postęp ──
        pgf = ttk.Frame(self.root)
        pgf.grid(row=7, column=0, sticky="ew", padx=12, pady=(0, 12))
        pgf.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(pgf, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew")
        self.status_lbl = ttk.Label(pgf, text="Gotowy.", anchor="w")
        self.status_lbl.grid(row=1, column=0, sticky="w", pady=(2, 0))

    def _folder_row(self, parent, row: int, label: str, var: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=6)
        ttk.Button(
            parent, text="Przeglądaj…", width=11,
            command=lambda v=var: self._browse(v),
        ).grid(row=row, column=2)

    def _slider_row(
        self, parent, row: int, label: str, var: tk.IntVar,
        from_: int, to: int, suffix: str = "",
    ) -> ttk.Label:
        ttk.Label(parent, text=label).grid(row=row * 2, column=0, sticky="w", pady=(6, 0))

        val_lbl = ttk.Label(parent, text=f"{var.get()}{suffix}", width=12, anchor="e")
        val_lbl.grid(row=row * 2, column=2, sticky="e")

        ttk.Scale(
            parent, from_=from_, to=to, variable=var, orient="horizontal",
            command=lambda v, lbl=val_lbl, s=suffix: lbl.config(text=f"{int(float(v))}{s}"),
        ).grid(row=row * 2 + 1, column=0, columnspan=3, sticky="ew", pady=(0, 2))

        return val_lbl

    # ──────────────────────────────── profile logic ──────────────────────────

    def _get_current_settings(self) -> dict:
        return {
            "line1":       self.wm_line1.get(),
            "line2":       self.wm_line2.get(),
            "font_family": self.font_family_var.get(),
            "bold":        self.bold_var.get(),
            "italic":      self.italic_var.get(),
            "underline":   self.underline_var.get(),
            "font_size":   int(self.font_size_var.get()),
            "spacing_h":   int(self.spacing_h_var.get()),
            "spacing_v":   int(self.spacing_v_var.get()),
            "opacity_pct": int(self.opacity_pct.get()),
            "export_size": int(self.export_size.get()),
            "source_path": self.source_path.get(),
            "output_path": self.output_path.get(),
        }

    def _apply_settings(self, data: dict) -> None:
        setters = {
            "line1":       lambda v: self.wm_line1.set(v),
            "line2":       lambda v: self.wm_line2.set(v),
            "font_family": lambda v: self.font_family_var.set(v) if v in FONT_NAMES else None,
            "bold":        lambda v: self.bold_var.set(bool(v)),
            "italic":      lambda v: self.italic_var.set(bool(v)),
            "underline":   lambda v: self.underline_var.set(bool(v)),
            "font_size":   lambda v: self.font_size_var.set(int(v)),
            "spacing_h":   lambda v: self.spacing_h_var.set(int(v)),
            "spacing_v":   lambda v: self.spacing_v_var.set(int(v)),
            "opacity_pct": lambda v: self.opacity_pct.set(int(v)),
            "export_size": lambda v: self.export_size.set(int(v)),
            "source_path": lambda v: self.source_path.set(v),
            "output_path": lambda v: self.output_path.set(v),
        }
        for key, setter in setters.items():
            if key in data:
                try:
                    setter(data[key])
                except Exception:
                    pass

    def _refresh_profile_list(self) -> None:
        profiles = _load_profiles()
        names = sorted(profiles.keys())
        self.profile_cb["values"] = names
        if names and not self.profile_var.get():
            self.profile_var.set(names[0])

    def _save_profile(self) -> None:
        name = simpledialog.askstring(
            "Zapisz profil",
            "Podaj nazwę profilu:",
            initialvalue=self.profile_var.get(),
            parent=self.root,
        )
        if not name or not name.strip():
            return
        name = name.strip()
        profiles = _load_profiles()
        profiles[name] = self._get_current_settings()
        _save_profiles(profiles)
        self._refresh_profile_list()
        self.profile_var.set(name)
        self.status_lbl.configure(text=f"Profil '{name}' zapisany.")

    def _load_profile(self) -> None:
        name = self.profile_var.get()
        if not name:
            messagebox.showinfo("Brak wyboru", "Wybierz profil z listy.")
            return
        profiles = _load_profiles()
        if name not in profiles:
            messagebox.showerror("Błąd", f"Profil '{name}' nie istnieje.")
            self._refresh_profile_list()
            return
        self._apply_settings(profiles[name])
        self.status_lbl.configure(text=f"Wczytano profil '{name}'.")

    def _delete_profile(self) -> None:
        name = self.profile_var.get()
        if not name:
            messagebox.showinfo("Brak wyboru", "Wybierz profil z listy.")
            return
        if not messagebox.askyesno("Usuń profil", f"Usunąć profil '{name}'?", parent=self.root):
            return
        profiles = _load_profiles()
        profiles.pop(name, None)
        _save_profiles(profiles)
        self.profile_var.set("")
        self._refresh_profile_list()
        self.status_lbl.configure(text=f"Profil '{name}' usunięty.")

    # ──────────────────────────────── overwrite dialog ───────────────────────

    def _ask_overwrite(self, filename: str) -> str:
        """
        Show per-file overwrite dialog. Returns one of:
        'yes', 'yes_all', 'no', 'no_all', 'cancel'
        """
        result = ["cancel"]

        dlg = tk.Toplevel(self.root)
        dlg.title("Plik już istnieje")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(
            dlg,
            text=f"Plik już istnieje w folderze docelowym:\n\n{filename}\n\nNadpisać?",
            justify="center",
            padding=(20, 16),
        ).pack()

        bf = ttk.Frame(dlg, padding=(12, 4, 12, 16))
        bf.pack()

        def pick(val):
            result[0] = val
            dlg.destroy()

        ttk.Button(bf, text="Tak",                width=8,  command=lambda: pick("yes")).grid(    row=0, column=0, padx=3)
        ttk.Button(bf, text="Tak dla wszystkich", width=18, command=lambda: pick("yes_all")).grid(row=0, column=1, padx=3)
        ttk.Button(bf, text="Nie",                width=8,  command=lambda: pick("no")).grid(     row=0, column=2, padx=3)
        ttk.Button(bf, text="Nie dla wszystkich", width=18, command=lambda: pick("no_all")).grid( row=0, column=3, padx=3)
        ttk.Button(bf, text="Anuluj",             width=8,  command=lambda: pick("cancel")).grid( row=0, column=4, padx=3)

        dlg.protocol("WM_DELETE_WINDOW", lambda: pick("cancel"))
        self.root.wait_window(dlg)
        return result[0]

    def _check_overwrites(
        self, dst: str, image_files: list, video_files: list
    ):
        """
        Check which output files already exist and ask the user what to do.
        Returns (image_files, video_files) with skipped files removed,
        or None if the user cancelled.
        """
        conflicts = []
        for fname in image_files:
            out = os.path.join(dst, os.path.splitext(fname)[0] + ".jpg")
            if os.path.exists(out):
                conflicts.append(fname)
        for fname in video_files:
            out = os.path.join(dst, os.path.splitext(fname)[0] + ".mp4")
            if os.path.exists(out):
                conflicts.append(fname)

        if not conflicts:
            return image_files, video_files

        skip = set()
        overwrite_all = False
        skip_all = False

        for fname in conflicts:
            if overwrite_all:
                break
            if skip_all:
                skip.add(fname)
                continue

            ans = self._ask_overwrite(fname)
            if ans == "yes":
                pass
            elif ans == "yes_all":
                overwrite_all = True
            elif ans == "no":
                skip.add(fname)
            elif ans == "no_all":
                skip.add(fname)
                skip_all = True
            else:  # cancel
                return None

        return (
            [f for f in image_files if f not in skip],
            [f for f in video_files if f not in skip],
        )

    # ──────────────────────────────── actions ────────────────────────────────

    def _browse(self, var: tk.StringVar) -> None:
        folder = filedialog.askdirectory(title="Wybierz folder")
        if folder:
            var.set(folder)

    def _wm_params(self) -> dict:
        return dict(
            line1=self.wm_line1.get(),
            line2=self.wm_line2.get(),
            font_size=int(self.font_size_var.get()),
            opacity=_pct_to_alpha(int(self.opacity_pct.get())),
            spacing_h=int(self.spacing_h_var.get()),
            spacing_v=int(self.spacing_v_var.get()),
            font_family=self.font_family_var.get(),
            bold=self.bold_var.get(),
            italic=self.italic_var.get(),
            underline=self.underline_var.get(),
        )

    def start_processing(self) -> None:
        if self._processing:
            return

        src = self.source_path.get().strip()
        dst = self.output_path.get().strip()

        if not src or not os.path.isdir(src):
            messagebox.showerror("Błąd", "Podaj prawidłowy folder źródłowy.")
            return
        if not dst:
            messagebox.showerror("Błąd", "Podaj folder docelowy.")
            return
        try:
            target = int(self.export_size.get())
            if not (100 <= target <= 20000):
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showerror("Błąd", "Rozmiar eksportu musi być liczbą od 100 do 20000 px.")
            return

        all_files    = os.listdir(src)
        image_files  = [f for f in all_files if os.path.splitext(f.lower())[1] in SUPPORTED_EXT]
        video_files  = [f for f in all_files if os.path.splitext(f.lower())[1] in SUPPORTED_VIDEO_EXT]

        if not image_files and not video_files:
            messagebox.showinfo(
                "Brak plików",
                "W folderze źródłowym nie znaleziono obsługiwanych plików.\n"
                "Zdjęcia: JPG, JPEG, PNG, TIF, TIFF, BMP, WEBP\n"
                "Wideo: MP4, MOV, AVI, MKV, MTS, M2TS, WMV, FLV",
            )
            return

        if video_files and not self._ffmpeg:
            answer = messagebox.askyesno(
                "Brak FFmpeg",
                f"Znaleziono {len(video_files)} plik(ów) wideo, ale FFmpeg nie jest dostępny.\n"
                "Pliki wideo zostaną pominięte.\n\n"
                "Czy kontynuować przetwarzanie zdjęć?",
                parent=self.root,
            )
            if not answer:
                return
            video_files = []

        os.makedirs(dst, exist_ok=True)

        result = self._check_overwrites(dst, image_files, video_files)
        if result is None:
            return
        image_files, video_files = result

        if not image_files and not video_files:
            messagebox.showinfo("Brak plików", "Nie wybrano żadnych plików do przetworzenia.")
            return

        self._processing = True
        self.process_btn.configure(state="disabled")
        params = self._wm_params()
        threading.Thread(
            target=self._worker,
            args=(src, dst, target, params, image_files, video_files),
            daemon=True,
        ).start()

    def _worker(
        self,
        src: str,
        dst: str,
        target: int,
        params: dict,
        image_files: list,
        video_files: list,
    ) -> None:
        total   = len(image_files) + len(video_files)
        errors  = []
        done    = 0

        for fname in image_files:
            src_path = os.path.join(src, fname)
            dst_path = os.path.join(dst, os.path.splitext(fname)[0] + ".jpg")

            try:
                process_image(src_path, dst_path, target_long_side=target, **params)
            except Exception as exc:
                errors.append(f"{fname}: {exc}")

            done += 1
            pct = int(done / total * 100)

            def _upd(p=pct, n=fname):
                self.progress.configure(value=p)
                self.status_lbl.configure(text=f"[{p}%]  {n}")

            self.root.after(0, _upd)

        for fname in video_files:
            src_path = os.path.join(src, fname)
            dst_path = os.path.join(dst, os.path.splitext(fname)[0] + ".mp4")

            def _pre(n=fname):
                self.status_lbl.configure(text=f"Przetwarzanie wideo: {n}…")

            self.root.after(0, _pre)

            try:
                process_video(
                    src_path, dst_path,
                    target_long_side=target,
                    ffmpeg_path=self._ffmpeg,
                    ffprobe_path=self._ffprobe,
                    **params,
                )
            except Exception as exc:
                errors.append(f"{fname}: {exc}")

            done += 1
            pct = int(done / total * 100)

            def _upd_v(p=pct, n=fname):
                self.progress.configure(value=p)
                self.status_lbl.configure(text=f"[{p}%]  {n}")

            self.root.after(0, _upd_v)

        self.root.after(0, lambda: self._finish(total, errors, len(video_files)))

    def _finish(self, total: int, errors: list, video_count: int) -> None:
        self._reset()
        ok = total - len(errors)
        noun = "pliku" if total == 1 else "plików"
        if errors:
            detail = "\n".join(errors[:10])
            if len(errors) > 10:
                detail += f"\n…i {len(errors) - 10} więcej."
            messagebox.showwarning(
                "Zakończono z błędami",
                f"Przetworzono {ok} z {total} {noun}.\n\nBłędy:\n{detail}",
            )
        else:
            messagebox.showinfo("Gotowe!", f"Pomyślnie przetworzono {total} {noun}.")
        self.status_lbl.configure(text=f"Zakończono — {ok}/{total} plików.")

    def _reset(self) -> None:
        self._processing = False
        self.process_btn.configure(state="normal")
        self.progress.configure(value=0)

    # ──────────────────────────────── preview ────────────────────────────────

    def show_preview(self) -> None:
        PW, PH = 680, 460

        bg = Image.new("RGB", (PW, PH))
        d = ImageDraw.Draw(bg)

        sky_top    = (165, 205, 235)
        sky_bottom = (88,  130, 178)
        gnd_top    = (52,  78,  40)
        gnd_bottom = (28,  44,  20)
        horizon = PH // 2

        for y in range(horizon):
            t = y / horizon
            d.line([(0, y), (PW, y)], fill=(
                int(sky_top[0] + t * (sky_bottom[0] - sky_top[0])),
                int(sky_top[1] + t * (sky_bottom[1] - sky_top[1])),
                int(sky_top[2] + t * (sky_bottom[2] - sky_top[2])),
            ))
        for y in range(horizon, PH):
            t = (y - horizon) / (PH - horizon)
            d.line([(0, y), (PW, y)], fill=(
                int(gnd_top[0] + t * (gnd_bottom[0] - gnd_top[0])),
                int(gnd_top[1] + t * (gnd_bottom[1] - gnd_top[1])),
                int(gnd_top[2] + t * (gnd_bottom[2] - gnd_top[2])),
            ))

        cx, cy = PW - 70, 60
        for i in range(75, 0, -3):
            t = (i / 75) ** 2
            r = int(sky_bottom[0] + t * (220 - sky_bottom[0]))
            g = int(sky_bottom[1] + t * (235 - sky_bottom[1]))
            b = int(sky_bottom[2] + t * (250 - sky_bottom[2]))
            d.ellipse([cx - i*2, cy - i*2, cx + i*2, cy + i*2], fill=(r, g, b))

        params = self._wm_params()
        overlay = create_watermark_overlay(PW, PH, **params)
        result = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")

        win = tk.Toplevel(self.root)
        win.title("Podgląd znaku wodnego")
        win.resizable(False, False)

        photo = ImageTk.PhotoImage(result)
        label = ttk.Label(win, image=photo)
        label.image = photo
        label.pack(padx=8, pady=8)

        ttk.Button(win, text="Zamknij", command=win.destroy).pack(pady=(0, 8))


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    WatermarkApp(root)
    root.mainloop()
