import logging.handlers
import datetime
import logging
import time
import sys
import os
import threading
import functools


class MDC:
    _context = threading.local()

    @classmethod
    def put(cls, key, value):
        if not hasattr(cls._context, "map"):
            cls._context.map = {}
        cls._context.map[key] = value

    @classmethod
    def get(cls, key, default=None):
        if not hasattr(cls._context, "map"):
            return default
        return cls._context.map.get(key, default)

    @classmethod
    def remove(cls, key):
        if hasattr(cls._context, "map"):
            cls._context.map.pop(key, None)

    @classmethod
    def clear(cls):
        if hasattr(cls._context, "map"):
            cls._context.map.clear()

    @classmethod
    def get_context(cls):
        if not hasattr(cls._context, "map"):
            cls._context.map = {}
        return cls._context.map


# MDC Filter Implementation
class MDCFilter(logging.Filter):
    def filter(self, record):
        mdc_data = MDC.get_context()

        for key, value in mdc_data.items():
            setattr(record, key, value)

            if hasattr(value, "__dict__"):
                for attr_name, attr_value in value.__dict__.items():
                    if not attr_name.startswith('_'):  # Skip private attributes
                        setattr(record, f"{key}_{attr_name}", attr_value)

        return True


mdc_filter = MDCFilter()


class ClientContextManager:
    def __init__(self, client):
        self.client = client

    def __enter__(self):
        # Set client context when entering the context manager
        self._set_context(self.client)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._clear_context()

    def _set_context(self, client):
        if client:
            MDC.put("client", client)
            client_name = getattr(client, "name", '*')
            client_id = getattr(client, "id", '*')
            client_ip = getattr(client, 'ip', '*')
            MDC.put("client_id", client_id)
            MDC.put("client_name", client_name)
            MDC.put("client_ip", client_ip)

    def _clear_context(self):
        MDC.remove("client")
        MDC.remove("client_name")
        MDC.remove("client_id")
        MDC.remove("client_ip")

    def __call__(self):
        self._set_context(self.client)
        return self._clear_context


# Function to add to logging module
def client_context(client=None):
    """
    Add client context to logs.

    Can be used in three ways:
    1. As a function:
        clear_func = logging.client_context(client)
        # ... do stuff with client context in logs
        clear_func()  # clear the context

    2. As a context manager:
        with logging.client_context(client):
            # ... do stuff with client context in logs

    3. As a decorator:
        @logging.client_context
        def handle_client(client):
            # ... all logs in this function will have client context
    """
    if callable(client) and not hasattr(client, "id") and not hasattr(client, "ip"):
        # Being used as a decorator without arguments
        @functools.wraps(client)
        def decorator(client_obj, *args, **kwargs):
            with ClientContextManager(client_obj):
                return client(client_obj, *args, **kwargs)

        return decorator
    else:
        # Being used as a function or context manager
        return ClientContextManager(client)


# https://stackoverflow.com/questions/6167587/the-logging-handlers-how-to-rollover-after-time-or-maxbytes
class EnhancedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, filename, when="midnight", interval=1, backup_count=0, encoding=None, delay=0, utc=0, maxbytes=0, backup_expire=0):
        """ This is just a combination of TimedRotatingFileHandler and RotatingFileHandler (adds maxBytes to TimedRotatingFileHandler) """
        super().__init__(filename, when, interval, backup_count, encoding, delay, utc)

        self.maxBytes = min(maxbytes, 100_000_000)  # Limit to 100MB
        self.backupExpire = min(backup_expire, 315_569_260)  # Limit to 10 years
        self.backupCount = min(backup_count, 999)
        self.suffix = "%Y-%m-%d"
        self.filename = filename

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.
        Basically, see if the supplied record would cause the file to exceed the size limit we have.
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
            # noinspection PyTypeChecker
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
            except PermissionError:
                pass
            except Exception as ex:
                logging.exception(ex)
        if not self.delay:
            self.stream = self._open()

        current_time = int(time.time())
        dst_now = time.localtime(current_time)[-1]
        new_rollover_at = self.computeRollover(current_time)

        t = self.rolloverAt - self.interval
        if self.utc:
            time_tuple = time.gmtime(t)
        else:
            time_tuple = time.localtime(t)
            dst_then = time_tuple[-1]
            if dst_now != dst_then:
                if dst_now:
                    addend = 3600
                else:
                    addend = -3600
                time_tuple = time.localtime(t + addend)

        while new_rollover_at <= current_time:
            new_rollover_at += self.interval

        if (self.when == "MIDNIGHT" or self.when.startswith('W')) and not self.utc:
            dst_at_rollover = time.localtime(new_rollover_at)[-1]
            if dst_now != dst_at_rollover:
                if not dst_now:  # DST kicks in before next rollover, so we need to deduct an hour
                    addend = -3600
                else:  # DST bows out before next rollover, so we need to add an hour
                    addend = 3600
                new_rollover_at += addend
        self.rolloverAt = new_rollover_at

    def delete_old_files(self):
        dir_name, base_name = os.path.split(self.baseFilename)
        files = [os.path.join(dir_name, f) for f in os.listdir(dir_name) if os.path.isfile(os.path.join(dir_name, f))]

        for fn in files:
            if fn == self.baseFilename:
                continue
            if self.backupExpire and (time.time() - os.path.getmtime(fn)) > self.backupExpire:
                os.remove(fn)

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
    def __init__(self, timestamp_fmt, path_fmt, msg_fmt, color=0, mdc_format=None):
        full_fmt = f"{timestamp_fmt} {path_fmt}"
        super().__init__(full_fmt)
        self.timestamp_fmt = timestamp_fmt
        self.path_fmt = path_fmt
        self.msg_fmt = msg_fmt
        self.color = color
        self.mdc_format = mdc_format or ""

    def format(self, record):
        if self.color and (levelname := record.levelname) in COLORS:
            record.levelname = f"{COLOR_SEQ % (30 + COLORS[levelname])}{levelname}{RESET_SEQ}"

        timestamp_formatter = logging.Formatter(self.timestamp_fmt)
        timestamp_part = timestamp_formatter.format(record)

        path_formatter = logging.Formatter(self.path_fmt)
        path_part = path_formatter.format(record)

        msg_formatter = logging.Formatter(self.msg_fmt)
        msg_part = msg_formatter.format(record)

        mdc_part = ''
        if self.mdc_format and hasattr(record, "client_id") and record.client_id:
            try:
                # Ensure client_name exists, even if just a placeholder
                if not hasattr(record, "client_name") or not record.client_name:
                    record.client_name = '-'

                mdc_part = f" {self.mdc_format % record.__dict__}"
            except (KeyError, ValueError):
                pass

        return f"{timestamp_part} {path_part}{mdc_part} - {msg_part}"


class IRCDLogger:
    file_handler = None
    stream_handler = None
    log = None
    loghandlers = []

    @staticmethod
    def view_logging_info():
        logging.info("Logger initialised with settings:")

        mb_file = IRCDLogger.file_handler.maxBytes / 1_000_000
        max_bytes_formatted = f"{IRCDLogger.file_handler.maxBytes:_}".replace('_', '.')
        logging.info(f"Max bytes: {max_bytes_formatted} ({mb_file:.2f} MB per file)")
        logging.info(f"Backup count: {IRCDLogger.file_handler.backupCount}")

        sec = datetime.timedelta(seconds=IRCDLogger.file_handler.backupExpire)
        d = datetime.datetime(1, 1, 1) + sec
        expire_formatted = f"{IRCDLogger.file_handler.backupExpire:_}".replace('_', '.')
        logging.info(f"Backup expire: {expire_formatted} seconds ({d.year - 1} years, "
                     f"{d.month - 1} months, {d.day - 1} days)")

        max_size = IRCDLogger.file_handler.maxBytes * (IRCDLogger.file_handler.backupCount + 1)
        mb_size = max_size / 1_000_000
        max_size_formatted = f"{max_size:_}".replace('_', '.')
        logging.info(f"Max possible total logs size: {max_size_formatted} bytes ({mb_size:.2f} MB)")

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


timestamp_fmt = "[%(asctime)s]"
path_fmt = "{%(relativepath)s:%(lineno)d} %(levelname)s"
mdc_fmt = "- [%(client_id)s/%(client_name)s@%(client_ip)s]"
msg_fmt = "%(message)s"

log_paths = {
    "file": "logs/ircd.log",
    "warning": "logs/warning.log",
    "error": "logs/error.log",
    "exception": "logs/exception.log"}

# Create file handlers.
handlers = []
for path, level in zip(log_paths.values(), [logging.DEBUG, logging.WARNING, logging.ERROR, logging.ERROR]):
    handler = EnhancedRotatingFileHandler(path, when="midnight", maxbytes=1_000 * 1_000 * 10, backup_count=30, backup_expire=7_776_000)
    handler.setLevel(level)
    handler.setFormatter(LogFormatter(timestamp_fmt=timestamp_fmt, path_fmt=path_fmt, msg_fmt=msg_fmt, color=0, mdc_format=mdc_fmt))
    handler.addFilter(PackagePathFilter())
    handler.addFilter(mdc_filter)

    if level == logging.DEBUG:
        IRCDLogger.file_handler = handler

    # Fix so that error events do not end up in warning.log.
    if level == logging.WARNING:
        handler.addFilter(lambda record: record.levelno == logging.WARNING)

    handlers.append(handler)

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(LogFormatter(timestamp_fmt=timestamp_fmt, path_fmt=path_fmt, msg_fmt=msg_fmt, color=1, mdc_format=mdc_fmt))

stream_handler.addFilter(PackagePathFilter())
stream_handler.addFilter(mdc_filter)
handlers.append(stream_handler)
IRCDLogger.stream_handler = stream_handler

IRCDLogger.loghandlers.extend(handlers)
logging.basicConfig(level=logging.DEBUG, handlers=IRCDLogger.loghandlers)

logging.client_context = client_context
