import logging
import os
import io
import unittest
import unittest.mock as mock
from contextlib import redirect_stdout

from safecor import Logger, Topics
import safecor._logger as _logger


class TestLoggerUnit(unittest.TestCase):

    def setUp(self):
        self._patcher = mock.patch.object(_logger, "System", mock.MagicMock())
        self._patcher.start()
        self.addCleanup(self._patcher.stop)
        _logger.System.domain_name.return_value = "testdomain"

        self.tmpfile = "/tmp/safecor_unit_test.log"
        if os.path.exists(self.tmpfile):
            os.remove(self.tmpfile)

        self.mqtt = mock.MagicMock()
        Logger().reset()

    def tearDown(self):
        Logger().reset()
        if os.path.exists(self.tmpfile):
            os.remove(self.tmpfile)

    def _setup(self, recording=True):
        Logger().setup("mod", self.mqtt, logging.INFO, recording, self.tmpfile)

    # --- setup / getters -------------------------------------------------

    def test_setup_and_getters(self):
        self._setup()
        logger = Logger()
        self.assertTrue(logger.is_setup())
        self.assertEqual(logger.module_name(), "mod")
        self.assertEqual(logger.filename(), self.tmpfile)
        self.assertTrue(logger.is_recording())
        self.assertEqual(logger.log_level(), logging.INFO)
        self.assertEqual(logger.domain_name(), "testdomain")
        self.mqtt.add_message_callback.assert_called_once()
        self.mqtt.subscribe.assert_called_once_with(f"{Topics.EVENTS}/#")

    def test_setup_idempotent(self):
        self._setup()
        Logger().setup("other", self.mqtt, logging.ERROR, False, "/other.log")
        # Second setup is ignored because the facility is already set up
        self.assertEqual(Logger().module_name(), "mod")
        self.assertEqual(Logger().log_level(), logging.INFO)

    def test_setup_no_recording(self):
        Logger().setup("mod", self.mqtt, logging.INFO, False, self.tmpfile)
        self.assertFalse(Logger().is_recording())
        self.mqtt.subscribe.assert_not_called()

    # --- event publishing ------------------------------------------------

    def test_event_methods(self):
        self._setup()
        logger = Logger()
        logger.info("an info")
        self.mqtt.publish.assert_called_with("system/events/info", mock.ANY)
        logger.error("an error")
        self.mqtt.publish.assert_called_with("system/events/error", mock.ANY)
        logger.warning("a warning")
        self.mqtt.publish.assert_called_with("system/events/warning", mock.ANY)
        logger.warn("a warn")
        self.mqtt.publish.assert_called_with("system/events/warning", mock.ANY)
        logger.debug("a debug")
        self.mqtt.publish.assert_called_with("system/events/debug", mock.ANY)
        logger.critical("a critical")
        self.mqtt.publish.assert_called_with("system/events/critical", mock.ANY)

    def test_event_payload_content(self):
        self._setup()
        Logger().info("the message", "custom_module")
        _, payload = self.mqtt.publish.call_args[0]
        self.assertEqual(payload["component"], "testdomain")
        self.assertEqual(payload["module"], "custom_module")
        self.assertEqual(payload["description"], "the message")
        self.assertIn("datetime", payload)

    def test_event_module_default(self):
        self._setup()
        Logger().info("the message")
        _, payload = self.mqtt.publish.call_args[0]
        self.assertEqual(payload["module"], "mod")

    def test_event_not_setup_no_publish(self):
        Logger().reset()
        Logger().info("should not publish")
        self.mqtt.publish.assert_not_called()

    # --- log level -------------------------------------------------------

    def test_set_log_level(self):
        self._setup()
        Logger().set_log_level(logging.ERROR)
        self.assertEqual(Logger().log_level(), logging.ERROR)

    def test_on_message_set_log_level(self):
        self._setup()
        Logger()._Logger__on_message(Topics.SET_LOG_LEVEL, {"level": 40})
        self.assertEqual(Logger().log_level(), 40)

    # --- write log (recording) ------------------------------------------

    def test_on_message_write_log(self):
        self._setup()
        Logger()._Logger__on_message(
            "system/events/info",
            {"datetime": "2025-01-01 00:00:00", "module": "mod", "description": "a logged line"}
        )
        with open(self.tmpfile, "r") as f:
            content = f.read()
        self.assertIn("a logged line", content)
        self.assertIn("[info]", content)

    def test_on_message_write_log_filtered_by_level(self):
        self._setup()
        # Raise the level so that info is filtered out
        Logger().set_log_level(logging.CRITICAL)
        Logger()._Logger__on_message(
            "system/events/info",
            {"datetime": "2025-01-01 00:00:00", "module": "mod", "description": "filtered out"}
        )
        if os.path.exists(self.tmpfile):
            with open(self.tmpfile, "r") as f:
                self.assertNotIn("filtered out", f.read())

    # --- save log --------------------------------------------------------

    def test_on_message_save_log(self):
        self._setup()
        with open(self.tmpfile, "wb") as f:
            f.write(b"existing log content\n")
        Logger()._Logger__on_message(Topics.SAVE_LOG, {"disk": "out", "filename": "file.txt"})
        self.mqtt.publish.assert_called()
        topic, payload = self.mqtt.publish.call_args[0]
        self.assertEqual(topic, f"{Topics.CREATE_FILE}/request")
        self.assertEqual(payload["filepath"], "/file.txt")
        self.assertEqual(payload["disk"], "out")
        self.assertTrue(payload["compressed"])

    def test_on_message_save_log_missing_args(self):
        self._setup()
        Logger()._Logger__on_message(Topics.SAVE_LOG, {})
        # An error event is published, not a create_file request
        topics_published = [c[0][0] for c in self.mqtt.publish.call_args_list]
        self.assertNotIn(f"{Topics.CREATE_FILE}/request", topics_published)

    # --- reset / clear ---------------------------------------------------

    def test_reset(self):
        self._setup()
        Logger().reset()
        self.assertFalse(Logger().is_setup())
        self.mqtt.unsubscribe_all.assert_called()
        self.mqtt.del_message_callback.assert_called()

    def test_clear_log(self):
        self._setup()
        with open(self.tmpfile, "w") as f:
            f.write("some content")
        Logger().clear_log()
        with open(self.tmpfile, "r") as f:
            self.assertEqual(f.read(), "")

    # --- static helpers --------------------------------------------------

    def test_loglevel_value(self):
        self.assertEqual(Logger.loglevel_value("debug"), logging.DEBUG)
        self.assertEqual(Logger.loglevel_value("info"), logging.INFO)
        self.assertEqual(Logger.loglevel_value("warn"), logging.WARN)
        self.assertEqual(Logger.loglevel_value("warning"), logging.WARN)
        self.assertEqual(Logger.loglevel_value("error"), logging.WARN)
        self.assertEqual(Logger.loglevel_value("critical"), logging.CRITICAL)
        self.assertEqual(Logger.loglevel_value("unknown"), logging.NOTSET)

    def test_loglevel_from_topic(self):
        self.assertEqual(Logger.loglevel_from_topic("system/events/debug"), logging.DEBUG)
        self.assertEqual(Logger.loglevel_from_topic("system/events/critical"), logging.CRITICAL)

    def test_format_logline(self):
        line = Logger.format_logline("hello world")
        self.assertTrue(line.endswith(" - hello world"))
        # 4 chars of the year
        self.assertRegex(line[:4], r"^\d{4}$")

    def test_print(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            Logger.print("printed message")
        self.assertIn("printed message", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
