"""Desktop-side transport for the isolated PDF worker."""
import json
import math
import os
from pathlib import Path
import select
import stat
import struct
from tempfile import TemporaryDirectory
import time

import fitz

from pdf_sandbox import launch_worker


def numeric_vector(value, length):
    return isinstance(value, list) and len(value) == length and all(
        type(item) in (int, float) and abs(item) <= 10**9 and math.isfinite(item)
        for item in value
    )


def validate_response(action, value):
    if action == "info":
        valid = (isinstance(value, list) and len(value) == 3
                 and type(value[0]) is int and 0 <= value[0] <= 2**31 - 1
                 and type(value[1]) is bool and type(value[2]) is int
                 and (value[0] > 0 or value[1]))
    elif action == "page":
        valid = (isinstance(value, list) and len(value) == 3
                 and all(numeric_vector(item, length)
                         for item, length in zip(value, (4, 6, 6)))
                 and value[0][2] > value[0][0] and value[0][3] > value[0][1])
    elif action == "words":
        valid = isinstance(value, list) and all(
            isinstance(word, list) and len(word) == 8 and numeric_vector(word[:4], 4)
            and isinstance(word[4], str) and all(type(index) is int for index in word[5:])
            for word in value
        )
    elif action == "authenticate":
        valid = type(value) in (bool, int) and value in (0, 1, 2, 4, 6)
    else:
        valid = action == "highlight" and value is True
    if not valid:
        raise ValueError("Invalid PDF worker response.")


class PdfPage:
    def __init__(self, document, index, geometry):
        self.document, self.index = document, index
        rect, rotation, derotation = geometry
        self.rect = fitz.Rect(rect)
        self.rotation_matrix = fitz.Matrix(rotation)
        self.derotation_matrix = fitz.Matrix(derotation)

    def get_text(self, kind, *, sort):
        if kind != "words" or not sort:
            raise ValueError("Unsupported text extraction mode.")
        return self.document.request("words", self.index)

    def add_highlight_annot(self, rects):
        self.document.request("highlight", self.index, [list(rect) for rect in rects])


class PdfDocument:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.pdf = self
        self.pages = {}
        self.closed = False
        fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("Choose a regular PDF file.")
            self.worker = launch_worker(fd)
        finally:
            os.close(fd)
        try:
            os.set_blocking(self.worker.stdin.fileno(), False)
            self.count, self.needs_pass, self.permissions = self.request("info")
        except Exception:
            self.close()
            raise

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.worker.poll() is None:
            self.worker.kill()
        self.worker.wait()
        self.worker.stdin.close()
        self.worker.stdout.close()

    def request(self, action, *args):
        if self.closed:
            raise RuntimeError("The PDF worker is closed. Reopen the document.")
        data = json.dumps([action, args], allow_nan=False).encode() + b"\n"
        if len(data) > 2**20:
            raise ValueError("PDF selection is too large.")
        deadline = time.monotonic() + 20
        incoming = self.worker.stdout.fileno()
        outgoing = self.worker.stdin.fileno()

        def read(size):
            output = bytearray()
            while len(output) < size:
                ready, _, _ = select.select([incoming], [], [], max(0, deadline - time.monotonic()))
                if not ready or time.monotonic() >= deadline:
                    raise TimeoutError()
                block = os.read(incoming, min(size - len(output), 65536))
                if not block:
                    raise EOFError()
                output.extend(block)
            return output

        try:
            pending = memoryview(data)
            while pending:
                _, ready, _ = select.select([], [outgoing], [], max(0, deadline - time.monotonic()))
                if not ready or time.monotonic() >= deadline:
                    raise TimeoutError()
                pending = pending[os.write(outgoing, pending):]
            header = read(5)
            size, = struct.unpack("!I", header[1:])
            binary = action in {"render", "crop", "save"}
            limit = {"render": 51 * 1024**2, "crop": 51 * 1024**2,
                     "save": 128 * 1024**2, "words": 8 * 1024**2}.get(action, 4096)
            expected = ord("+") if binary else ord("=")
            if header[0] == ord("!"):
                limit = 2048
            if size > limit or header[0] not in (expected, ord("!")):
                raise ValueError()
            payload = read(size)
            if header[0] == ord("="):
                result = json.loads(payload)
                validate_response(action, result)
                return result
            if header[0] == ord("+"):
                return bytes(payload)
        except (OSError, EOFError, ValueError, RecursionError) as error:
            self.close()
            raise RuntimeError("The isolated PDF worker stopped or could not start. "
                               "Reopen the PDF and check that Bubblewrap user namespaces are enabled.") from error
        raise ValueError(payload.decode("utf-8", errors="replace"))

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        if index not in self.pages:
            self.pages[index] = PdfPage(self, index, self.request("page", index))
        return self.pages[index]

    def authenticate(self, password):
        result = self.request("authenticate", password)
        if result:
            self.count, self.needs_pass, self.permissions = self.request("info")
        return result

    def render(self, page_index, scale):
        data = self.request("render", page_index, scale)
        magic, dimensions, depth, pixels = data.split(b"\n", 3)
        width, height = map(int, dimensions.split())
        if (magic != b"P6" or depth != b"255" or not 0 < width <= 4096
                or not 0 < height <= 4096 or len(pixels) != width * height * 3):
            raise ValueError("Invalid image returned by PDF worker.")
        return f"P6\n{width} {height}\n255\n".encode() + pixels

    def crop(self, page_index, first, last):
        return self.request("crop", page_index, list(first), list(last))

    def save_copy(self, destination):
        destination = Path(destination)
        data = self.request("save")
        with TemporaryDirectory(prefix=".jatayu-pdf-", dir=destination.parent) as temporary:
            staged = Path(temporary) / "copy.pdf"
            fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(data)
            os.link(staged, destination)
