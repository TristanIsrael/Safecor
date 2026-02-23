# Installation automatisée de l'infrastructure PXE pour les stations blanches

Cette documentation décrit l'utilisation d'Ansible pour déployer automatiquement les services nécessaires à la mise en oeuvre du boot PXE pour les stations blanches, c'est-à-dire la capacité à démarrer une station blanche par le réseau.

## Principe de fonctionnement

Le déploiement automatisé avec Ansible va installer et configurer chacun des services sélectionnés sur une ou plusieurs machines qui exécuterons ces services. Le déploiement est configuré à l'aide d'un fichier d'*inventaire*.

## Compatibilité

Les scripts d'installation ont été écrits pour déployer les services sur des machines avec un OS Alpine Linux. Dans le cas où un OS différent serait installé, les scripts devront être adaptés.

## Pré-requis

- Identifier les services à installer (dhcp, http, nfs, tftp). Voir le chapitre *description des services*.
- Créer les VM ou préparer les machines qui vont accueillir les services
  - Les machines doivent avoir un accès SSH avec un compte d'utilisateur possédant les droits sudo
  - Python doit être installé sur les machines
- Identifier les adresses IP, noms d'hôtes ou noms DNS des machines cibles
- Identifier l'URL du dépôt des paquets Alpine (paquets installés via la commande apk)
- Identifier l'URL du dépôt contenant les fichiers du noyau Linux (vmlinux-virt, modloop-virt et initramfs-virt)
- Préparer la machine utilisée pour le déploiement. Voir le chapitre *Préparation au déploiement*.

## Description des services

Les services qui peuvent être installés sont décrits ci-dessous, l'opérateur décidera de les installer ou non lors de la configuration du déploiement.

- DHCP : Le service DHCP fournit l'adresse IP aux machines du segment réseau mais également (et surtout) les informations pour le boot PXE. Sans cette information, aucune machine ne pourra démarrer par le réseau. (Défaut : no)

- TFTP : Le service TFTP fournit le fichier noyau PXE qui est téléchargé par les machines clients au début du démarrage par le réseau. Ce service peut être installé sur la même machine que le serveur HTTP ou NFS. (Défaut : yes)

- HTTP_NFS : Les services HTTP et NFS doivent être sur la même machine sauf si un serveur de partage de fichiers est utilisé et qu'il est monté sur les deux machines. Ces deux services ont besoin d'accéder aux mêmes fichiers. (Défaut : yes)

  - Le service HTTP fournit les fichiers supplémentaires pour le démarrage par le réseau, en particulier le noyau Linux et la configuration de la machine cliente. Ce serveur ne fournit pas le dépôt de binaires pour l'installation des paquets de la distribution sur la machine cliente (Voir le chapitre *Configuration*). (Défaut : yes)

  - Le service NFS fournit un stockage pour la configuration des machines clients. Cette machine n'est utilisée que par l'intégrateur des stations blanches et n'est pas nécessaire dans le mode de fonctionnement normal. (Défaut : no).

### Cinématique du démarrage par le réseau

Pour mieux comprendre l'enjeu de cette installation, la cinématique suivante explique les rôles de chaque serveur.

- Démarrage de la machine cliente

- La machine cliente cherche un serveur DHCP pour obtenir une adresse IP.

- Le serveur DHCP installé répond en donnant une nouvelle adresse IP et une configuration de boot PXE. Celle-ci décrit l'emplacement d'un fichier de noyau PXE à télécharger par la machine clience sur un serveur TFTP.

- La machine cliente télécharge le noyau PXE sur le serveur TFTP à l'adresse indiquée par le serveur DHCP.

- La machine client boote sur le noyau PXE

- Le noyau PXE est configuré pour télécharger le reste de sa configuration et des binaires (notamment le noyau Linux) sur un serveur HTTP. Les données sont téléchargées sur ce serveur HTTP.

- La machine cliente boote sur le noyau Linux.

- A la fin du boot sur le noyau Linux, la configuration de la machine cliente (paquets à installer) est téléchargée sur le serveur HTTP.

- La configuration est appliquée sur la machine cliente et les paquets sont téléchargés sur le dépôt de paquets Alpine puis installés.

- La machine cliente est prête.

#### Stratégie de mise à disposition des noyaux et paquets Alpine

Deux stratégies sont possibles pour la mise à disposition des artefacts de déploiement :

1 - (**préférée**) Les artefacts sont mis à disposition par l'intégrateur

Les URL *depot_alpine* et "depot_noyaux* sont gérées par l'intégrateur. Il les fournit après avoir validé la non-régression sur les paquets mis à disposition (MCO et MCS).

Dans ce scénario, l'intégrateur a accès à des ressources communes (sur Internet, DECOS ou MEDUSA). Il sélectionne la branche des binaires qu'il souhaite utiliser (version 3.15.5, 3.16.1, edge, etc) et télécharge les paquets pour les mettre à disposition sur un autre dépôt, ou dans un autre répertoire qu'il maîtrise. C'est ce dernier qui sera utilisé pour le démarrage par le réseau.

2 - (non recommandée) Les artefacts sont mis à disposition sur un dépôt commun

Les URL *depot_alpine* et *depot_noyau* sont génériques et pointent sur un dépôt qui est mis à jour régulièrement (exemple DECOS ou MEDUSA). Cette stratégie a le défaut de ne pas permettre à l'intégrateur de jouer son rôle et de tester les montées de version sur les nouvelles versions de paquet et de noyau.

## Installation de l'infrastructure

Cette partie décrit les étapes de l'installation (ou déploiement) de l'infrastructure pour le boot PXE.

### Préparation au déploiement

Une machine va être utilisée pour installer et configurer les différents services sur chaque serveur. Cette machine utiliser Ansible pour réaliser toutes les actions.

Il faut donc tout d'abord créer une machine virtuelle pour le déploiement. La machine virtuelle devra être installée avec un OS Linux (Alpine de préférence). Le guide d'installation ci-dessous est adapté à Alpine Linux, pour une autre distribution, les commandes devront être adaptées.

### Configuration du système

Modifier le fichier /etc/apk/repositories pour qu'il corresponde à l'exemple ci-dessous et adapter les URL en fonction de votre configuration locale.

```
http://192.168.10.3/alpine/latest-stable/main/
http://192.168.10.3/alpine/latest-stable/community/
```

### Installation des outils

```
$ sudo apk update
$ sudo apk upgrade
$ sudo apk add ansible sshpass
```

### Récupération des sources du projet

```
$ mkdir -p ~/panoptiscan
$ cd ~/panoptiscan
$ git clone http://serveur_git/panoptiscan/panoptiscan.git
```

### Configuration du déploiement

Pour configurer l'installation il faut modifier les fichiers suivants.

#### inventory.yml

Ce fichier doit être créé à partir du fichier exemple inventory.yml.dist.

``` $ cp inventory.yml.dist inventory.yml```

Modifier le fichier en fonction du contexte de l'installation. Pour activer ou désactiver un service, il faut modifier la variable correspondante dans le fichier defaults/main.yml décrit ci-dessous.

Ce fichier définit également des variables indispensables à l'installation. Adapter les variables en fonction du contexte de l'installation.

| Variable     | Description                                   | Obligatoire ? | Valeur par défaut |
|--------------|-----------------------------------------------|---------------|-------------------|
| install_dhcp | Définit si le serveur DHCP doit être installé | Non           | no                |
| install_tftp | Définit si le serveur TFTP doit être installé | Non           | yes               |
| install_http | Définit si le serveur HTTP doit être installé | Oui           | yes               |
| install_nfs | Définit si le serveur NFS doit être installé | Oui           | yes               |
| depot_alpine | URL du dépôt Alpine                           | Oui           |                   |
| depot_noyaux | URL contenant les noyaux Linux Alpine         | Oui           |                   |
| dhcp_domain       | Nom de domaine pour le réseau local | Oui | panoptiscan.lan |
| lan_subnet        | Sous-réseau IPv4 pour le réseau local | Oui | 192.168.10.0 |
| lan_netmask       | Masque de sous-réseau IPv4 pour le réseau local | Oui | 255.255.255.0 |
| lan_ip_start      | Début de la plage d'adresses IPv4 distribuées par le serveur DHCP | Oui | 192.168.10.10 |
| lan_ip_end        | Fin de la plage d'adresses IPv4 distribuées par le serveur DHCP | Oui | 192.168.10.253 |
| lan_ip_broadcast  | Adresse IPv4 de broadcast pour le réseau local | Oui | 192.168.10.255 |
| http_server  | Adresse IPv4 du serveur HTTP | 192.168.10.2 | |
| tftp_server  | Adresse IPv4 du serveur TFTP | 192.168.10.2 | |
| dhcp_server  | Adresse IPv4 du serveur DHCP | 192.168.10.1 | |
| nfs_server  | Adresse IPv4 du serveur NFS | 192.168.10.2 | |

**ATTENTION : les URL doivent contenir un / en fin de ligne**

#### Utilisation d'un serveur DHCP existant

Si un serveur DHCP existe déjà, il faut le configurer pour qu'il donne les informations de boot :

- activer le boot réseau : activé

- adresse du serveur TFTP : *à remplir*

- prochain serveur : *saisir l'adresse du serveur TFTP*

- nom de fichier BIOS par défaut : gpxe.kpxe

### Exécution de l'installation

L'installation est réalisée de façon totalement automatisée par Ansible grâce à la commande suivante :

```
$ cd ~/panoptiscan/ansible/deploy-infra-pxe
$ ansible-playbook -i inventory.yml deploy-infra-pxe.yml
```

A la fin de l'installation, une vérification de bon fonctionnement. Elle s'assure que :

- Les serveurs sont joignables

- Les services sont fonctionnels

- Les fichiers sont bien disponibles à l'endroit attendu.

*Il est recommandé de conserver la machine de déploiement, ou une sauvegarde, afin de mettre à jour plus facilement l'infrastructure ultérieurement. Au minimum il faudra conserver le fichier iventory.yml.*

## Mise à jour

La mise à jour de l'infrastructure de boot PXE se fait avec les mêmes outils que lors de l'installation. Les étapes de mise à jour sont les suivantes :

- Mise à jour du dépôt Alpine

- Mise à jour des fichiers du projet Panoptiscan dans le dépôt GIT ou directement sur la machine de déploiement

- Exécution du script d'installation (voir chapitre *Exécution de l'installation*)

## Dette

Ce chapitre présente la dette identifiée et à corriger.

| Type     | Description                                   |
|----------|-----------------------------------------------|
| SSI      | La règle de filtrage sur le service NFS (/etc/exports) doit être revue pour ne permettre l'accès en écriture qu'à l'intégrateur. |
| SSI      | Les droits d'accès au répertoire de données PXE sur le serveur HTTP/NFS sont 0777 car il n'y a pas de groupe commun entre HTTP et NFS. |

## Notes

### Boot raspberry Pi

- récupérer l'archive alpine-rpi-*-aarch64.tar.gz et la décompresser dans /var/tftpboot sur le serveur TFTP
- supprimer les fichiers /var/tftpboot/boot/*-rpi et ne conserver que les *-rpi4
- copier le fichier /var/tftpboot/boot/modloop-rpi4 dans le dossier /var/www/pxe/
- sur le dépot Panoptiscan créer un lien symbolique entre le dossier x86_64 et le dossier aarch64 
- installer les fichiers clamav dans les dépôts