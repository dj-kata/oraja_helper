import ctypes
import ctypes.wintypes
import logging

logger = logging.getLogger(__name__)


class NamedPipeLineReceiver:
    PIPE_ACCESS_INBOUND = 0x00000001
    PIPE_TYPE_BYTE = 0x00000000
    PIPE_READMODE_BYTE = 0x00000000
    PIPE_WAIT = 0x00000000
    PIPE_UNLIMITED_INSTANCES = 255
    INVALID_HANDLE_VALUE = ctypes.wintypes.HANDLE(-1).value
    ERROR_PIPE_CONNECTED = 535

    def __init__(self, pipe_name="oraja_helper", buffer_size=65536):
        self.pipe_path = rf"\\.\pipe\{pipe_name}"
        self.buffer_size = buffer_size
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_api()

    def _configure_api(self):
        self.kernel32.CreateNamedPipeW.argtypes = [
            ctypes.wintypes.LPCWSTR,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.LPVOID,
        ]
        self.kernel32.CreateNamedPipeW.restype = ctypes.wintypes.HANDLE
        self.kernel32.ConnectNamedPipe.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.LPVOID]
        self.kernel32.ConnectNamedPipe.restype = ctypes.wintypes.BOOL
        self.kernel32.ReadFile.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.wintypes.LPVOID,
            ctypes.wintypes.DWORD,
            ctypes.POINTER(ctypes.wintypes.DWORD),
            ctypes.wintypes.LPVOID,
        ]
        self.kernel32.ReadFile.restype = ctypes.wintypes.BOOL
        self.kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = ctypes.wintypes.BOOL

    def is_available(self):
        return hasattr(ctypes, "WinDLL")

    def read_line(self):
        handle = self.kernel32.CreateNamedPipeW(
            self.pipe_path,
            self.PIPE_ACCESS_INBOUND,
            self.PIPE_TYPE_BYTE | self.PIPE_READMODE_BYTE | self.PIPE_WAIT,
            self.PIPE_UNLIMITED_INSTANCES,
            self.buffer_size,
            self.buffer_size,
            0,
            None,
        )
        if handle == self.INVALID_HANDLE_VALUE:
            raise OSError(ctypes.get_last_error(), f"CreateNamedPipeW failed: {self.pipe_path}")

        try:
            connected = self.kernel32.ConnectNamedPipe(handle, None)
            if not connected and ctypes.get_last_error() != self.ERROR_PIPE_CONNECTED:
                raise OSError(ctypes.get_last_error(), f"ConnectNamedPipe failed: {self.pipe_path}")

            chunks = []
            while True:
                buf = ctypes.create_string_buffer(self.buffer_size)
                read = ctypes.wintypes.DWORD(0)
                ok = self.kernel32.ReadFile(handle, buf, self.buffer_size, ctypes.byref(read), None)
                if not ok or read.value == 0:
                    break
                chunks.append(buf.raw[:read.value])
                if b"\n" in chunks[-1]:
                    break
            return b"".join(chunks).decode("utf-8", errors="replace").strip()
        finally:
            self.kernel32.CloseHandle(handle)
