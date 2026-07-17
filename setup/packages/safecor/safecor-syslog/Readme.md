# safecor-syslog

This package provides a syslog facility for Domains.

The logging can be done multiple ways:
- Using the official Safecor python API (with safecor-lib package).
- Using a syslog client or library (with this package).

This facility is useful for integrating third-party software that already use syslog. It behaves like a bridge between syslog in the DomU and the Safecor's logging facility. 

At the end, all logs are gathered in the same file and can be exported using the API.

## Dependencies

- safecor-lib
  

