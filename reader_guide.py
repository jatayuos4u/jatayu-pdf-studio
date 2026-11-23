"""In-app reader guide and keyboard reference."""
import tkinter as tk
from tkinter import ttk


TOPICS = {
    "Reading": (
        ("Open a PDF", "Choose Open PDF or press Ctrl+O. Use the thumbnail strip or "
         "the Previous and Next buttons to turn pages."),
        ("Jump to a page", "Type a page number in the bottom bar and press Enter, "
         "or press Ctrl+G. The reader counts from the first PDF page, which can "
         "differ from the number printed on the page."),
        ("Adjust the view", "Choose Fit page to see the entire sheet or Fit width "
         "to enlarge the text. Use − and + to zoom, or click the percentage to "
         "enter a value. Drag the green scrollbar to move within a zoomed page."),
        ("Read in full screen", "Press F11. The bottom bar keeps page navigation, "
         "bookmarks, and zoom within reach. Press Esc to return to the normal view."),
    ),
    "Bookmarks & Review": (
        ("Bookmark a page", "Click the top-right page fold or press Ctrl+D. The fold "
         "turns orange when saved. Click it again to remove the bookmark."),
        ("Bookmark an exact spot", "Right-click beside a paragraph and choose "
         "Bookmark this spot. Add a label to make it easier to find later."),
        ("Revisit or remove bookmarks", "Open Bookmarks, select an entry, then choose "
         "Go to or Remove. Bookmarks are stored locally for each PDF path."),
        ("Highlight and save a copy", "Switch to Review, drag across words, then "
         "click Highlight selection. Choose Save a copy to export the marked-up PDF."),
        ("Copy text or a page area", "Drag across text and press Ctrl+C. For a photo "
         "or a scanned page, choose Copy area as image, drag a rectangle, and paste "
         "into an app that accepts images."),
    ),
}

SHORTCUTS = (
    ("Open a PDF", "Ctrl+O"),
    ("Close the current PDF", "Ctrl+W"),
    ("Go to page", "Ctrl+G"),
    ("Previous / next page", "Page Up / Page Down"),
    ("Full screen / exit", "F11 / Esc"),
    ("Fit page", "Ctrl+0"),
    ("Zoom in / out", "Ctrl++ / Ctrl+−"),
    ("Zoom with the mouse", "Ctrl+mouse wheel"),
    ("Bookmark the current page", "Ctrl+D"),
    ("Copy selected text", "Ctrl+C"),
    ("Save a copy", "Ctrl+Shift+S"),
    ("Open this guide", "F1"),
)


def open_reader_guide(parent, icon):
    paper, panel, ink, green = "#f6efe4", "#fff8ed", "#211e17", "#194b31"
    window = tk.Toplevel(parent, bg=paper)
    window.title("Reader Guide · Jatayu PDF Studio")
    window.transient(parent)
    window.geometry("740x525")
    window.minsize(480, 350)

    header = tk.Frame(window, bg=green, padx=18, pady=13)
    header.pack(fill="x")
    tk.Label(header, image=icon, bg=green).pack(side="left", padx=(0, 12))
    text = tk.Frame(header, bg=green)
    text.pack(side="left")
    tk.Label(text, text="Reader Guide", bg=green, fg=panel,
             font=("DejaVu Serif", 19, "bold")).pack(anchor="w")
    tk.Label(text, text="Jatayu PDF Studio", bg=green, fg=panel,
             font=("DejaVu Sans", 10)).pack(anchor="w")

    notebook = ttk.Notebook(window, padding=2)
    notebook.pack(fill="both", expand=True, padx=16, pady=(14, 4))
    notebook.enable_traversal()

    for name, sections in (*TOPICS.items(), ("Keyboard Shortcuts", None)):
        tab = tk.Frame(notebook, bg=panel)
        notebook.add(tab, text=name)
        content = tk.Text(
            tab, wrap="word", bg=panel, fg=ink, relief="flat", padx=16, pady=10,
            font=("DejaVu Sans", 11), highlightthickness=0, cursor="arrow",
        )
        scroll = ttk.Scrollbar(tab, orient="vertical", command=content.yview)
        content.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        content.pack(side="left", fill="both", expand=True)
        content.tag_configure("heading", foreground=green, spacing1=9, spacing3=3,
                              font=("DejaVu Sans", 11, "bold"))
        content.tag_configure("body", spacing3=8)
        content.tag_configure("key", foreground=green, spacing1=5, spacing3=5,
                              tabs=("255p",), font=("DejaVu Sans", 11, "bold"))
        if sections is None:
            for action, shortcut in SHORTCUTS:
                content.insert("end", action + "\t", "key")
                content.insert("end", shortcut + "\n", "key")
        else:
            for heading, body in sections:
                content.insert("end", heading + "\n", "heading")
                content.insert("end", body + "\n", "body")
        content.configure(state="disabled")

    close = tk.Button(window, text="Close", command=window.destroy,
                      bg=green, fg=panel, padx=16, pady=5, relief="flat")
    close.pack(anchor="e", padx=16, pady=(4, 12))
    window.bind("<Escape>", lambda event: window.destroy())
    window.bind("<F1>", lambda event: "break")
    close.focus_set()
    return window
