# --- app.py ---
# Importation du framework Flask.
# Si Flask n'est pas installé, vous devez l'installer : pip install Flask
from flask import Flask, render_template_string

# Initialisation de l'application Flask
app = Flask(__name__)

# Définition du contenu HTML pour l'interface de la page de location de camions.
# Le style est intégré pour maintenir l'application dans un seul fichier Python.
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Location de Camions</title>
    <!-- Styles CSS pour une interface moderne et responsive -->
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f0f4f8;
            color: #2c3e50;
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background-color: #ffffff;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.15);
            max-width: 600px;
            width: 100%;
            border-top: 6px solid #e74c3c; /* Rouge pour un look dynamique/logistic */
        }
        h1 {
            color: #e74c3c;
            font-size: 2em;
            margin-bottom: 10px;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 15px;
        }
        p.subtitle {
            font-size: 1em;
            color: #7f8c8d;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #34495e;
        }
        input[type="text"], 
        input[type="number"],
        input[type="date"],
        select {
            width: 100%;
            padding: 12px;
            border: 1px solid #bdc3c7;
            border-radius: 8px;
            box-sizing: border-box;
            transition: border-color 0.3s;
        }
        input[type="text"]:focus, 
        input[type="number"]:focus,
        input[type="date"]:focus,
        select:focus {
            border-color: #e74c3c;
            outline: none;
            box-shadow: 0 0 5px rgba(231, 76, 60, 0.3);
        }
        .submit-button {
            width: 100%;
            padding: 15px;
            background-color: #e74c3c;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1.1em;
            font-weight: bold;
            cursor: pointer;
            transition: background-color 0.3s ease, transform 0.1s ease;
        }
        .submit-button:hover {
            background-color: #c0392b;
        }
        .submit-button:active {
            transform: scale(0.98);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Formulaire de Location de Camions</h1>
        <p class="subtitle">Sélectionnez le type de véhicule et la durée de la location.</p>
        
        <form action="#" method="POST">
            
            <div class="form-group">
                <label for="truckType">Type de Camion :</label>
                <select id="truckType" name="truckType" required>
                    <option value="" disabled selected>Choisir un type...</option>
                    <option value="petit">Petit (2 tonnes)</option>
                    <option value="moyen">Moyen (5 tonnes)</option>
                    <option value="grand">Grand (10+ tonnes)</option>
                    <option value="remorque">Semi-remorque</option>
                </select>
            </div>

            <div class="form-group">
                <label for="startDate">Date de Début de Location :</label>
                <input type="date" id="startDate" name="startDate" required>
            </div>
            
            <div class="form-group">
                <label for="duration">Durée de Location (jours) :</label>
                <input type="number" id="duration" name="duration" min="1" value="1" required>
            </div>

            <button type="submit" class="submit-button">Soumettre la Demande</button>
        </form>
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