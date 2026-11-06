"""Outils communs aux tests.

Le hachage reel (600 000 iterations PBKDF2) prend environ 0,2 s par compte :
les tests le baissent a 1 000 iterations. Chaque empreinte garde son propre
nombre d'iterations, donc la verification reste exacte.
"""
from gestion_tickets.acteurs import UserRegistry

UserRegistry.PBKDF2_ITERATIONS = 1_000

MDP = "motdepasse-test"
