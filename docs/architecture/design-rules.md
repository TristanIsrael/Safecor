# Safecor Design Rules

> **Scope**: the design rules and guidelines that govern all the features of Safecor (offline copy of the Wiki `Design-rules` page).
>
> **Last updated**: 2026-11-20

The table below presents the rules guiding the design of the platform and their impact on operational maintenance (OCM), security maintenance (SCM), ease of integration of business components, and performance.

| Id | Rule | OCM | SCM | Integration | Performance |
|--|--|--|--|--|--|
| #1 | Use of off-the-shelf software and libraries | x | x | | |
| #2 | Use of standard protocols | x | x | x | |
| #3 | Components from mainstream channels | x | x | | |
| #4 | Use of lightweight software and libraries | | | | x |
| #5 | Use of robust software and libraries | | x | | |
| #6 | Provision of an API | | x | | |
| #7 | Provision of built-in debugging tools | x | x | x | x |
| #8 | Stateless system | | x | | |
| #9 | Configuration management | x | x | x | x |
| #10 | Always reduce attack surface | x | x | | |

## Use of off-the-shelf software and libraries

The platform mainly relies on Alpine Linux, Mosquitto, XOrg, and python.

**Alpine Linux** provides several crucial features and capabilities to meet the design rules:

- Ultra-lightweight: it allows creating a system with a very small memory and disk footprint, mainly due to the use of the MUSL system library, Busybox, and OpenRC.
- Enhanced security: all packages are compiled with security options such as stack-smashing protection, PIE, and fortify source.
- Powerful, fast, and lightweight package manager (APK).
- Modular: default minimal installation and enhanced capabilities by adding component packages.
- Fast booting thanks to its lightweight and modular nature.
- Rolling release distribution with continuous updates without the need for a complete reinstallation.

**Mosquitto** is an MQTT broker that provides inter-application and inter-component messaging capabilities.

**XOrg** is a display server for graphical user interfaces. It allows business applications to display their graphical interface on the system's screen.

**python** is an interpreter and programming language. It offers easy integration capabilities as it does not impose any compilation chain or software factory for developing software building blocks for the product.

## Use of standard protocols

The platform uses the MQTT protocol for messaging and notification functions, allowing it to rely on a mature and well-understood communication mechanism. Business components can communicate with each other, send commands to the platform, and receive notifications using this protocol.

## Components from mainstream channels

All the software used comes from one of the two official binary repositories of Alpine Linux: `main` and `community`.

This way, as soon as a security patch or bug fix is published, the platform and products can benefit from an upgrade simply by updating the installed packages.

## Use of lightweight software and libraries

The choice of components on which the platform relies was made based on strict criteria of lightweight nature and performance. When multiple components can serve the same function, the choice is made based on the component's disk and memory footprint, as well as its performance (speed, stability).

## Use of robust software and libraries

Similarly, the robustness of a component is considered when it may be exploited as a vector for a threat. While the Alpine Linux packages are compiled with options that enhance their security, vulnerabilities may still exist in these components. The CVE system is used and monitored to confirm or reject the choices of critical components in the platform.

## Provision of an API

The provision of an API is a crucial element for facilitating the integration of business components and enabling rapid product creation. The provided API allows for easy invocation of platform functions and sending notifications, either through a python function call or by sending an MQTT message.

## Provision of built-in debugging tools

The platform offers an integrated mechanism that facilitates debugging of business applications. The API provides functions such as `debug`, `warn`, `critical`, among others, that allow propagating debugging messages or system statuses. When the system is configured in debugging mode, these messages can then be captured from a device connected via an RS-232 serial port. All debugging and system information messages are also centralized by the platform and can be serialized on demand into a text file.

## Stateless system

The stateless nature of the platform is its main guarantee against integrity breaches (see [../security/security-model.md](../security/security-model.md)). It is immune to any attempt to compromise its integrity. In return, it does not provide any permanent storage functionality, databases, or recovery from previous states. As a result, business components must manage their own permanent storage when necessary, particularly by using external storage.

## Configuration management

The platform facilitates hardware and software configuration management through the use of a description file called `topology.json`. This file allows defining one or more software configurations and associating them with hardware configurations. For example, the system integrator or designer can choose to enable or disable the GUI, the use of USB ports, or the memory allocated to a business component. They can also prohibit the use of one or more PCI peripherals. Using the APK package manager in product packaging also allows fine-grained specification of which software packages will be used by the system, with a dependency system that allows choosing the components of the platform to be used.

The available platform packages are:

- `safecor-core` — this package is essential.
- `safecor-lib` — this package allows installing the API into a system component. It is optional.
- `safecor-gui-base` — this package initializes the graphical environment for displaying the GUI in a system component. It is optional.
- `safecor-sys-gui` — this package initializes access to the system's graphics card. It will not be installed if the product does not include a graphical interface.
- `safecor-sys-usb` — this package enables the use of USB peripherals on the hardware. It will not be installed if the product does not enable USB functionality.
- `safecor-container-debian` — this package installs an LXC container with a Debian Linux system to run programs that are incompatible with Alpine Linux or require glibc. It is meant to be installed into a virtual machine and run in memory.

## Always reduce attack surface

The attack surface of the platform is reduced systematically: every component that is not strictly needed is removed, every service runs unprivileged (see [../security/security-model.md](../security/security-model.md)), and the decisions taken on the architecture are recorded in [decisions/](decisions/README.md).
