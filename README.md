# Jatayu PDF Studio

Jatayu PDF Studio is a desktop PDF reader for JatayuOS and Debian 13. It supports full-screen reading, page and spot bookmarks, and text highlighting.

**Current stable release: v0.10.7.**

## Download and install

**JatayuOS or Debian 13**

[Download Jatayu PDF Studio v0.10.7 (.deb)](https://github.com/jatayuos4u/jatayu-pdf-studio/releases/download/v0.10.7/jatayu-pdf-studio_0.10.7-1_all.deb)

[Latest release](https://github.com/jatayuos4u/jatayu-pdf-studio/releases/latest) · [v0.10.7 release notes and checksums](https://github.com/jatayuos4u/jatayu-pdf-studio/releases/tag/v0.10.7)

Run this from the folder containing the downloaded package:

```sh
sudo apt install ./jatayu-pdf-studio_0.10.7-1_all.deb
```

## Run from source

Open a terminal in the extracted source folder and run

```sh
sudo apt install python3-tk python3-fitz bubblewrap libseccomp2 kdialog wl-clipboard xclip
python3 app.py demo/Monsoon-Field-Notes.pdf
```

## Read and review

- Drag over words in a PDF with a text layer. Use Ctrl+C, the right-click menu,
  or **Copy text** to copy the selected words.
- Click **Copy area as image**, then drag across the page to copy the region as
  PNG. This works on scanned pages. Paste into a desktop app that accepts PNG.
  Install wl-clipboard for Wayland or xclip for X11.
- Switch to **Review**, select words, and click **Highlight selection**. Use
  **Save a copy** to export the annotated PDF to a new filename.
- Click **Full screen** or press F11. Use **Previous**, **Next**, or the page
  field in the full-screen bottom bar. Press Enter after typing a page number.
  Press Esc or click **Exit full screen** to restore the regular interface.
- Enter a page number in the bottom bar and press Enter. Ctrl+G works in full screen.
- Use − / +, click the current percentage, or use Ctrl+mouse wheel to zoom.
  The normal and full-screen bottom bars share the zoom setting. Zoom keeps
  the same point centered where the page boundaries allow it.
  Use **Fit page** (Ctrl+0) to see the entire page, or **Fit width** and scroll.
  Drag the green scrollbar at the right edge to move within the current page in either window mode.
  Shift+mouse wheel pans sideways when zoomed in.

- Click the page’s top-right fold to toggle a whole-page bookmark. The
  thumbnail also shows a marker. Ctrl+D saves the current page.
- Right-click any point on a page and choose **Bookmark this spot**. Add an
  optional label. The page displays a small ribbon and a dot at that spot.
- Open **Bookmarks** in either view to jump to or remove a saved page or spot.
  Spots are stored in page coordinates and can be revisited at different zoom
  levels. Bookmarks are stored locally by PDF path, separately from the PDF.

Open and Save use the KDE file picker when kdialog is installed. The application
uses Tk and PyMuPDF and opens one document at a time. Text selection is by word.
Scans without a text layer support image copying.

## Branding and Help

The logo and PNG app icons are in `artwork/`. The application uses the mark
in its header and registers window icons with Tk. **Help** provides the reader
guide, About, and licence and credits. Press **F1** to open the Reader Guide, with tabs for reading, bookmarks and review, and keyboard shortcuts.


## Licence and credits

Created by **Anup Kumar Yadav** for JatayuOS. Jatayu PDF Studio is licensed
under [GNU AGPL v3 only](LICENSE) (`AGPL-3.0-only`). PDF rendering uses
PyMuPDF and MuPDF by Artifex Software. See [third-party notices](THIRD-PARTY-NOTICES.md).

## Build the Debian package

From this source directory, run `./packaging/build-deb.sh`. An optional argument
selects an existing output directory. Install using APT with the local .deb
path. PDF opening requires Bubblewrap and fails if the worker cannot start.
