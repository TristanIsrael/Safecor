# Automated installation of the PXE infrastructure for white stations

This documentation describes the use of Ansible to automatically deploy the services needed for the PXE boot of white stations, i.e. the ability to boot a white station over the network.

## Working principle

The automated deployment with Ansible installs and configures each of the selected services on one or several machines that will run these services. The deployment is configured using an *inventory* file.

## Compatibility

The installation scripts were written to deploy the services on machines with an Alpine Linux OS. In case a different OS is installed, the scripts must be adapted.

## Prerequisites

- Identify the services to install (dhcp, http, nfs, tftp). See the *description of the services* chapter.
- Create the VMs or prepare the machines that will host the services
  - The machines must have SSH access with a user account holding sudo rights
  - Python must be installed on the machines
- Identify the IP addresses, hostnames or DNS names of the target machines
- Identify the URL of the Alpine package repository (packages installed via the apk command)
- Identify the URL of the repository containing the Linux kernel files (vmlinux-virt, modloop-virt and initramfs-virt)
- Prepare the machine used for the deployment. See the *Deployment preparation* chapter.

## Description of the services

The services that can be installed are described below; the operator will decide whether to install them during the deployment configuration.

- DHCP: The DHCP service provides the IP address to the machines of the network segment but also (and above all) the information for the PXE boot. Without this information, no machine can boot over the network. (Default: no)

- TFTP: The TFTP service provides the PXE kernel file that is downloaded by the client machines at the beginning of the network boot. This service can be installed on the same machine as the HTTP or NFS server. (Default: yes)

- HTTP_NFS: The HTTP and NFS services must be on the same machine unless a file sharing server is used and it is mounted on both machines. These two services need to access the same files. (Default: yes)

  - The HTTP service provides the additional files for the network boot, in particular the Linux kernel and the configuration of the client machine. This server does not provide the binary repository for installing the distribution packages on the client machine (see the *Configuration* chapter). (Default: yes)

  - The NFS service provides a storage for the client machines configuration. This machine is only used by the white station integrator and is not needed in normal operation mode. (Default: no).

### Network boot sequence

To better understand the stakes of this installation, the following sequence explains the roles of each server.

- Boot of the client machine

- The client machine looks for a DHCP server to obtain an IP address.

- The installed DHCP server responds by giving a new IP address and a PXE boot configuration. This describes the location of a PXE kernel file to be downloaded by the client machine on a TFTP server.

- The client machine downloads the PXE kernel on the TFTP server at the address indicated by the DHCP server.

- The client machine boots on the PXE kernel

- The PXE kernel is configured to download the rest of its configuration and binaries (notably the Linux kernel) on an HTTP server. The data are downloaded on this HTTP server.

- The client machine boots on the Linux kernel.

- At the end of the boot on the Linux kernel, the configuration of the client machine (packages to install) is downloaded on the HTTP server.

- The configuration is applied on the client machine and the packages are downloaded on the Alpine package repository then installed.

- The client machine is ready.

#### Strategy for providing the Alpine kernels and packages

Two strategies are possible for providing the deployment artifacts:

1 - (**preferred**) The artifacts are provided by the integrator

The *depot_alpine* and *depot_noyaux* URLs are managed by the integrator. He provides them after having validated the non-regression on the packages made available (MCO and MCS).

In this scenario, the integrator has access to common resources (on Internet, DECOS or MEDUSA). He selects the branch of binaries he wants to use (version 3.15.5, 3.16.1, edge, etc) and downloads the packages to make them available on another repository, or in another directory that he controls. This latter is the one used for the network boot.

2 - (not recommended) The artifacts are provided on a common repository

The *depot_alpine* and *depot_noyau* URLs are generic and point to a repository that is regularly updated (for example DECOS or MEDUSA). This strategy has the drawback of not allowing the integrator to play his role and to test version upgrades on the new package and kernel versions.

## Installation of the infrastructure

This part describes the steps of the installation (or deployment) of the infrastructure for the PXE boot.

### Deployment preparation

A machine will be used to install and configure the different services on each server. This machine will use Ansible to perform all the actions.

It is therefore necessary to first create a virtual machine for the deployment. The virtual machine must be installed with a Linux OS (Alpine preferably). The installation guide below is adapted to Alpine Linux; for another distribution, the commands must be adapted.

### System configuration

Modify the /etc/apk/repositories file to match the example below and adapt the URLs according to your local configuration.

```
http://192.168.10.3/alpine/latest-stable/main/
http://192.168.10.3/alpine/latest-stable/community/
```

### Installation of the tools

```
$ sudo apk update
$ sudo apk upgrade
$ sudo apk add ansible sshpass
```

### Retrieving the project sources

```
$ mkdir -p ~/panoptiscan
$ cd ~/panoptiscan
$ git clone http://serveur_git/panoptiscan/panoptiscan.git
```

### Deployment configuration

To configure the installation, the following files must be modified.

#### inventory.yml

This file must be created from the example file inventory.yml.dist.

``` $ cp inventory.yml.dist inventory.yml```

Modify the file according to the installation context. To enable or disable a service, the corresponding variable must be modified in the defaults/main.yml file described below.

This file also defines variables that are essential to the installation. Adapt the variables according to the installation context.

| Variable     | Description                                   | Mandatory? | Default value |
|--------------|-----------------------------------------------|------------|---------------|
| install_dhcp | Defines whether the DHCP server must be installed | No         | no            |
| install_tftp | Defines whether the TFTP server must be installed | No         | yes           |
| install_http | Defines whether the HTTP server must be installed | Yes        | yes           |
| install_nfs  | Defines whether the NFS server must be installed | Yes        | yes           |
| depot_alpine | URL of the Alpine repository                   | Yes        |               |
| depot_noyaux | URL containing the Alpine Linux kernels        | Yes        |               |
| dhcp_domain       | Domain name for the local network | Yes | panoptiscan.lan |
| lan_subnet        | IPv4 subnet for the local network | Yes | 192.168.10.0 |
| lan_netmask       | IPv4 subnet mask for the local network | Yes | 255.255.255.0 |
| lan_ip_start      | Start of the range of IPv4 addresses distributed by the DHCP server | Yes | 192.168.10.10 |
| lan_ip_end        | End of the range of IPv4 addresses distributed by the DHCP server | Yes | 192.168.10.253 |
| lan_ip_broadcast  | IPv4 broadcast address for the local network | Yes | 192.168.10.255 |
| http_server  | IPv4 address of the HTTP server | 192.168.10.2 | |
| tftp_server  | IPv4 address of the TFTP server | 192.168.10.2 | |
| dhcp_server  | IPv4 address of the DHCP server | 192.168.10.1 | |
| nfs_server  | IPv4 address of the NFS server | 192.168.10.2 | |

**WARNING: the URLs must contain a / at the end of the line**

#### Using an existing DHCP server

If a DHCP server already exists, it must be configured to provide the boot information:

- enable network boot: enabled

- TFTP server address: *to fill in*

- next server: *enter the address of the TFTP server*

- default BIOS filename: gpxe.kpxe

### Running the installation

The installation is performed fully automatically by Ansible thanks to the following command:

```
$ cd ~/panoptiscan/ansible/deploy-infra-pxe
$ ansible-playbook -i inventory.yml deploy-infra-pxe.yml
```

At the end of the installation, a proper functioning verification is performed. It ensures that:

- The servers are reachable

- The services are functional

- The files are well available at the expected location.

*It is recommended to keep the deployment machine, or a backup, in order to more easily update the infrastructure later. At a minimum, the iventory.yml file must be kept.*

## Update

The update of the PXE boot infrastructure is done with the same tools as during the installation. The update steps are the following:

- Update the Alpine repository

- Update the Panoptiscan project files in the GIT repository or directly on the deployment machine

- Run the installation script (see the *Running the installation* chapter)

## Debt

This chapter presents the identified debt to be fixed.

| Type     | Description                                   |
|----------|-----------------------------------------------|
| SSI      | The filtering rule on the NFS service (/etc/exports) must be reviewed to only allow write access to the integrator. |
| SSI      | The access rights to the PXE data directory on the HTTP/NFS server are 0777 because there is no common group between HTTP and NFS. |

## Notes

### Raspberry Pi boot

- retrieve the alpine-rpi-*-aarch64.tar.gz archive and decompress it in /var/tftpboot on the TFTP server
- delete the /var/tftpboot/boot/*-rpi files and keep only the *-rpi4
- copy the /var/tftpboot/boot/modloop-rpi4 file in the /var/www/pxe/ directory
- on the Panoptiscan repository create a symbolic link between the x86_64 directory and the aarch64 directory
- install the clamav files in the repositories
