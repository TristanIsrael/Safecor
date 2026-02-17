# Safecor Tests

Safecor Tests is the host application for all the functional tests and non-regression tests of Safecor.

This application is supposed to be ran on a fully compatible system (see [Prerequisites](https://github.com/TristanIsrael/Safecor/wiki/Prerequisistes)).

## Build

The ISO image is built with `mkimage.sh` and the scripts `mkimg.tests.sh` and `genapkvol-tests.sh` located in the directory `setup/iso/tests`.

## Screenshot

![Screenshot of Safecor Tests](misc/tests-app.png)

## Create a USB disk (x86 only)

- Download the image file [safecor-tests-x86_64.iso](https://www.alefbet.net/github/safecor/iso/safecor-tests-x86_64.iso).
- Format a USB disk in FAT.
- Use a software like `Rufus` or `dd` to put the image on the disk.
- Boot on the USB disk

## Documentation

