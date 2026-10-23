"""One cancellable workflow at a time; stop the entire chain on any failed step."""
from __future__ import annotations
from dataclasses import dataclass, field
import codecs
import os
import signal
import sys
from .runtime import external_environment
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


@dataclass
class Job:
    title: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    done: object = None
    allow_failure: bool = False


class Runner(QObject):
    output = Signal(str)
    step_started = Signal(str, object)
    completed = Signal(bool, str)
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc = None
        self.pending = []
        self.current = None
        self.captured = ''
        self.cancelled = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timed_out)

    @property
    def busy(self):
        return self.current is not None

    def start(self, jobs):
        if self.busy:
            raise RuntimeError('A workflow is running. Stop it before starting another.')
        if not jobs:
            raise ValueError('No commands to run.')
        self.pending = list(jobs)
        self.cancelled = False
        self.busy_changed.emit(True)
        self._next()

    def _next(self):
        if not self.pending:
            self._finish(True, 'Done')
            return
        self.current = self.pending.pop(0)
        self.captured = ''
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        proc = QProcess(self)
        self.proc = proc
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        if hasattr(proc, 'setUnixProcessParameters'):
            proc.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)
        if self.current.command[0] == sys.executable:
            env = QProcessEnvironment.systemEnvironment()
        else:
            env = QProcessEnvironment()
            for name, value in external_environment().items():
                env.insert(name, value)
        for name, value in self.current.env.items():
            env.insert(name, value)
        proc.setProcessEnvironment(env)
        proc.readyReadStandardOutput.connect(self._read)
        proc.finished.connect(self._exited)
        proc.errorOccurred.connect(self._error)
        self.step_started.emit(self.current.title, self.current.command)
        proc.start(self.current.command[0], self.current.command[1:])
        # Version/help probes should never hold the UI indefinitely.
        if self.current.allow_failure:
            self.timer.start(10000)

    def _read(self):
        if self.proc:
            text = self.decoder.decode(bytes(self.proc.readAllStandardOutput()))
            self.captured += text
            # Keep enough for info/help while avoiding unbounded capture of build output.
            self.captured = self.captured[-2_000_000:]
            if text:
                self.output.emit(text)

    def _exited(self, code, status):
        if not self.current:
            return
        self.timer.stop()
        self._read()
        tail = self.decoder.decode(b'', final=True)
        self.captured += tail
        if tail:
            self.output.emit(tail)
        job = self.current
        self.proc.deleteLater()
        self.proc = None
        if self.cancelled:
            self._finish(False, 'Stopped')
        elif (code != 0 or status == QProcess.ExitStatus.CrashExit) and not job.allow_failure:
            self._finish(False, f'{job.title} failed (exit {code}). Remaining steps skipped.')
        else:
            try:
                if job.done:
                    job.done(self.captured, code)
            except Exception as error:
                self._finish(False, f'{job.title}: {error}')
                return
            QTimer.singleShot(0, self._next)

    def _error(self, error):
        if error == QProcess.ProcessError.FailedToStart and self.current:
            job = self.current
            message = self.proc.errorString()
            self.timer.stop()
            self.proc.deleteLater()
            self.proc = None
            if job.allow_failure:
                self.output.emit(message + '\n')
                QTimer.singleShot(0, self._next)
            else:
                self._finish(False, f'{job.title}: {message}')

    def _finish(self, success, message):
        self.pending.clear()
        self.current = None
        self.busy_changed.emit(False)
        self.completed.emit(success, message)

    def timed_out(self):
        if self.proc:
            self.output.emit('Tool probe timed out.\n')
            self._kill()

    def _kill(self):
        if self.proc:
            pid = self.proc.processId()
            if pid:
                try:
                    os.killpg(pid, signal.SIGKILL)
                    return
                except (ProcessLookupError, PermissionError):
                    pass
            self.proc.kill()

    def stop(self):
        if self.busy:
            self.cancelled = True
            self.pending.clear()
            self._kill()
