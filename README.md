# 🎯 CréaCV — Système de génération de CV professionnel

Application web Flask complète pour générer, prévisualiser et vendre des CV professionnels.

---

## 📦 Structure du projet

```
cv_saas/
├── app.py                    # Application Flask principale
├── database.db               # Base SQLite (auto-créée au démarrage)
├── requirements.txt
├── templates/
│   ├── index.html            # Formulaire client
│   ├── success.html          # Page après soumission
│   ├── cv_simple.html        # Template CV Simple
│   ├── cv_professionnel.html # Template CV Professionnel
│   ├── cv_premium.html       # Template CV Premium (or/noir)
│   ├── admin_login.html      # Login admin
│   ├── admin.html            # Dashboard admin
│   └── payment_required.html # Page paiement requis
├── static/
│   └── uploads/              # Photos uploadées
├── pdf/                      # PDFs générés
└── preview/                  # (réservé)
```

---

## 🚀 Installation

### 1. Prérequis système

**Linux/Mac :**
```bash
# Weasyprint nécessite des dépendances système
# Ubuntu/Debian :
sudo apt-get install -y python3-pip libpango-1.0-0 libpangoft2-1.0-0 libcairo2

# Mac (Homebrew) :
brew install pango cairo
```

**Windows :**
- Installez [GTK for Windows](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases)

### 2. Installer Python et les dépendances

```bash
# Créer un environnement virtuel (recommandé)
python3 -m venv venv
source venv/bin/activate      # Mac/Linux
# OU
venv\Scripts\activate          # Windows

# Installer les dépendances
pip install -r requirements.txt
```

### 3. Lancer l'application

```bash
python app.py
```

L'application sera disponible sur : **http://localhost:5000**

---

## 🔐 Accès Admin

- URL : `http://localhost:5000/admin`
- Mot de passe par défaut : `admin123`

> ⚠️ **IMPORTANT** : Changez le mot de passe dans `app.py` ligne 15 :
> ```python
> ADMIN_PASSWORD = "votre_mot_de_passe_securise"
> ```

---

## 🌐 Routes disponibles

| Route | Description |
|-------|-------------|
| `/` | Formulaire client |
| `/preview/<id>` | Aperçu du CV |
| `/download/<id>` | Téléchargement PDF (si payé) |
| `/success/<id>` | Page confirmation |
| `/admin` | Panel administration |
| `/admin/logout` | Déconnexion |

### API Admin (POST, cookie requis)
| Route | Action |
|-------|--------|
| `/admin/validate/<id>` | Valider le paiement |
| `/admin/unvalidate/<id>` | Annuler la validation |
| `/admin/delete/<id>` | Supprimer un client |
| `/admin/stats` | Statistiques (GET) |

---

## 🧪 Test local — Flux complet

1. Ouvrez `http://localhost:5000`
2. Remplissez le formulaire → Soumettez
3. Vous êtes redirigé vers la page succès avec lien preview
4. Cliquez sur "Voir l'aperçu" → Le CV s'affiche
5. Cliquez sur "Télécharger PDF" → Bloqué (paiement requis)
6. Allez sur `http://localhost:5000/admin` (mdp: `admin123`)
7. Trouvez le client → Cliquez "✓ Valider"
8. Retournez sur `/download/<id>` → Le PDF se télécharge !

---

## ⚙️ Configuration

Modifiez dans `app.py` :

```python
ADMIN_PASSWORD = "admin123"   # Mot de passe admin
```

Pour la production, ajoutez aussi :
```python
app.secret_key = "votre_clé_secrète_unique"
```

---

## 🌍 Déploiement en production

### Option 1 : VPS simple avec Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Option 2 : Avec Nginx (recommandé)

```nginx
server {
    listen 80;
    server_name votre-domaine.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /static {
        alias /chemin/vers/cv_saas/static;
    }
}
```

### Option 3 : Railway / Render

Ajoutez un fichier `Procfile` :
```
web: gunicorn app:app
```

---

## 💡 Personnalisation

### Changer le numéro WhatsApp
Dans `success.html` et `payment_required.html`, remplacez :
```
https://wa.me/?text=...
```
par :
```
https://wa.me/33600000000?text=...
```

### Ajouter un tarif
Dans `index.html`, modifiez les `.template-badge` pour afficher les prix.

### Modifier les templates CV
Éditez `templates/cv_simple.html`, `cv_professionnel.html`, `cv_premium.html`.

---

## 📊 Base de données

Table `cv_clients` :
```sql
id TEXT          -- Identifiant unique (ex: abc123de45)
nom TEXT
email TEXT
telephone TEXT
ville TEXT
pays TEXT
poste TEXT
objectif TEXT
formation TEXT   -- Texte brut, séparé par \n
experience TEXT
competences TEXT
langues TEXT
template TEXT    -- simple / professionnel / premium
photo_path TEXT  -- Chemin relatif vers la photo
paid INTEGER     -- 0 = non payé, 1 = payé
created_at TEXT  -- YYYY-MM-DD HH:MM:SS
notes_admin TEXT -- Notes internes
```

---

## 🐛 Problèmes courants

**WeasyPrint ne génère pas le PDF :**
```bash
# Vérifiez les dépendances système
python3 -c "import weasyprint; print('OK')"
```

**Photos non affichées dans le PDF :**
- Vérifiez que les chemins sont absolus dans la génération PDF
- Le `base_url` dans `generate_pdf()` doit pointer vers le dossier du projet

**Port 5000 occupé :**
```bash
python app.py  # Modifiez le port dans la dernière ligne si besoin
# app.run(debug=True, port=5001)
```
