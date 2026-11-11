import os
import socket
import sys
import threading
import time

import serial

# arguments attendus :
#   [emission, réception]
#   type : [série, socket]
#   chemin du fichier
#   taille trame
cote = ""
if len(sys.argv) < 5:
    print("Arguments manquants : {} action type chemin".format(sys.argv[0]))
    print("   action : émission ou réception")
    print("   type : série ou socket")
    print("   chemin du port série ou de la socket")
    print("   taille de la trame (en octets)")
    exit(1)

action = sys.argv[1]
type = sys.argv[2]
chemin = sys.argv[3]
taille = int(sys.argv[4])

if not os.path.exists(chemin):
    print("ERREUR : le fichier {} n'existe pas ou n'est pas accessible".format(chemin))
    exit(2)

if action != "émission" and action != "réception" and action != "test":
    print("Erreur : action inconnue")
    exit(3)

if type != "série" and type != "socket":
    print("Erreur : type inconnu")
    exit(4)

compte = 0
taille_totale = 0
perfo = 0.0  # En trames par seconde
duree = 0.0  # En nanosecondes
delai = 1.0
ref_temps = time.time_ns()

trame = b""
for i in range(taille):
    trame += b"X"


def mesure_perfo():
    global compte, delai, perfo, duree
    duree += delai
    perfo = compte / duree  # Perfo en trames / seconde
    debit = taille_totale / duree  # Débit en octets / seconde
    print(
        "Perfo : {} trames par seconde. débit : {} octets par seconde. {} trames. {} secondes".format(
            perfo, debit, compte, duree
        )
    )
    threading.Timer(delai, mesure_perfo).start()


threading.Timer(delai, mesure_perfo).start()

if action == "test":
    while True:
        pass

if type == "série":
    fd = serial.Serial(chemin)
    if action == "émission":
        while True:
            fd.write(trame)
            compte += 1
            taille_totale += taille
    elif action == "réception":
        while True:
            recv = fd.read(taille)
            if len(recv) > 0:
                taille_totale += len(recv)
                compte += 1
            # print("len={}".format(len(recv)))
elif type == "socket":
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(chemin)
    if action == "émission":
        while True:
            sock.send(trame)
            compte += 1
            taille_totale += taille
    elif action == "réception":
        while True:
            recv = sock.recv(taille)
            if len(recv) > 0:
                taille_totale += len(recv)
                compte += 1
