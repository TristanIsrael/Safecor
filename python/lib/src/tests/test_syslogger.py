import unittest
import unittest.mock as mock

from safecor import SysLogger
import safecor._syslogger as _syslogger


class TestSysLogger(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch.object(_syslogger, "syslog")
        self.mock_syslog = patcher.start()
        self.addCleanup(patcher.stop)
        self.logger = SysLogger("test_module")

    def test_openlog_on_init(self):
        self.mock_syslog.openlog.assert_called_once()
        _, kwargs = self.mock_syslog.openlog.call_args
        self.assertEqual(kwargs["ident"], "Safecor/test_module")

    def test_critical(self):
        self.logger.critical("a critical message")
        self.mock_syslog.syslog.assert_called_with(self.mock_syslog.LOG_EMERG, "a critical message")

    def test_error(self):
        self.logger.error("an error")
        self.mock_syslog.syslog.assert_called_with(self.mock_syslog.LOG_ERR, "an error")

    def test_warning(self):
        self.logger.warning("a warning")
        self.mock_syslog.syslog.assert_called_with(self.mock_syslog.LOG_WARNING, "a warning")

    def test_warn_synonym(self):
        self.logger.warn("a warning via warn")
        self.mock_syslog.syslog.assert_called_with(self.mock_syslog.LOG_WARNING, "a warning via warn")

    def test_info(self):
        self.logger.info("an info")
        self.mock_syslog.syslog.assert_called_with(self.mock_syslog.LOG_INFO, "an info")

    def test_debug(self):
        self.logger.debug("a debug")
        self.mock_syslog.syslog.assert_called_with(self.mock_syslog.LOG_DEBUG, "a debug")


if __name__ == "__main__":
    unittest.main()
