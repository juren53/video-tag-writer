"""PyQt6 Single Instance Guard - Reusable Single-Instance Module

A lightweight, reusable module that lets any PyQt6 application allow only
one running instance. A second launch silently signals the primary
instance to raise itself and then exits — no error dialog.

Author: Generated with Claude Code
License: MIT
Version: 1.0.0

Vendored from ~/Projects/single-instance-guard — copy-paste consumption is
the intended integration model for this module (see its own CLAUDE.md).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstanceGuard:
    """Allows only one process at a time; secondary launches raise the primary.

    Uses QLocalServer / QLocalSocket so a second launch silently raises
    the already-running window rather than showing an error dialog.

    Example:
        >>> import sys
        >>> from PyQt6.QtWidgets import QApplication
        >>> from single_instance_guard import SingleInstanceGuard
        >>>
        >>> app = QApplication(sys.argv)
        >>> guard = SingleInstanceGuard("MyApp-SingleInstance")
        >>> if not guard.try_acquire():
        ...     sys.exit(0)  # existing instance raised; we exit cleanly
        >>> window = MainWindow()
        >>> guard.connect_window(window)
        >>> app.aboutToQuit.connect(guard.release)
        >>> window.show()
        >>> sys.exit(app.exec())
    """

    def __init__(
        self,
        app_id: str,
        connect_timeout_ms: int = 500,
        write_timeout_ms: int = 1000,
    ):
        """Create a guard for the given application identifier.

        Args:
            app_id: Unique name for the local socket (e.g. "MyApp-SingleInstance").
                Must be unique per application — reusing another app's id will
                cause the two applications to treat each other as instances
                of the same app.
            connect_timeout_ms: How long to wait when probing for an existing
                instance before assuming none is running.
            write_timeout_ms: How long to wait for the "raise" signal to be
                written to the existing instance's socket.
        """
        self._socket_name = app_id
        self._connect_timeout_ms = connect_timeout_ms
        self._write_timeout_ms = write_timeout_ms
        self._server: QLocalServer | None = None

    def try_acquire(self, payload: bytes = b"") -> bool:
        """Attempt to become the primary instance.

        Args:
            payload: Optional extra bytes to send to the primary instance
                alongside the raise signal (e.g. a file path from argv, so
                the primary can open it). Must not contain a newline.

        Returns:
            True if this process should become the primary instance.
            False if an existing instance was found and signalled to raise
            (caller should exit immediately).
        """
        probe = QLocalSocket()
        probe.connectToServer(self._socket_name)
        if probe.waitForConnected(self._connect_timeout_ms):
            message = b"raise\n" + payload if payload else b"raise"
            probe.write(message)
            probe.waitForBytesWritten(self._write_timeout_ms)
            probe.disconnectFromServer()
            return False

        # Become the primary — remove any stale socket from a previous crash
        QLocalServer.removeServer(self._socket_name)
        self._server = QLocalServer()
        self._server.listen(self._socket_name)
        return True

    def connect_window(self, window, on_payload=None) -> None:
        """Wire incoming connections from secondary launches to raise *window*.

        Args:
            on_payload: Optional callable invoked with the decoded payload
                string when a secondary launch sends one (e.g. a file path).
                Not called when a secondary launch sends no payload.
        """
        if self._server is None:
            return
        self._server.newConnection.connect(
            lambda: self._handle_connection(window, on_payload)
        )

    def _handle_connection(self, window, on_payload) -> None:
        conn = self._server.nextPendingConnection()
        if conn is None:
            return
        conn.readyRead.connect(lambda: self._on_data(conn, window, on_payload))

    def _on_data(self, conn, window, on_payload) -> None:
        data = bytes(conn.readAll())
        if data.startswith(b"raise"):
            # Un-minimise, then bring to front
            state = window.windowState() & ~Qt.WindowState.WindowMinimized
            window.setWindowState(state)
            window.show()
            window.raise_()
            window.activateWindow()
            _, _, payload = data.partition(b"\n")
            if payload and on_payload is not None:
                on_payload(payload.decode("utf-8"))
        conn.disconnectFromServer()

    def release(self) -> None:
        """Release the socket. Call on application exit (e.g. aboutToQuit)."""
        if self._server:
            self._server.close()
            QLocalServer.removeServer(self._socket_name)
            self._server = None
