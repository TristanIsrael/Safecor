# Panoptiscan

 Panoptiscan

## Use cases to handle

- Log the performance and the memory consumption in DEBUG mode

- Deacidize the files on the station to scan them

## Requirements

- The white station must not have any mass storage device connected (hard disk, memory card)

- It must be built from an approved master, this master must be verified

- In case of virus detection, copy only the clean files

- The scan journal is copied at the same time as the files

## Approaches considered

- Definition of a master with YOCTO, easily modifiable, mastered and deployable -> Output in IMG format

## Bug fixes

- OK after inserting the first media: change the message "Insert a second USB key"

- After the scan:

- OK hide the progress bar

- Display the result figures

- Display the copy button and the eject button side by side

- Add a button to power off the device

## Debugging

- https://github.com/pyutils/line_profiler

## Icons

https://iconsplace.com/custom-color/eject-icon-17/
