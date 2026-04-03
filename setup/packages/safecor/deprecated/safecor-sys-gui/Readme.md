# safecor-sys-gui

This package provides an isolated access to the graphical device. The Graphical User Interface of your product must be constructed on top of this package.

As a result, a new VM `sys-gui` is automatically created and started when the system boots up.

**The `sys-gui` VM is created only if this package is added to your product as a dependency.**

## What is done

- A XEN configuration file is created for the `sys-gui` VM. 
- A set of scripts are created in order to detect the GUI and attach them to the `sys-gui` VM.

## Isolation

The isolation is configured with a PCI passthru. The setup of the GPU is fully handled by this package, the product-specific package has no additional configuration to do.
The GUI is available in the `sys-gui` VM as a regular GUI.

## Performance

Depending on the GPU, different functions are available in the `sys-gui` virtual machine.

## Integration

In order to use the `sys-gui` VM in your product you need to add the package `safecor-sys-gui` to your own package, by editing the `APKBUILD` file and set the following line :
```
depends='safecor-sys-gui'
```

**An example of integration using the `sys-gui` VM is available with the `safecor-diag` package.**
