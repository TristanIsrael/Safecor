# Alpine package `safecor-tests`

This package sets the system with an end-to-end test GUI. It provides only the system configuration. 
The end-user application is provided by the package `safecor-tests-gui`.

## Dependencies

Here is the dependencies tree for this product:

- safecor-tests
  - safecor-lib 
  - safecor-core 
  - safecor-sys-gui

## Build process

This product is intended to be built as an ISO image and booted from a USB key.

The ISO image is built by `mkimage.sh` and the scripts `mkimg.diag.sh` and `genapkovl-diag.sh` located in `setup/iso/tests`.

## Documentation

- [Tests wiki page](https://github.com/TristanIsrael/Safecor/wiki/Tests)