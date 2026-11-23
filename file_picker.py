"""Use Plasma's file picker when kdialog is available."""
from pathlib import Path
import shutil
import subprocess
from tkinter import filedialog


def choose_pdf(parent, start, *, save=False):
    executable = shutil.which("kdialog")
    title = "Save a PDF copy" if save else "Open PDF"
    if executable:
        command = [executable, "--title", title]
        if parent.tk.call("tk", "windowingsystem") == "x11":
            frame = str(parent.tk.call("wm", "frame", parent._w))
            command.extend(["--embed", str(int(frame, 0))])
        action = "--getsavefilename" if save else "--getopenfilename"
        try:
            result = subprocess.run(
                [*command, action, str(start), "application/pdf"],
                capture_output=True, text=True, check=False,
            )
        except OSError:
            pass
        else:
            if result.returncode == 0:
                return result.stdout.removesuffix("\n")
            if result.returncode == 1:
                return ""

    options = {"parent": parent, "title": title, "filetypes": [("PDF files", "*.pdf")]}
    if save:
        return filedialog.asksaveasfilename(
            **options, initialdir=start.parent, initialfile=start.name,
            defaultextension=".pdf",
        )
    return filedialog.askopenfilename(**options, initialdir=start)


def pdf_copy_path(selection):
    path = Path(selection)
    if path.suffix.lower() != ".pdf":
        path = path.with_name(path.name + ".pdf")
    return path
