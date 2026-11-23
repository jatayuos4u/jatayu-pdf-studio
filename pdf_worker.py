"""PDF parsing operations. Run only inside the sandbox."""
import json
import resource
import struct
import sys
import warnings

import fitz


def execute(pdf, action, args):
    if action == "authenticate":
        return pdf.authenticate(args[0])
    if pdf.is_encrypted:
        if action == "info":
            return [0, True, 0]
        raise ValueError("Unlock the PDF before reading pages.")
    if action == "info":
        count = len(pdf)
        if not count:
            raise ValueError("Choose a PDF with at least one page.")
        return [count, False, pdf.permissions]
    if action == "save":
        return pdf.tobytes(garbage=3, deflate=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    page = pdf[args[0]]
    if action == "page":
        return [list(page.rect), list(page.rotation_matrix), list(page.derotation_matrix)]
    if action == "words":
        return page.get_text("words", sort=True)
    if action == "render":
        scale = min(args[1], 4096 / max(page.rect.width, page.rect.height))
        return page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes("ppm")
    if action == "crop":
        area = fitz.Rect(args[1], args[2]).normalize() & page.rect
        if area.width >= 2 and area.height >= 2:
            scale = min(2, 4096 / max(area.width, area.height))
            return page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=area,
                                   alpha=False).tobytes("png")
        return b""
    if action == "highlight":
        page.add_highlight_annot([fitz.Rect(rect) for rect in args[1]])
        return True
    raise ValueError("Unknown PDF operation.")


def main():
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    warnings.filterwarnings("ignore")
    fitz.TOOLS.mupdf_display_errors(False)
    fitz.TOOLS.mupdf_display_warnings(False)
    output = sys.stdout.buffer
    pdf = None
    while line := sys.stdin.buffer.readline(2**20 + 1):
        try:
            action, args = json.loads(line)
            if pdf is None:
                pdf = fitz.open("/input.pdf", filetype="pdf")
                if not pdf.is_pdf:
                    raise ValueError("Choose a PDF file.")
            result = execute(pdf, action, args)
            payload = result if isinstance(result, bytes) else json.dumps(result, allow_nan=False).encode()
            if len(payload) > 128 * 1024**2:
                raise ValueError("PDF operation exceeded the output size limit.")
            status = b"+" if isinstance(result, bytes) else b"="
        except Exception as error:
            status = b"!"
            payload = str(error)[:500].encode("utf-8", errors="replace")
        output.write(status + struct.pack("!I", len(payload)))
        output.write(payload)
        output.flush()


if __name__ == "__main__":
    main()
