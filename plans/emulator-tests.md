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

---

## Suivi des corrections

Ledger des problèmes remontés, traités un par un. Statuts : **Corrigé** · **À faire** · **À clarifier** (question en attente) · **Différé**.

| # | Problème | Type | Statut | Action / plan |
|---|----------|------|--------|---------------|
| 1.1 | Thème sombre illisible · pleine largeur · marges | UI | **Corrigé** (à vérifier sur cible) | Style Material demandé (`QT_QUICK_CONTROLS_STYLE`) + color-scheme clair/sombre système (gardé, dégrade proprement). À vérifier visuellement sur le système cible (l'env de test offscreen n'a pas les APIs de thème). |
| 1.3 | Broker externe / embarqué | UI | **Corrigé** | Reformulé en `(embarqué)` / `(externe)` ; i18n EN/FR mis à jour. |
| 1.4 | Changement de config non propagé à l'état | Bug | **Corrigé** | `apply_configuration_settings` applique le bloc `settings` d'une config (`screen.rotation`/`enabled`/`default_focus`, `usb.use`) à l'environnement (miroir de `ConfigurationHelper.__merge_configuration`) ; `select_configuration` l'appelle et le panneau d'état re-synchronise via `stateChanged`. |
| 1.5 | Panneau Actions « undefined undefined » | Bug | **Corrigé** | L'`Event` (dataclass) ne s'exposait pas en QML → le signal émet désormais une ligne formatée `HH:MM:SS source: texte`. |
| 1.6 | Panneau MQTT Events « undefined undefined » | Bug | **Corrigé** | Idem 1.5. |
| 1.7 | Texte des logs non sélectionnable | UI | **Corrigé** | Les délégués des 3 listes de journaux passent de `Text` à `TextEdit { readOnly: true; selectByMouse: true }` (sélection + copie). |
| 1.8 | Disque : dialogue · bouton à droite · multi-disques | UI | **Corrigé** (dialogue différé) | Bouton `Attach` déplacé à droite (après le champ chemin) ; multi-disques confirmé (la `Repeater` liste les disques attachés, refus id/chemin dupliqué). Boîte de dialogue de répertoire **différée** : l'API `FileDialog` de `QtQuick.Dialogs` (propriété `folder`) est absente dans ce build Qt → saisir le chemin dans le champ texte. |
| 1.9 | Workflow : listes (restart / switch GUI) | UI | **Corrigé** | `ComboBox` listant les domaines métier démarrés. |
| 1.10 | Logging : disque de save log en liste | UI | **Corrigé** | `ComboBox` listant les disques attachés. |
| 1.11 | Target : ping en liste | UI | **Corrigé** | `ComboBox` listant les domaines démarrés (confirmer : le ping cible un domaine). |
| 2.1 | `--topology` obligatoire | Bug | **Corrigé** | `--topology` optionnel pour `--gui` ; topologie chargeable depuis le panneau Setup. |
| 3.1 | Changement de topologie → stop / chargement / démarrage | Comportement | **Corrigé** | `load_topology` stoppe, recharge et redémarre si l'émulateur tournait ; un bandeau d'avertissement signale que le changement à chaud peut impacter le SST (reset éventuel). |
| 3.2 | Disques avec même id et/ou même chemin | Comportement | **Corrigé** | L'attach est refusé si l'id ou le chemin est déjà utilisé (action `attach_disk_rejected` journalisée). |