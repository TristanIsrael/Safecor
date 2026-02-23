import syslog

class SysLogger():
    """ This class is a logger that sends messages to the system logger facility (syslog) 
    """

    def __init__(self, module_name:str):
        self.__module_name = module_name

        syslog.openlog(
            ident=f"Safecor/{self.__module_name}",
            logoption=syslog.LOG_PID,
            facility=syslog.LOG_DAEMON
        )

    def __del__(self):
        syslog.closelog()

    def critical(self, description:str):
        """ Sends a critical message """

        print(description)
        syslog.syslog(syslog.LOG_EMERG, description)

    def error(self, description:str):
        """ Sends an error message """

        print(description)
        syslog.syslog(syslog.LOG_ERR, description)

    def warning(self, description:str):
        """ Sends a warning message """

        print(description)
        syslog.syslog(syslog.LOG_WARNING, description)

    def warn(self, description:str):
        """ Sends a warning message 

            Synonym of :func:`warning`.
        """

        print(description)
        syslog.syslog(syslog.LOG_WARNING, description)

    def info(self, description:str):
        """ Sends an information message """

        #print(description)
        syslog.syslog(syslog.LOG_INFO, description)

    def debug(self, description:str):
        """ Sends a debugging message """

        #print(description)
        syslog.syslog(syslog.LOG_DEBUG, description)