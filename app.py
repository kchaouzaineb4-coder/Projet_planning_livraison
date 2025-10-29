# --- app.py ---
# Importation du framework Flask.
# Si Flask n'est pas installé, vous devez l'installer : pip install Flask
from flask import Flask, render_template_string

# Initialisation de l'application Flask
app = Flask(__name__)

# Définition du contenu HTML pour l'interface de la page.
# Note : Pour une application plus grande, le HTML devrait être dans un fichier
# séparé (template) et non dans une chaîne de caractères.
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interface Web Simple</title>
    <!-- Styles CSS pour rendre l'interface un peu plus agréable -->
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f0f4f8;
            color: #2c3e50;
            text-align: center;
            padding: 50px 20px;
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            background-color: #ffffff;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            max-width: 600px;
            width: 100%;
            border-top: 5px solid #3498db;
        }
        h1 {
            color: #3498db;
            font-size: 2.2em;
            margin-bottom: 20px;
        }
        p {
            font-size: 1.1em;
            line-height: 1.6;
        }
        .action-button {
            display: inline-block;
            margin-top: 25px;
            padding: 10px 20px;
            background-color: #2ecc71;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            transition: background-color 0.3s ease;
        }
        .action-button:hover {
            background-color: #27ae60;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bienvenue ! Ceci est votre interface Web</h1>
        <p>
            Ce contenu est servi par le fichier Python (app.py) utilisant Flask. 
            C'est le point de départ pour afficher tous vos éléments d'interface.
        </p>
        <p>Modifiez le contenu de la variable `HTML_CONTENT` pour construire votre application.</p>
        <a href="#" class="action-button">Démarrer l'Application</a>
    </div>
</body>
</html>
"""

# Définition de la route par défaut ('/')
@app.route('/')
def index():
    # Retourne la chaîne HTML pour l'afficher dans le navigateur
    return render_template_string(HTML_CONTENT)

# Exécuter l'application
if __name__ == '__main__':
    # Lance le serveur local de développement.
    # L'application sera accessible à l'adresse http://127.0.0.1:5000/
    # (ou l'équivalent local)
    app.run(debug=True)