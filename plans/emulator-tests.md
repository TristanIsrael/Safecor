# Safecor emulator - tests de validation

Ce document décrit les problèmes rencontrés lors des tests de validation de l'émulateur Safecor.

## 1. Problèmes GUI

### 1.1 Apparence de la GUI

- Sur mon Macbook, avec le thème sombre activé, le texte de la GUI est illisible car il est écrit en noir. Il faut appliquer des thèmes standards (Material par exemple) et prendre en compte le mode d'affichage du système (clair / sombre)

- Les panneaux (`Product language`, `Logging`, etc) doivent être en plein largeur dans leur parent.

- Il faut laisser plus d'espace à gauche et à droite des panneaux pour aérer visuellement.

### 1.3 Etat du broker

La GUI doit indiquer si le broker utilisé est un broker externe ou embarqué.

### 1.4 Changement de configuration

Lorsque l'utilisateur change la configuration sélectionnée, le panneau d'état du système n'est pas mis à jour. Par exemple, l'orientation de l'écran n'est pas modifiée.

### 1.5 Panneau `Actions`

Le panneau `Actions` affiche plusieurs lignes `undefined undefined`, et aucune ligne intelligible.

### 1.6 Panneau `MQTT Events`

Le panneau `MQTT Events` affiche plusieurs lignes `undefined undefined`, et aucune ligne intelligible.

### 1.7 Sélection de texte dans les panneaux

Le contenu des panneaux de logs doit pouvoir être sélectionné pour un copier-coller.

### 1.8 Sélection du disque

- La sélection du répertoire pour un disque doit se faire avec une boite de dialogue en plus du champ de texte. 
- Le bouton `Attach` doit être placé à droite de la ligne.
- Il n'est possible d'attacher qu'un seul disque alors qu'il en faut plusieurs

### 1.9 Panneau `Workflow`

- Le champ `Restart domain` ne doit pas être un champ de texte mais une liste déroulante affichant uniquement la liste des domaines qui sont démarrés.
- Le champ `Switch GUI to` ne doit pas être un champ de texte mais une liste déroulante affichant uniquement la liste des domaines qui sont démarrés.

### 1.10 Panneau `Logging`

- Le champ `disk` de `save log` doit être une liste déroulante affichant uniquement les disques qui sont actuellement attachés.

### 1.11 Panneau `Target`

- Le champ `ping` doit être une liste déroulante affichant uniquement les disques qui sont actuellement attachés.

## 2. Problèmes au démarrage

### 2.1 Topologie obligatoire

L'argument `--topology` ne devrait pas être obligatoire pour démarrer l'application. Elle doit pouvoir démarrer sans topologie fournie et laisser l'utilisateur en charger une.

## 3. Comportements à vérifier

- Lorsque l'utilisateur change la topologie, l'émulateur soit s'arrêter, charger la topologie et démarrer
- Que se passe-t-il si l'utilisateur attache plusieurs disques avec le même identifiant et/ou le même chemin ?