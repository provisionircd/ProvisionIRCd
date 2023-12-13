import logging.handlers
import datetime
import logging
import time
import sys
import os


class EnhancedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, filename, when='midnight', interval=1, backup_count=0, encoding=None, delay=0, utc=0, maxBytes=0, backupExpire=0):
        """ This is just a combination of TimedRotatingFileHandler and RotatingFileHandler (adds maxBytes to TimedRotatingFileHandler) """
        logging.handlers.TimedRotatingFileHandler.__init__(self, filename, when, interval, backup_count, encoding, delay, utc)

        self.maxBytes = maxBytes if maxBytes <= 1000 * 100000 else 1000 * 100000  # Limit single file to max. 100MB
        self.suffix = '%Y-%m-%d'
        self.filename = filename
        self.backupExpire = backupExpire if backupExpire <= 315569260 else 315569260  # Limit expire to max. 10 years.
        self.backupCount = backup_count if backup_count <= 999 else 999

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, see if the supplied record would cause the file to exceed
        the size limit we have.

        we are also comparing times
        """

        if self.stream is None:  # Delay was set...
            self.stream = self._open()
        if self.maxBytes > 0:  # Are we rolling over?
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  # Due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return 1
        if int(time.time()) >= self.rolloverAt:
            return 1
        return 0

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
            dfn = self.rotation_filename(self.baseFilename + "." + d + ".001")
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

        if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
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
        files = os.listdir(dir_name)
        for file in [file for file in files if os.path.join(dir_name, file) != self.baseFilename]:
            fn = os.path.join(dir_name, file)
            if not os.path.isfile(fn):
                continue
            logtimestamp = int(os.path.getmtime(fn))  # Based on last modify.
            diff = int(time.time()) - logtimestamp
            if self.backupExpire and diff > self.backupExpire:
                # print('Removing {} because it is >{} seconds old.'.format(file, diff))
                os.remove(fn)
                continue

            oldest = [os.path.join(dir_name, f) for f in files if os.path.isfile(os.path.join(dir_name, f))]
            oldest.sort(key=lambda f: int(os.path.getmtime(f) * 1000))

            exceed = len(oldest) - self.backupCount
            # print('Exceeding by {} files.'.format(exceed))
            if exceed > 0:
                remove_files = oldest[:exceed]
                # print('Remove {} files:'.format(len(remove_files)))
                for f in remove_files:
                    # print('os.remove({})'.format(f))
                    os.remove(f)


datefile = time.strftime('%Y%m%d')
if not os.path.exists('logs'):
    os.mkdir('logs')
filename = 'logs/ircd.log'

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

# The background is set with 40 plus the number of the color, and the foreground with 30

# These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"

COLORS = {
    'WARNING': YELLOW,
    'INFO': BLUE,
    'DEBUG': WHITE,
    'CRITICAL': YELLOW,
    'ERROR': RED
}


class PackagePathFilter(logging.Filter):
    def filter(self, record):
        pathname = record.pathname
        record.relativepath = None
        abs_sys_paths = map(os.path.abspath, sys.path)
        for path in sorted(abs_sys_paths, key=len, reverse=True):  # longer paths first
            if not path.endswith(os.sep):
                path += os.sep
            if pathname.startswith(path):
                record.relativepath = os.path.relpath(pathname, path)
                break
        return True


class LogFormatter(logging.Formatter):
    def __init__(self, fmt, color=0):
        self.color = color
        logging.Formatter.__init__(self, fmt=fmt)

    def format(self, record):
        levelname = record.levelname
        if self.color:
            if levelname in COLORS:
                levelname_color = COLOR_SEQ % (30 + COLORS[levelname]) + levelname + RESET_SEQ
                record.levelname = levelname_color
        return logging.Formatter.format(self, record)


class IRCDLogger:
    forked = 0
    file_handler = None
    stream_handler = None
    log = None
    loghandlers = []

    @staticmethod
    def view_logging_info():
        logging.info('Logger initialised with settings:')
        mb_file = IRCDLogger.file_handler.maxBytes * IRCDLogger.file_handler.backupCount
        mb_file = mb_file / IRCDLogger.file_handler.backupCount
        mb_file = float(mb_file) / 1000 / 1000
        mb_file = "%.2f" % mb_file
        logging.info(f'maxBytes: {IRCDLogger.file_handler.maxBytes} ({mb_file} MB per file)')

        logging.info(f'backupCount: {IRCDLogger.file_handler.backupCount}')

        sec = datetime.timedelta(seconds=IRCDLogger.file_handler.backupExpire)
        d = datetime.datetime(1, 1, 1) + sec
        logging.info(f'backupExpire: {IRCDLogger.file_handler.backupExpire} ({d.year - 1} years, {d.month - 1} months, {d.day - 1} days)')

        max_size = IRCDLogger.file_handler.maxBytes * (IRCDLogger.file_handler.backupCount + 1)  # Include base file.
        mb_size = float(max_size) / 1000 / 1000
        mb_size = "%.2f" % mb_size
        logging.info(f'Max possible total logs size: {max_size} bytes ({mb_size} MB)')

        logging.info(f'Logs will rotate log files with interval: {IRCDLogger.file_handler.when}')

        if max_size > 10000000000:
            gb_size = float(mb_size) / 1000
            gb_size = "%.2f" % gb_size
            logging.warning(f'Total log size limit exceeds 10GB: {gb_size} GB')
            logging.warning('Pausing for 5 seconds for visibility...')
            time.sleep(5)

    @staticmethod
    def fork():
        logging.getLogger().removeHandler(IRCDLogger.stream_handler)
        IRCDLogger.loghandlers.remove(IRCDLogger.stream_handler)

    @staticmethod
    def debug():
        IRCDLogger.stream_handler.setLevel(logging.DEBUG)


file_fmt = "[%(asctime)s] {%(relativepath)s:%(lineno)d} %(levelname)s - %(message)s"
file_handler = EnhancedRotatingFileHandler(filename, when='midnight', maxBytes=1_000 * 1_000, backup_count=30, backupExpire=2_629_744)
file_handler.setLevel(logging.DEBUG)
file_formatter = LogFormatter(fmt=file_fmt, color=0)
file_handler.setFormatter(file_formatter)
file_handler.addFilter(PackagePathFilter())
IRCDLogger.file_handler = file_handler
IRCDLogger.loghandlers.append(file_handler)

stream_fmt = "[%(asctime)s] {%(relativepath)s:%(lineno)d} %(levelname)s - %(message)s"
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_formatter = LogFormatter(fmt=stream_fmt, color=1)
stream_handler.setFormatter(stream_formatter)
stream_handler.addFilter(PackagePathFilter())
IRCDLogger.stream_handler = stream_handler
IRCDLogger.loghandlers.append(stream_handler)

logging.basicConfig(level=logging.DEBUG, handlers=IRCDLogger.loghandlers)
# IRCDLogger.view_logging_info()
