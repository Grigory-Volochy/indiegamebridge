import time
from logging.handlers import TimedRotatingFileHandler


class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    # On Windows, os.rename in TimedRotatingFileHandler.doRollover fails with
    # PermissionError (WinError 32) when another process still has the log file
    # open. The base class also leaves rolloverAt unchanged on failure, so every
    # subsequent emit in the same process retries the rollover and re-raises.
    # This subclass absorbs the failure, reopens the stream, and advances
    # rolloverAt so the current process keeps logging into the existing file
    # until the next interval, when rotation can be retried.
    def doRollover(self):
        try:
            super().doRollover()
        except (PermissionError, OSError):
            if self.stream is None:
                self.stream = self._open()
            self.rolloverAt = self.computeRollover(int(time.time()))
