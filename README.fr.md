# Safecor - un système d’exploitation pour produits de sécurité

![Usage restreint](https://img.shields.io/badge/Usage-Restricted-red)
![Pas de redistribution](https://img.shields.io/badge/Redistribution-Disallowed-red)
![Contributions via le dépôt](https://img.shields.io/badge/Contributions-Repo-blue)

[![plateforme](https://img.shields.io/badge/platforme-Alpine-Linux.svg)](https://gbatemp.net/forums/nintendo-switch.283/?prefix_id=44)
[![langage](https://img.shields.io/badge/langage-Python-ba1632.svg)](https://github.com/topics/cpp)
[![Licence propriétaire](https://img.shields.io/badge/licence-Proprietary-189c11.svg)](https://www.gnu.org/licenses/old-licenses/gpl-3.0.en.html)
[![Dernière version](https://img.shields.io/github/v/release/TristanIsrael/Safecor?label=latest&color=blue)](https://github.com/TristanIsrael/Safecor/releases/latest)
[![Téléchargements](https://img.shields.io/github/downloads/TristanIsrael/Safecor/total?color=6f42c1)](https://github.com/TristanIsrael/Safecor/graphs/traffic)
[![Problèmes GitHub](https://img.shields.io/github/issues/TristanIsrael/Safecor?color=222222)](https://github.com/TristanIsrael/Safecor/issues)
[![Étoiles GitHub](https://img.shields.io/github/stars/TristanIsrael/Safecor)](https://github.com/TristanIsrael/Safecor/stargazers)
![CI](https://github.com/TristanIsrael/Safecor/actions/workflows/build-all.yml/badge.svg)

**Ce projet fournit une architecture logicielle pour créer des produits de sécurité.**

> ⚠️ **Avis important**

Ce dépôt est soumis à une licence restrictive.  
Vous **n’êtes pas autorisé à forker, copier, modifier ou réutiliser** ce code sous quelque forme que ce soit, y compris via les fonctionnalités GitHub, **sans l’autorisation écrite explicite** de l’auteur.

## 📚 Documentation

Les nouveaux utilisateurs doivent commencer par la [documentation sur l’architecture](wiki/Architecture.md).

La documentation principale est disponible dans le [Wiki GitHub](https://github.com/TristanIsrael/Safecor/wiki).

Documentation API générée automatiquement :  
- [Documentation API Python sur GitHub Pages](https://tristanisrael.github.io/Safecor)  
- [Documentation du protocole sur GitHub Wiki](https://github.com/TristanIsrael/Safecor/wiki/Protocol)

## 📁 Structure des répertoires du projet

Le projet est divisé en différentes parties :

| Dossier | Description |
|--|--|
| certs | contient la clé publique pour le dépôt Alpine |
| misc | contient différents objets comme polices, logos et scripts |
| python | contient le code source du projet [Voir README.md](python/README.md) |
| setup | contient le code source des paquets Alpine [Voir README.md](setup/README.md) |

## 📜 Licence

Veuillez lire attentivement la [licence](python/lib/LICENCE.md) avant d’utiliser ce produit. 

## 🚀 Releases

*Veuillez noter que seuls les paquets x86_64 sont disponibles actuellement.*

Les releases sont disponibles dans le [dépôt officiel](https://alefbet.net/github/safecor).

Ajoutez la ligne suivante dans `/etc/apk/repositories` :
```
https://alefbet.net/github/safecor
```

Le fichier de [la clé publique](https://alefbet.net/github/safecor/safecor.rsa.pub) doit être téléchargé dans le répertoire `/etc/apk/keys`.

## 🖥️ Compatibilité

| Alpine | Status |
|--|--|
| v3.20 | ![Working](https://img.shields.io/badge/Working-109900) |
| v3.21 | ![Working](https://img.shields.io/badge/Working-109900) |
| v3.22 | ![Not tested](https://img.shields.io/badge/Not%20tested-ffa500) |
| v3.23 | ![Not tested](https://img.shields.io/badge/Not%20tested-ffa500) |

## 🏁 Première utilisation

Lors de la première utilisation de Safecor, nous vous suggérons de commencer par l’[application de démonstration](python/demo/README.md) ou l’[application de diagnostic](python/diag/README.md).

Suivez les instructions de la documentation [provisioning](python/lib/docs/source/markdown/provisioning.md).

**Veuillez noter que votre matériel doit être compatible avec VT-d et VT-x. Cela peut être vérifié avec l’[application de diagnostic](python/diag/README.md).**
