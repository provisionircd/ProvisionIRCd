import logging.handlers
import datetime
import logging
import time
import sys
import os


class EnhancedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, filename, when="midnight", interval=1, backup_count=0, encoding=None, delay=0, utc=0, maxBytes=0, backupExpire=0):
        """ This is just a combination of TimedRotatingFileHandler and RotatingFileHandler (adds maxBytes to TimedRotatingFileHandler) """
        super().__init__(filename, when, interval, backup_count, encoding, delay, utc)

        self.maxBytes = min(maxBytes, 100_000_000)  # Limit to 100MB
        self.backupExpire = min(backupExpire, 315_569_260)  # Limit to 10 years
        self.backupCount = min(backup_count, 999)
        self.suffix = "%Y-%m-%d"
        self.filename = filename

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, see if the supplied record would cause the file to exceed
        the size limit we have.

        we are also comparing times
        """

        if self.stream is None:
            self.stream = self._open()

        if 0 < self.maxBytes <= self.stream.tell() + len(self.format(record) + '\n'):
            return 1

        return int(time.time()) >= self.rolloverAt

    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """

        if self.stream:
            self.stream.close()
            self.stream = None
        if self.backupCount > 0:
            d = datetime.datetime.today().strftime(self.suffix)
            for i in range(self.backupCount - 1, 0, -1):
                n = "%03d" % i
                sfn = self.rotation_filename("%s.%s.%03d" % (self.baseFilename, d, int(n)))
                dfn = self.rotation_filename("%s.%s.%03d" % (self.baseFilename, d, int(n) + 1))
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.rotation_filename(self.baseFilename + '.' + d + ".001")
            if os.path.exists(dfn):
                os.remove(dfn)
            try:
                self.rotate(self.baseFilename, dfn)
                self.delete_old_files()
            except:
                pass
        if not self.delay:
            self.stream = self._open()

        currentTime = int(time.time())
        dstNow = time.localtime(currentTime)[-1]
        newRolloverAt = self.computeRollover(currentTime)

        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            dstThen = timeTuple[-1]
            if dstNow != dstThen:
                if dstNow:
                    addend = 3600
                else:
                    addend = -3600
                timeTuple = time.localtime(t + addend)

        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval

        if (self.when == "MIDNIGHT" or self.when.startswith('W')) and not self.utc:
            dstAtRollover = time.localtime(newRolloverAt)[-1]
            if dstNow != dstAtRollover:
                if not dstNow:  # DST kicks in before next rollover, so we need to deduct an hour
                    addend = -3600
                else:  # DST bows out before next rollover, so we need to add an hour
                    addend = 3600
                newRolloverAt += addend
        self.rolloverAt = newRolloverAt

    def delete_old_files(self):
        dir_name, base_name = os.path.split(self.baseFilename)
        files = [os.path.join(dir_name, f) for f in os.listdir(dir_name) if os.path.isfile(os.path.join(dir_name, f))]

        for fn in files:
            if fn == self.baseFilename:
                continue

            if self.backupExpire and (time.time() - os.path.getmtime(fn)) > self.backupExpire:
                os.remove(fn)
                continue

        oldest = sorted(files, key=os.path.getmtime)
        for fn in oldest[:-self.backupCount]:
            os.remove(fn)


if not os.path.exists("logs"):
    os.mkdir("logs")

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

# These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"

COLORS = dict(WARNING=YELLOW, INFO=BLUE, DEBUG=WHITE, CRITICAL=YELLOW, ERROR=RED)


class PackagePathFilter(logging.Filter):
    def filter(self, record):
        pathname = record.pathname
        record.relativepath = None
        abs_sys_paths = map(os.path.abspath, sys.path)
        for path in sorted(abs_sys_paths, key=len, reverse=True):  # longer paths first
            path = path if path.endswith(os.sep) else path + os.sep
            if pathname.startswith(path):
                record.relativepath = os.path.relpath(pathname, path)
                break
        return True


class LogFormatter(logging.Formatter):
    def __init__(self, fmt, color=0):
        super().__init__(fmt)
        self.color = color

    def format(self, record):
        if self.color and (levelname := record.levelname) in COLORS:
            record.levelname = f"{COLOR_SEQ % (30 + COLORS[levelname])}{levelname}{RESET_SEQ}"
        return super().format(record)


class IRCDLogger:
    forked = 0
    file_handler = None
    stream_handler = None
    log = None
    loghandlers = []

    @staticmethod
    def view_logging_info():
        logging.info("Logger initialised with settings:")

        mb_file = IRCDLogger.file_handler.maxBytes / 1_000_000
        logging.info(f"maxBytes: {IRCDLogger.file_handler.maxBytes} ({mb_file:.2f} MB per file)")

        logging.info(f"backupCount: {IRCDLogger.file_handler.backupCount}")

        sec = datetime.timedelta(seconds=IRCDLogger.file_handler.backupExpire)
        d = datetime.datetime(1, 1, 1) + sec
        logging.info(f"backupExpire: {IRCDLogger.file_handler.backupExpire} seconds ({d.year - 1} years, {d.month - 1} months, {d.day - 1} days)")

        max_size = IRCDLogger.file_handler.maxBytes * (IRCDLogger.file_handler.backupCount + 1)
        mb_size = max_size / 1_000_000
        logging.info(f"Max possible total logs size: {max_size} bytes ({mb_size:.2f} MB)")

        # logging.info(f"Logs will rotate log files with interval: {IRCDLogger.file_handler.when}")

        if max_size > 10_000_000_000:
            gb_size = mb_size / 1_000
            logging.warning(f"Total log size limit exceeds 10GB: {gb_size:.2f} GB")
            logging.warning("Pausing for 5 seconds for visibility...")
            time.sleep(5)

    @staticmethod
    def fork():
        logging.getLogger().removeHandler(IRCDLogger.stream_handler)
        IRCDLogger.loghandlers.remove(IRCDLogger.stream_handler)

    @staticmethod
    def debug():
        IRCDLogger.stream_handler.setLevel(logging.DEBUG)


log_fmt = "[%(asctime)s] {%(relativepath)s:%(lineno)d} %(levelname)s - %(message)s"
log_paths = {
    "file": "logs/ircd.log",
    "warning": "logs/warning.log",
    "error": "logs/error.log",
    "exception": "logs/exception.log"
}
log_levels = [logging.DEBUG, logging.WARNING, logging.ERROR, logging.ERROR]

# Create file handlers.
handlers = []
for path, level in zip(log_paths.values(), log_levels):
    handler = EnhancedRotatingFileHandler(path, when="midnight", maxBytes=1_000 * 1_000 * 10, backup_count=30, backupExpire=7_776_000)
    handler.setLevel(level)
    handler.setFormatter(LogFormatter(fmt=log_fmt, color=0))
    handler.addFilter(PackagePathFilter())

    if level == logging.DEBUG:
        IRCDLogger.file_handler = handler

    # Fix so that error events do not end up in warning.log.
    if level == logging.WARNING:
        handler.addFilter(lambda record: record.levelno == logging.WARNING)

    handlers.append(handler)

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(LogFormatter(fmt=log_fmt, color=1))
stream_handler.addFilter(PackagePathFilter())
handlers.append(stream_handler)
IRCDLogger.stream_handler = stream_handler

IRCDLogger.loghandlers.extend(handlers)
logging.basicConfig(level=logging.DEBUG, handlers=IRCDLogger.loghandlers)
IRCDLogger.view_logging_info()
