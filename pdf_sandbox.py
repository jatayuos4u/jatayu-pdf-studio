"""Launch the PDF worker with filtered syscalls and a private filesystem."""
import ctypes as c
import errno
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryFile


def network_filter(output):
    lib = c.CDLL("libseccomp.so.2")
    lib.seccomp_init.argtypes = [c.c_uint32]
    lib.seccomp_init.restype = c.c_void_p
    lib.seccomp_release.argtypes = [c.c_void_p]
    lib.seccomp_syscall_resolve_name.argtypes = [c.c_char_p]
    lib.seccomp_rule_add.argtypes = [c.c_void_p, c.c_uint32, c.c_int, c.c_uint]
    lib.seccomp_export_bpf.argtypes = [c.c_void_p, c.c_int]
    context = lib.seccomp_init(0x7fff0000)  # Allow other native syscalls.
    if not context:
        raise RuntimeError("Could not initialize PDF sandbox filter.")
    try:
        for name in (b"socket", b"socketpair", b"socketcall", b"io_uring_setup"):
            number = lib.seccomp_syscall_resolve_name(name)
            if number >= 0 and lib.seccomp_rule_add(context, 0x00050000 | errno.EPERM, number, 0):
                raise RuntimeError("Could not configure PDF sandbox filter.")
        if lib.seccomp_export_bpf(context, output.fileno()):
            raise RuntimeError("Could not export PDF sandbox filter.")
        output.seek(0)
    finally:
        lib.seccomp_release(context)


def launch_worker(pdf_fd):
    worker_dir = Path(__file__).resolve().parent
    python = Path(sys.executable).resolve()
    with TemporaryFile() as rules:
        network_filter(rules)
        command = [
            "/usr/bin/bwrap", "--unshare-all", "--unshare-user", "--share-net",
            "--disable-userns", "--die-with-parent", "--new-session", "--clearenv",
            "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64", "--dir", "/tmp",
            "--setenv", "HOME", "/tmp", "--setenv", "LANG", "C.UTF-8",
        ]
        # The development environment can use a Python runtime outside /usr.
        if not python.is_relative_to("/usr"):
            runtime = Path(sys.prefix).resolve()
            command.extend(["--ro-bind", str(runtime), str(runtime)])
        # Allow system font fallback without exposing per-user font configuration.
        command.extend(["--ro-bind-try", "/etc/fonts", "/etc/fonts"])
        command.extend([
            "--ro-bind", str(worker_dir / "pdf_worker.py"), "/pdf_worker.py",
            "--ro-bind", f"/proc/self/fd/{pdf_fd}", "/input.pdf",
            "--remount-ro", "/", "--seccomp", str(rules.fileno()), "--", str(python),
            "-I", "-B", "/pdf_worker.py",
        ])
        return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, bufsize=0,
                                pass_fds=(rules.fileno(), pdf_fd))
