import sys
import os

# Ajouter le dossier racine au path pour importer app.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app

# Vercel cherche cette variable "app"
