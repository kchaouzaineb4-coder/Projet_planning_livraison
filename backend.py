# backend.py
import pandas as pd

def normalize_columns(df):
    # Supprimer espaces autour des noms de colonnes et remplacer apostrophes typographiques
    df.columns = df.columns.str.strip().str.replace("’", "'", regex=False)
    return df

def process_delivery_files(liv_file, clients_file, volumes_file):
    """
    Traitement principal des fichiers de livraison
    """
    # --- Charger les fichiers ---
    df_liv = pd.read_excel(liv_file)
    df_clients = pd.read_excel(clients_file)
    df_vol = pd.read_excel(volumes_file)

    # --- Normaliser les colonnes ---
    df_liv = normalize_columns(df_liv)
    df_clients = normalize_columns(df_clients)
    df_vol = normalize_columns(df_vol)

    # --- Vérifier colonnes importantes ---
    required_cols_liv = ["Client commande", "Article", "Poids de l'US"]
    required_cols_clients = ["Client", "Raison sociale"]
    required_cols_vol = ["Article", "Volume de l'US"]

    for col in required_cols_liv:
        if col not in df_liv.columns:
            raise ValueError(f"Colonne manquante dans livraisons : {col}")
    for col in required_cols_clients:
        if col not in df_clients.columns:
            raise ValueError(f"Colonne manquante dans clients : {col}")
    for col in required_cols_vol:
        if col not in df_vol.columns:
            raise ValueError(f"Colonne manquante dans volumes : {col}")

    # --- Convertir les colonnes numériques ---
    df_liv["Poids de l'US"] = pd.to_numeric(df_liv["Poids de l'US"], errors="coerce").fillna(0)
    df_liv["Quantité livrée US"] = pd.to_numeric(df_liv.get("Quantité livrée US", 1), errors="coerce").fillna(0)
    df_vol["Volume de l'US"] = pd.to_numeric(df_vol["Volume de l'US"], errors="coerce").fillna(0)

    # --- Fusion avec clients ---
    df_merge = df_liv.merge(
        df_clients[['Client', 'Raison sociale']],
        left_on='Client commande', right_on='Client', how='left'
    )

    # --- Fusion avec volumes ---
    df_merge = df_merge.merge(
        df_vol[['Article', "Volume de l'US"]],
        on='Article', how='left'
    )

    # --- Calculs ---
    df_merge["Poids total"] = df_merge["Quantité livrée US"] * df_merge["Poids de l'US"]
    df_merge["Volume total"] = df_merge["Quantité livrée US"] * df_merge["Volume de l'US"]

    df_result = df_merge.groupby(['Client commande','Raison sociale']).agg({
        'Poids total':'sum',
        "Volume total": "sum",
        'Article':'count'
    }).rename(columns={'Article':'Nb livraisons'}).reset_index()

    return df_result
