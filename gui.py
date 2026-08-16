#!/usr/bin/env python
"""Desktop front end for the plate reader.

    python gui.py

Detection and OCR both run on a worker thread so the window stays responsive;
progress messages are marshalled back to the Tk thread with ``after``.
"""
from __future__ import annotations

import queue
import threading
from pathlib import Path
from tkinter import BOTH, END, LEFT, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

import cv2
import ttkbootstrap as tb
from PIL import Image, ImageTk
from ttkbootstrap.constants import DISABLED, NORMAL, PRIMARY, SUCCESS

import config
from plate_reader import PlateDetector, get_backend, read_images

PREVIEW_SIZE = (420, 150)


class PlateApp(tb.Window):
    def __init__(self) -> None:
        super().__init__(themename="superhero")
        self.title("Moroccan Licence-Plate Reader")
        self.geometry("880x620")
        self.minsize(760, 560)

        self.selected: list[Path] = []
        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self._detector: PlateDetector | None = None
        self._backend = None
        self._preview_image: ImageTk.PhotoImage | None = None

        self._build_ui()
        self.after(100, self._drain_queue)

    # ---------- layout ----------
    def _build_ui(self) -> None:
        tb.Label(
            self,
            text="Moroccan Licence-Plate Reader",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(16, 2))
        tb.Label(
            self,
            text="Runs entirely offline — no API key required",
            bootstyle="secondary",
        ).pack(pady=(0, 10))

        buttons = tb.Frame(self)
        buttons.pack(pady=6)

        self.choose_button = tb.Button(
            buttons,
            text="Choose image(s)",
            width=20,
            bootstyle=PRIMARY,
            command=self.choose_files,
        )
        self.choose_button.pack(side=LEFT, padx=5)

        self.run_button = tb.Button(
            buttons,
            text="Read plates",
            width=20,
            state=DISABLED,
            bootstyle=SUCCESS,
            command=self.start_run,
        )
        self.run_button.pack(side=LEFT, padx=5)

        self.preview = tb.Label(
            self, text="Detected plate appears here", anchor="center", relief="groove"
        )
        self.preview.pack(pady=12, ipadx=8, ipady=8)

        self.result = tb.Label(self, text="", font=("Consolas", 22, "bold"))
        self.result.pack(pady=6)

        self.progress = tb.Progressbar(self, mode="indeterminate", bootstyle=PRIMARY)
        self.progress.pack(fill="x", padx=16, pady=(0, 8))

        # tkinter's own scrolled text is used rather than ttkbootstrap's, which
        # moved between the 1.x and 2.x releases; this works on both. Its
        # colours are set by hand since it is not a themed widget.
        self.log = ScrolledText(
            self,
            height=12,
            font=("Consolas", 9),
            background="#20374c",
            foreground="#dfe3e8",
            insertbackground="#dfe3e8",
            relief="flat",
            borderwidth=0,
        )
        self.log.pack(fill=BOTH, expand=True, padx=16, pady=(0, 14))

    # ---------- actions ----------
    def choose_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select image(s)",
            initialdir=str(config.SAMPLES_DIR if config.SAMPLES_DIR.exists() else "."),
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All files", "*.*")],
        )
        if not paths:
            return
        self.selected = [Path(p) for p in paths]
        self.run_button.config(state=NORMAL)
        self.log_line(f"Selected {len(self.selected)} file(s).")
        for path in self.selected:
            self.log_line(f"  {path.name}")

    def start_run(self) -> None:
        if not self.selected:
            return
        self.set_busy(True)
        self.result.config(text="")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        try:
            if self._detector is None:
                self.messages.put(("log", "Loading detection model..."))
                self._detector = PlateDetector()
            if self._backend is None:
                self.messages.put(
                    ("log", "Loading OCR model (first run downloads it)...")
                )
                self._backend = get_backend()

            result = read_images(
                self.selected,
                detector=self._detector,
                backend=self._backend,
                progress=lambda message: self.messages.put(("log", message)),
            )
            self.messages.put(("result", result))
        except Exception as exc:  # surfaced to the user, never swallowed
            self.messages.put(("error", exc))

    # ---------- Tk-thread updates ----------
    def _drain_queue(self) -> None:
        while True:
            try:
                kind, payload = self.messages.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self.log_line(str(payload))
            elif kind == "result":
                self._show_result(payload)
            elif kind == "error":
                self.set_busy(False)
                messagebox.showerror("Error", str(payload))
                self.log_line(f"ERROR: {payload}")

        self.after(100, self._drain_queue)

    def _show_result(self, result) -> None:
        self.set_busy(False)

        best = next(
            (image.best for image in result.images if image.best is not None), None
        )
        if best is not None:
            self._show_crop(best.detection.crop)

        if result.plate:
            self.result.config(text=result.plate.text, bootstyle="success")
            self.log_line(f"==> {result.plate.text}")
            if len(result.images) > 1:
                self.log_line(
                    f"    agreement: {result.agreement}/{len(result.images)} images"
                )
        else:
            self.result.config(text="unreadable", bootstyle="danger")
            self.log_line("==> no valid plate could be read")

    def _show_crop(self, crop) -> None:
        image = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        image.thumbnail(PREVIEW_SIZE)
        self._preview_image = ImageTk.PhotoImage(image)
        self.preview.configure(image=self._preview_image, text="")

    # ---------- helpers ----------
    def log_line(self, text: str) -> None:
        self.log.insert(END, text + "\n")
        self.log.see(END)

    def set_busy(self, busy: bool) -> None:
        state = DISABLED if busy else NORMAL
        self.choose_button.config(state=state)
        self.run_button.config(state=state)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()


def main() -> None:
    if not config.MODEL_PATH.exists():
        messagebox.showerror(
            "Model not found",
            f"Expected weights at:\n{config.MODEL_PATH}\n\n"
            "Set the PLATE_MODEL environment variable to point at your .pt file.",
        )
        return
    PlateApp().mainloop()


if __name__ == "__main__":
    main()
