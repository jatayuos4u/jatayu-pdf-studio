#!/usr/bin/env python3
"""Jatayu PDF Studio prototype."""
import sys
import subprocess
import sqlite3

import fitz
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from bookmarks import Bookmarks
from file_picker import choose_pdf, pdf_copy_path
from pdf_document import PdfDocument
from reader_guide import open_reader_guide
from viewport import PAGE_MARGIN, PIXELS_PER_POINT, display_scale
from image_clipboard import copy_png
from selection import copy_text, nearest_word, page_words

PAPER = "#f6efe4"
PANEL = "#fff8ed"
INK = "#211e17"
GREEN = "#194b31"
ORANGE = "#b8430a"
BORDER = "#b8ad9d"
FONT = ("DejaVu Serif", 11)
VERSION = "v10.4"
ARTWORK = Path(__file__).resolve().parent / "artwork"


class Studio:
    def __init__(self, root):
        self.root = root
        root.report_callback_exception = self.report_callback_error
        self.bookmarks = Bookmarks()
        self.document = None
        self.index = 0
        self.dirty = False
        self.mode = "Read"
        self.display_scale = 1
        self.rendered_page = None
        self.render_job = None
        self.preview_key = None
        self.title = tk.StringVar(value="No document open")
        self.page_number = tk.StringVar()
        self.zoom = tk.StringVar(value="Fit page")
        self.zoom_readout = tk.StringVar()
        self.last_directory = Path.home()
        self.page_total = tk.StringVar(value="/ 0")
        self.fullscreen = False
        self.area_mode = False
        self.drag_start = None
        self.selected_words = []
        self.words = []
        self.word_key = None
        self.page_menu = tk.Menu(root, tearoff=False)
        self.reader_guide = None
        self.saved_pages = []
        self.saved_spots = []
        self.bookmark_target = None
        self.icons = {
            size: tk.PhotoImage(master=root, file=str(ARTWORK / f"jatayu-pdf-studio-{size}.png"))
            for size in (24, 48, 128)
        }
        root.iconphoto(True, self.icons[128], self.icons[48], self.icons[24])
        root.title(f"Jatayu PDF Studio {VERSION}")
        root.geometry("1360x880")
        root.minsize(820, 550)
        root.configure(bg=PAPER)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Control-w>", lambda event: self.close_document())
        root.bind("<Control-o>", lambda event: self.open())
        root.bind("<Control-0>", lambda event: self.fit_page())
        root.bind("<Control-Shift-S>", lambda event: self.save())
        root.bind("<Prior>", lambda event: self.go(-1))
        root.bind("<Next>", lambda event: self.go(1))

        root.bind("<F1>", lambda event: self.show_help())
        root.bind("<F11>", lambda event: self.toggle_fullscreen())
        root.bind("<Escape>", lambda event: self.escape())
        root.bind("<Control-g>", lambda event: self.jump_dialog())
        root.bind("<Control-d>", lambda event: self.bookmark_current())

        header = self.header = self.frame(root)
        header.pack(fill="x", padx=16, pady=8)
        self.label(header, image=self.icons[24]).pack(side="left", padx=(0, 7))
        self.label(header, "Jatayu PDF Studio", font=("DejaVu Serif", 15, "bold"),
                   fg=GREEN).pack(side="left")
        help_button = tk.Menubutton(
            header, text="Help ▾", bg=PANEL, fg=INK, font=FONT, padx=10, pady=5,
            relief="flat", highlightbackground=BORDER, highlightthickness=1,
            takefocus=True,
        )
        help_menu = tk.Menu(help_button, tearoff=False, bg=PANEL, fg=INK)
        help_menu.add_command(label="Reader guide and shortcuts", accelerator="F1", command=self.show_help)
        help_menu.add_command(label="About Jatayu PDF Studio", command=self.show_about)
        help_menu.add_command(label="Licence and credits", command=self.show_licence)
        help_button.configure(menu=help_menu)
        help_button.bind("<Return>", lambda event: help_menu.post(
            help_button.winfo_rootx(), help_button.winfo_rooty() + help_button.winfo_height()
        ))
        help_button.pack(side="right", padx=(6, 0))
        self.button(header, "Open PDF", self.open).pack(side="right")
        self.close_pdf_button = self.button(header, "Close PDF", self.close_document, state="disabled")
        self.close_pdf_button.pack(side="right", padx=(6, 0))
        self.button(header, "Full screen", self.toggle_fullscreen).pack(side="right", padx=6)
        self.button(header, "Bookmarks", self.show_bookmarks).pack(side="right")
        self.label(header, variable=self.title).pack(expand=True)

        workspace = self.workspace = self.frame(root)
        workspace.pack(fill="both", expand=True, padx=12)
        self.inspector = self.frame(workspace)
        self.inspector.pack(side="right", fill="y", padx=(14, 0))
        modes = self.frame(self.inspector)
        modes.pack(fill="x", pady=(16, 20))
        self.modes = {}
        for mode in ("Read", "Review"):
            button = self.button(modes, mode, lambda selected=mode: self.set_mode(selected))
            button.pack(side="left", fill="x", expand=True)
            self.modes[mode] = button
        self.tools = self.frame(self.inspector, bg=PANEL, highlightbackground=BORDER,
                                highlightthickness=1)
        self.tools.pack(fill="x")
        self.viewport = self.frame(workspace)
        self.viewport.pack(side="left", fill="both", expand=True)
        self.viewport.columnconfigure(0, weight=1)
        self.viewport.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self.viewport, bg=PAPER, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.page_scrollbar = tk.Scrollbar(
            self.viewport, orient="vertical", command=self.canvas.yview,
            width=20, bg=GREEN, activebackground=ORANGE, troughcolor="#d3c6b4",
            relief="flat", borderwidth=1, highlightthickness=0,
        )
        self.page_scrollbar.grid(row=0, column=1, sticky="ns", padx=(3, 0))
        self.canvas.configure(yscrollcommand=self.page_scrollbar.set)
        self.page_scrollbar.bind("<Button-4>", lambda event: self.scroll(-1))
        self.page_scrollbar.bind("<Button-5>", lambda event: self.scroll(1))
        self.canvas.bind("<Configure>", self.queue_render)
        self.canvas.bind("<Button-1>", self.begin_selection)
        self.canvas.bind("<B1-Motion>", self.drag_selection)
        self.canvas.bind("<ButtonRelease-1>", self.end_selection)
        self.canvas.bind("<Button-3>", self.context_menu)
        self.canvas.bind("<Control-c>", lambda event: self.copy_selection())
        self.canvas.bind("<Control-Button-4>", lambda event: self.change_zoom(1))
        self.canvas.bind("<Control-Button-5>", lambda event: self.change_zoom(-1))
        self.canvas.bind("<Control-plus>", lambda event: self.change_zoom(1))
        self.canvas.bind("<Control-equal>", lambda event: self.change_zoom(1))
        self.canvas.bind("<Control-minus>", lambda event: self.change_zoom(-1))
        self.canvas.bind("<Button-4>", lambda event: self.scroll(-1))
        self.canvas.bind("<Button-5>", lambda event: self.scroll(1))
        self.canvas.bind("<Shift-Button-4>", lambda event: self.pan(-1))
        self.canvas.bind("<Shift-Button-5>", lambda event: self.pan(1))

        self.divider = self.frame(root, bg=BORDER, height=1)
        self.divider.pack(fill="x", padx=12, pady=(8, 0))
        footer = self.footer = self.frame(root)
        footer.pack(fill="x", padx=16, pady=6)
        self.page_navigation(footer).pack(side="left")
        self.fullscreen_bar = self.frame(root)
        navigation = self.page_navigation(self.fullscreen_bar, full=True)
        self.fullscreen_bar.columnconfigure((0, 2), weight=1, uniform="sides")
        navigation.grid(row=0, column=1, pady=4)
        self.button(self.fullscreen_bar, "Bookmarks", self.show_bookmarks).grid(
            row=0, column=0, sticky="w", padx=12
        )
        self.button(navigation, "Exit full screen", self.toggle_fullscreen).pack(
            side="left", padx=(16, 0)
        )
        full_controls = self.zoom_controls(self.fullscreen_bar, compact=True)
        full_controls.grid(row=0, column=2, sticky="e", padx=12, pady=4)
        self.label(full_controls, VERSION, fg=GREEN).pack(side="left", padx=(6, 0))
        self.zoom_controls(footer).pack(side="right")
        self.filmstrip = self.frame(footer)
        self.filmstrip.pack(expand=True)
        self.thumbnails = []
        self.set_mode("Read")

    def zoom_controls(self, parent, *, compact=False):
        controls = self.frame(parent)
        zoom_box = ttk.Combobox(controls, textvariable=self.zoom, state="readonly",
                                values=("Fit page", "Fit width", "75%", "100%", "125%", "150%"),
                                width=9)
        self.button(controls, "−", lambda: self.change_zoom(-1), padx=6).pack(side="left")
        self.button(controls, "", self.zoom_dialog, textvariable=self.zoom_readout,
                    width=5, padx=3).pack(side="left")
        self.button(controls, "+", lambda: self.change_zoom(1), padx=6).pack(side="left")
        zoom_box.pack(side="left", padx=4)
        zoom_box.bind("<<ComboboxSelected>>", self.queue_render)
        if not compact:
            self.button(controls, "Fit page", self.fit_page, bg=GREEN, fg=PANEL).pack(side="left")
        return controls

    def show_help(self):
        if self.reader_guide is None or not self.reader_guide.winfo_exists():
            self.reader_guide = open_reader_guide(self.root, self.icons[48])
        else:
            self.reader_guide.deiconify()
            self.reader_guide.lift()
            self.reader_guide.focus_set()
        return "break"

    def show_about(self):
        panel = tk.Toplevel(self.root, bg=PAPER)
        panel.title("About Jatayu PDF Studio")
        panel.transient(self.root)
        panel.resizable(False, False)
        self.label(panel, image=self.icons[128]).pack(padx=32, pady=(20, 8))
        self.label(panel, "Jatayu PDF Studio", fg=GREEN,
                   font=("DejaVu Serif", 18, "bold")).pack(padx=32)
        self.label(panel, f"Prototype {VERSION}").pack(pady=(4, 10))
        self.label(panel, "A PDF reader for JatayuOS").pack()
        self.label(panel, "Creator: Anup Kumar Yadav").pack(pady=(4, 12))
        close = self.button(panel, "Close", panel.destroy, bg=GREEN, fg=PANEL)
        close.pack(pady=(0, 18))
        panel.bind("<Escape>", lambda event: panel.destroy())
        panel.wait_visibility()
        close.focus_set()
        panel.grab_set()

    def show_licence(self):
        messagebox.showinfo(
            "Licence and credits",
            "The Jatayu PDF Studio app licence is pending the creator’s selection.\n\n"
            "This prototype uses Python, Tk, and PyMuPDF. It can also use "
            "KDialog, wl-clipboard, and xclip. On Debian, installed package "
            "copyright notices are available in /usr/share/doc/<package>/copyright.",
            parent=self.root,
        )

    def page_navigation(self, parent, *, full=False):
        navigation = self.frame(parent)
        self.button(navigation, "‹ Previous" if full else "‹",
                    lambda: self.go(-1)).pack(side="left")
        page_entry = ttk.Entry(navigation, textvariable=self.page_number, width=6, justify="center")
        page_entry.pack(side="left", padx=(6, 0))
        page_entry.bind("<Return>", lambda event: self.jump(self.page_number.get()))
        self.label(navigation, variable=self.page_total).pack(side="left", padx=6)
        self.button(navigation, "Next ›" if full else "›",
                    lambda: self.go(1)).pack(side="left")
        return navigation

    def frame(self, parent, **options):
        return tk.Frame(parent, **({"bg": PAPER} | options))

    def label(self, parent, text="", variable=None, **options):
        return tk.Label(parent, text=text, textvariable=variable,
                        **({"bg": parent["bg"], "fg": INK, "font": FONT} | options))

    def button(self, parent, text, command, **options):
        return tk.Button(parent, text=text, command=command,
                         **({"bg": PANEL, "fg": INK, "font": FONT, "relief": "flat",
                             "highlightbackground": BORDER, "highlightthickness": 1,
                             "padx": 10, "pady": 5} | options))

    def set_mode(self, mode):
        self.mode = mode
        for label, button in self.modes.items():
            button.configure(bg=ORANGE if label == mode else PANEL,
                             fg=PANEL if label == mode else INK)
        for widget in self.tools.winfo_children():
            widget.destroy()
        self.tools.pack(fill="x")
        content = self.frame(self.tools, bg=PANEL, padx=10, pady=12)
        content.pack(fill="x")
        self.button(content, "Copy text", self.copy_selection).pack(fill="x", pady=3)
        self.button(content, "Copy area as image", self.start_area).pack(fill="x", pady=3)
        if mode == "Review":
            self.button(content, "Highlight selection", self.highlight_selection).pack(fill="x", pady=3)
            self.button(content, "Save a copy", self.save, bg=GREEN, fg=PANEL).pack(fill="x", pady=3)

    def report_callback_error(self, error_type, error, traceback):
        messagebox.showerror("Jatayu PDF Studio", str(error), parent=self.root)

    def open(self, path=None):
        if self.dirty and not messagebox.askyesno("Unsaved edits", "Discard the unsaved edits?"):
            return
        path = path or choose_pdf(self.root, self.last_directory)
        if not path:
            return
        candidate = None
        try:
            candidate = PdfDocument(path)
            if candidate.pdf.needs_pass:
                password = simpledialog.askstring("Password", "Enter the PDF password", show="*")
                if password is None:
                    candidate.close()
                    return
                if not candidate.pdf.authenticate(password):
                    raise ValueError("Incorrect PDF password.")
        except (ValueError, RuntimeError, OSError) as error:
            if candidate:
                candidate.close()
            messagebox.showerror("Could not open PDF", str(error))
            return
        if self.document:
            self.document.close()
        self.word_key = None
        self.document = candidate
        self.close_pdf_button.configure(state="normal")
        self.saved_pages, self.saved_spots = [], []
        self.load_bookmarks()
        self.last_directory = candidate.path.parent
        self.index = 0
        self.dirty = False
        self.title.set(candidate.path.name)
        self.preview_key = None
        self.refresh()

    def go(self, step):
        if self.document:
            self.select_page(max(0, min(len(self.document.pdf) - 1, self.index + step)))

    def select_page(self, index):
        self.index = index
        self.refresh()

    def jump(self, value):
        if not self.document:
            self.page_number.set("")
            return "break"
        count = len(self.document.pdf)
        try:
            number = int(value)
        except (ValueError, TypeError):
            number = 0
        if 1 <= number <= count:
            self.select_page(number - 1)
            self.canvas.focus_set()
        else:
            messagebox.showinfo("Go to page", f"Enter a page number from 1 to {count}.", parent=self.root)
            self.page_number.set(str(self.index + 1))
        return "break"

    def jump_dialog(self):
        if self.document:
            number = simpledialog.askinteger(
                "Go to page", f"Page (1–{len(self.document.pdf)})", parent=self.root,
                initialvalue=self.index + 1, minvalue=1, maxvalue=len(self.document.pdf),
            )
            if number is not None:
                self.jump(number)
        return "break"

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)
        if self.fullscreen:
            for widget in (self.header, self.inspector, self.footer):
                widget.pack_forget()
            self.fullscreen_bar.pack(fill="x")
        else:
            self.fullscreen_bar.pack_forget()
            self.header.pack(before=self.workspace, fill="x", padx=16, pady=8)
            self.inspector.pack(before=self.viewport, side="right", fill="y", padx=(14, 0))
            self.footer.pack(fill="x", padx=16, pady=6)
        self.canvas.focus_set()
        self.queue_render()
        return "break"

    def escape(self):
        if self.area_mode:
            self.cancel_selection()
        elif self.fullscreen:
            self.toggle_fullscreen()
        else:
            self.cancel_selection()
        return "break"

    def load_bookmarks(self):
        try:
            self.saved_pages = self.bookmarks.pages(self.document.path)
            self.saved_spots = self.bookmarks.spots(self.document.path)
        except (OSError, sqlite3.Error) as error:
            messagebox.showerror("Bookmarks", str(error), parent=self.root)

    def update_bookmarks(self, operation, *args):
        try:
            operation(self.document.path, *args)
        except (OSError, sqlite3.Error) as error:
            messagebox.showerror("Bookmarks", str(error), parent=self.root)
            return
        self.load_bookmarks()
        self.preview_key = None
        self.refresh()

    def bookmark_current(self):
        if self.document:
            self.update_bookmarks(self.bookmarks.set, self.index + 1, True)
        return "break"

    def toggle_page_bookmark(self):
        if self.rendered_page != (self.document, self.index):
            return "break"
        page = self.index + 1
        self.update_bookmarks(self.bookmarks.set, page, page not in self.saved_pages)
        return "break"

    def bookmark_spot(self, point):
        page = self.document.pdf[self.index]
        label = simpledialog.askstring(
            "Bookmark this spot", "Optional label", parent=self.root,
            initialvalue=f"{point.y / page.rect.height:.0%} down the page",
        )
        if label is not None:
            self.update_bookmarks(self.bookmarks.add_spot, self.index + 1,
                                  point.x / page.rect.width, point.y / page.rect.height,
                                  label.strip() or "Saved spot")

    def show_bookmarks(self):
        if not self.document:
            return
        self.load_bookmarks()
        panel = tk.Toplevel(self.root, bg=PAPER)
        panel.title("Bookmarks")
        panel.transient(self.root)
        panel.geometry("460x380")
        panel.minsize(350, 240)
        self.label(panel, "Bookmarks", fg=GREEN,
                   font=("DejaVu Serif", 18, "bold")).pack(anchor="w", padx=16, pady=(12, 6))
        body = self.frame(panel)
        body.pack(fill="both", expand=True, padx=16)
        rows = tk.Listbox(body, bg=PANEL, fg=INK, font=FONT, selectbackground=GREEN,
                          selectforeground=PANEL, exportselection=False)
        scroll = ttk.Scrollbar(body, orient="vertical", command=rows.yview)
        rows.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        rows.pack(side="left", fill="both", expand=True)
        entries = []

        def populate():
            entries[:] = [(number, None) for number in self.saved_pages]
            entries.extend((spot[1], spot) for spot in self.saved_spots)
            entries.sort(key=lambda entry: entry[0])
            rows.delete(0, "end")
            for number, spot in entries:
                detail = spot[4] if spot else "Whole page"
                rows.insert("end", f"Page {number}  ·  {detail}")
            if entries:
                rows.selection_set(0)
            else:
                rows.insert("end", "No bookmarks yet")

        def open_selected(event=None):
            selection = rows.curselection()
            if not selection or not entries:
                return
            number, spot = entries[selection[0]]
            if number > len(self.document.pdf):
                messagebox.showinfo("Bookmarks", "That page is no longer in this PDF.", parent=panel)
                return
            panel.destroy()
            self.bookmark_target = (spot[2], spot[3]) if spot else (None, None)
            self.jump(number)

        def remove_selected():
            selection = rows.curselection()
            if not selection or not entries:
                return
            number, spot = entries[selection[0]]
            if spot:
                self.update_bookmarks(self.bookmarks.remove_spot, spot[0])
            else:
                self.update_bookmarks(self.bookmarks.set, number, False)
            populate()

        buttons = self.frame(panel)
        buttons.pack(fill="x", padx=16, pady=10)
        self.button(buttons, "Save current page", lambda: (self.bookmark_current(), populate())).pack(side="left")
        self.button(buttons, "Remove", remove_selected).pack(side="right")
        self.button(buttons, "Go to", open_selected, bg=GREEN, fg=PANEL).pack(side="right", padx=5)
        rows.bind("<Double-Button-1>", open_selected)
        rows.bind("<Return>", open_selected)
        panel.bind("<Escape>", lambda event: panel.destroy())
        panel.grab_set()
        populate()
        rows.focus_set()

    def draw_bookmarks(self, width, height):
        right, top = self.page_x + width, self.page_y
        saved = self.index + 1 in self.saved_pages
        fold = min(24, width / 3, height / 3)
        marker = self.canvas.create_polygon(
            right - fold, top, right, top, right, top + fold,
            fill=ORANGE if saved else PANEL, outline=ORANGE if saved else BORDER,
        )
        self.canvas.tag_bind(marker, "<Button-1>", lambda event: self.toggle_page_bookmark())
        for _, page, x, y, _ in self.saved_spots:
            if page != self.index + 1:
                continue
            cy = max(top + 7, min(top + height - 7, top + y * height))
            self.canvas.create_polygon(right - 17, cy - 6, right, cy - 6, right, cy + 6,
                                       right - 17, cy + 6, right - 12, cy,
                                       fill=ORANGE, outline="")
            # A small dot identifies the exact saved spot on the page.
            cx = self.page_x + x * width
            self.canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=ORANGE, outline=PANEL)

    def zoom_dialog(self):
        if self.document:
            value = simpledialog.askinteger(
                "Zoom", "Zoom percentage (10–400)", parent=self.root,
                minvalue=10, maxvalue=400, initialvalue=int(self.zoom_readout.get().rstrip("%") or 100),
            )
            if value is not None:
                self.set_zoom(value)

    def set_zoom(self, value):
        self.zoom.set(f"{max(10, min(400, value))}%")
        self.queue_render()

    def change_zoom(self, direction):
        if self.document:
            zoom = self.zoom.get()
            current = int(zoom.rstrip("%")) if zoom.endswith("%") else round(
                100 * self.display_scale / PIXELS_PER_POINT
            )
            self.set_zoom(current + direction * 10)
        return "break"

    def fit_page(self):
        self.zoom.set("Fit page")
        self.queue_render()

    def scroll(self, direction):
        if self.canvas.yview() == (0.0, 1.0):
            self.go(direction)
        else:
            self.canvas.yview_scroll(direction * 3, "units")

    def pan(self, direction):
        self.canvas.xview_scroll(direction * 3, "units")
        return "break"

    def queue_render(self, event=None):
        if self.render_job is not None:
            self.root.after_cancel(self.render_job)
        self.render_job = self.root.after(60, self.render)

    def render(self):
        self.render_job = None
        key = (self.document, self.index)
        anchor = None
        if self.document and self.rendered_page == key:
            old_width, old_height = self.rendered_viewport
            anchor = (
                (self.canvas.canvasx(0) + old_width / 2 - self.page_x) / self.display_scale,
                (self.canvas.canvasy(0) + old_height / 2 - self.page_y) / self.display_scale,
            )
        self.cancel_selection()
        self.canvas.delete("all")
        if not self.document:
            self.canvas.create_text(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2,
                                    text="Open a PDF to begin", fill=INK, font=FONT)
            return
        page = self.document.pdf[self.index]
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        self.display_scale = display_scale(
            page.rect.width, page.rect.height, width, height, self.zoom.get()
        )
        self.zoom_readout.set(f"{self.display_scale / PIXELS_PER_POINT:.0%}")
        self.page_image = tk.PhotoImage(data=self.document.render(self.index, self.display_scale),
                                        format="PPM")
        image_width = self.page_image.width()
        image_height = self.page_image.height()
        self.page_x = max(PAGE_MARGIN, (width - image_width) // 2)
        self.page_y = max(PAGE_MARGIN, (height - image_height) // 2)
        self.canvas.create_rectangle(
            self.page_x - 1, self.page_y - 1,
            self.page_x + image_width, self.page_y + image_height, outline=BORDER
        )
        self.canvas.create_image(self.page_x, self.page_y, image=self.page_image, anchor="nw")
        region_width = max(width, self.page_x + image_width + PAGE_MARGIN)
        region_height = max(height, self.page_y + image_height + PAGE_MARGIN)
        self.canvas.configure(scrollregion=(0, 0, region_width, region_height))
        self.draw_bookmarks(image_width, image_height)
        if self.bookmark_target is not None:
            x, y = self.bookmark_target
            anchor = None if x is None else (x * page.rect.width, y * page.rect.height)
            self.bookmark_target = None
        if anchor is None:
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)
        else:
            x, y = anchor
            self.canvas.xview_moveto((self.page_x + x * self.display_scale - width / 2) / region_width)
            self.canvas.yview_moveto((self.page_y + y * self.display_scale - height / 2) / region_height)
        self.rendered_page = key
        self.rendered_viewport = (width, height)

    def refresh(self):
        count = len(self.document.pdf)
        self.page_number.set(str(self.index + 1))
        self.page_total.set(f"/ {count}")
        first = max(0, min(self.index - 2, count - 5))
        key = (first, self.index)
        if self.preview_key != key:
            self.preview_key = key
            for widget in self.filmstrip.winfo_children():
                widget.destroy()
            self.thumbnails.clear()
            for index in range(first, min(first + 5, count)):
                page = self.document.pdf[index]
                scale = 68 / max(page.rect.width, page.rect.height)
                image = tk.PhotoImage(data=self.document.render(index, scale), format="PPM")
                self.thumbnails.append(image)
                button = self.button(self.filmstrip, f"{index + 1} ▰" if index + 1 in self.saved_pages else str(index + 1),
                                     lambda selected=index: self.select_page(selected),
                                     image=image, compound="top", padx=4, pady=2,
                                     bg=ORANGE if index == self.index else PANEL,
                                     fg=PANEL if index == self.index else INK)
                button.pack(side="left", padx=5)
        self.queue_render()

    def permitted(self, permission, message):
        if not self.document:
            return False
        if not self.document.pdf.permissions & permission:
            messagebox.showinfo("PDF permissions", message, parent=self.root)
            return False
        return True

    def start_area(self):
        if self.permitted(fitz.PDF_PERM_COPY, "This PDF restricts copying."):
            self.cancel_selection()
            self.area_mode = True
            self.canvas.configure(cursor="crosshair")
            self.canvas.focus_set()

    def cancel_selection(self):
        self.selected_words = []
        self.drag_start = None
        self.area_mode = False
        self.canvas.delete("selection")
        self.canvas.configure(cursor="")

    def page_point(self, event):
        return fitz.Point(
            (self.canvas.canvasx(event.x) - self.page_x) / self.display_scale,
            (self.canvas.canvasy(event.y) - self.page_y) / self.display_scale,
        )

    def draw_selection(self, rect):
        x0, y0, x1, y1 = rect
        self.canvas.create_rectangle(
            self.page_x + x0 * self.display_scale, self.page_y + y0 * self.display_scale,
            self.page_x + x1 * self.display_scale, self.page_y + y1 * self.display_scale,
            fill="#77a9df", stipple="gray50", outline="#386ba8", tags="selection",
        )

    def begin_selection(self, event):
        self.canvas.focus_set()
        self.drag_start = None
        self.selected_words = []
        self.canvas.delete("selection")
        if not self.document or self.render_job is not None or not hasattr(self, "page_x"):
            return
        page = self.document.pdf[self.index]
        point = self.page_point(event)
        if not page.rect.contains(point):
            return
        if not self.area_mode:
            key = (self.document, self.index)
            if self.word_key != key:
                self.words = page_words(page)
                self.word_key = key
        self.drag_start = point

    def drag_selection(self, event):
        if self.drag_start is None:
            return
        self.canvas.delete("selection")
        page = self.document.pdf[self.index]
        point = self.page_point(event)
        if self.area_mode:
            self.draw_selection(fitz.Rect(self.drag_start, point).normalize() & page.rect)
        elif self.words:
            first = nearest_word(self.words, self.drag_start * page.derotation_matrix)
            last = nearest_word(self.words, point * page.derotation_matrix)
            lo, hi = sorted((first, last))
            self.selected_words = self.words[lo:hi + 1]
            for word in self.selected_words:
                self.draw_selection(fitz.Rect(word[:4]) * page.rotation_matrix)

    def end_selection(self, event):
        if self.drag_start is None:
            return
        if self.area_mode:
            image = self.document.crop(self.index, self.drag_start, self.page_point(event))
            self.cancel_selection()
            if image:
                try:
                    copy_png(image)
                except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                    messagebox.showerror("Could not copy image", str(error), parent=self.root)
        self.drag_start = None

    def copy_selection(self):
        if not self.selected_words:
            messagebox.showinfo("Copy text", "Drag across text to select it first. For scanned pages, use Copy area as image.", parent=self.root)
        elif self.permitted(fitz.PDF_PERM_COPY, "This PDF restricts copying."):
            self.root.clipboard_clear()
            self.root.clipboard_append(copy_text(self.selected_words))
        return "break"

    def context_menu(self, event):
        menu = self.page_menu
        menu.delete(0, "end")
        menu.add_command(label="Copy text", command=self.copy_selection)
        menu.add_command(label="Copy area as image", command=self.start_area)
        if self.mode == "Review":
            menu.add_command(label="Highlight selection", command=self.highlight_selection)
        if self.document and self.rendered_page == (self.document, self.index) and self.render_job is None:
            point = self.page_point(event)
            if self.document.pdf[self.index].rect.contains(point):
                menu.add_command(label="Bookmark this spot", command=lambda: self.bookmark_spot(point))
        menu.add_separator()
        menu.add_command(label="Go to page", command=self.jump_dialog)
        if self.document:
            menu.add_command(label="Close PDF", accelerator="Ctrl+W", command=self.close_document)
        menu.add_command(label="Exit full screen" if self.fullscreen else "Full screen",
                         command=self.toggle_fullscreen)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def highlight_selection(self):
        if not self.selected_words or not self.permitted(
            fitz.PDF_PERM_ANNOTATE, "This PDF restricts adding annotations."
        ):
            return
        page = self.document.pdf[self.index]
        page.add_highlight_annot([fitz.Rect(word[:4]) for word in self.selected_words])
        self.mark_edited()

    def mark_edited(self):
        self.dirty = True
        self.title.set(self.document.path.name + " •")
        self.preview_key = None
        self.refresh()

    def save(self):
        if not self.document:
            return
        suggested = self.last_directory / (self.document.path.stem + " - copy.pdf")
        selection = choose_pdf(self.root, suggested, save=True)
        if not selection:
            return
        path = pdf_copy_path(selection)
        try:
            self.document.save_copy(path)
        except (OSError, RuntimeError, ValueError) as error:
            messagebox.showerror("Could not save copy", str(error))
            return
        self.last_directory = path.parent
        self.dirty = False
        self.title.set(self.document.path.name)
        messagebox.showinfo("Saved", "The PDF copy was saved.")

    def close_document(self):
        if not self.document:
            return "break"
        if self.dirty and not messagebox.askyesno(
            "Unsaved edits", "Discard the unsaved edits?", parent=self.root
        ):
            return "break"
        self.document.close()
        self.document = None
        self.dirty = False
        self.index = 0
        self.rendered_page = self.word_key = self.bookmark_target = self.preview_key = None
        self.saved_pages.clear()
        self.saved_spots.clear()
        self.words.clear()
        self.title.set("No document open")
        self.page_number.set("")
        self.page_total.set("/ 0")
        self.zoom_readout.set("")
        for widget in self.filmstrip.winfo_children():
            widget.destroy()
        self.thumbnails.clear()
        self.close_pdf_button.configure(state="disabled")
        self.canvas.configure(scrollregion=(0, 0, 0, 0))
        self.queue_render()
        return "break"

    def close(self):
        if self.dirty and not messagebox.askyesno("Unsaved edits", "Discard the unsaved edits?"):
            return
        if self.document:
            self.document.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk(className="JatayuPdfStudio")
    app = Studio(root)
    if len(sys.argv) > 1:
        root.after_idle(lambda: app.open(sys.argv[1]))
    root.mainloop()
