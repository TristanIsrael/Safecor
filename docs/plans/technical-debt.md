# Technical debt

This document identifies and follows the technical debt of Safecor.

## Documentation

- Some functions of the python source code are not documented or their documentation is not up-to-date (for example Dom0Controller.start()).
- Private functions are not well documented.
- The shell scripts are not documented. They should have inline documentation to explain their algorithm

## Project structure

- The file `AGENTS.md` gathers all the rules. It should be divided into several smaller files:
  - The files related to *processes* should be rewritten in skills
  - The files related to *rules* should be rewritten in thematic documentation files.
- The documentation structure should be:
  - The file `AGENTS.md` should concentrate the technical description of the project for a quick overview of the technical stack, and it should reference other specific files for the different topics (architecture, coding conventions, testing, general rules, documentation, etc)
  - The `docs/` folder should contain the following folders with their related files:
```
docs/
   ├── architecture/
   ├── specifications/
   ├── decisions/
   └── development/
```

## Technical concerns

- The Alpine packages are downloaded during the first setup of the product (by a calll to `/usr/lib/safecor/bin/post-install.sh`) and then the packages are bundled into a squashfs file. In a future release the squashfs file should be bundled in the installation medium (it should be built in the CI and not on the system).
- In Alpine 4.24, QEMU v. 11.0.3 is bundled and the command line crafted by Xen is not compatible with this QEMU version: `-machine xenfv` does not exist. `-machine xenfv-4.2` should be used instead.

## Security

- There is no monitoring on the security aspects of the project. The supply chain should be monitored (Alpine Linux, Xen, Qemu) and the vulnerabilities should be analyzed and fixed as soon as possible.
