# backend.py
import pandas as pd

def traitement_backend(liv_file, clients_file, volumes_file):
    # --- 1. Charger les fichiers ---
    df_liv = pd.read_excel(liv_file)
    df_clients = pd.read_excel(clients_file)
    df_vol = pd.read_excel(volumes_file)

    # --- 2. Nettoyage des colonnes numériques ---
    # Poids
    if "Poids de l'US" in df_liv.columns:
        df_liv["Poids de l'US"] = pd.to_numeric(
            df_liv["Poids de l'US"].astype(str).str.replace(",", "."), errors="coerce"
        ).fillna(0)
    else:
        df_liv["Poids de l'US"] = 0

    # Quantité livrée US
    if "Quantité livrée US" not in df_liv.columns:
        df_liv["Quantité livrée US"] = 1  # par défaut si colonne inexistante
    df_liv["Quantité livrée US"] = pd.to_numeric(df_liv["Quantité livrée US"], errors="coerce").fillna(0)

    # Volume
    if "Volume de l'US" in df_vol.columns:
        df_vol["Volume de l'US"] = pd.to_numeric(
            df_vol["Volume de l'US"].astype(str).str.replace(",", "."), errors="coerce"
        ).fillna(0)
    else:
        df_vol["Volume de l'US"] = 0

    # --- 3. Calculer poids total par ligne ---
    df_liv["Poids total ligne"] = df_liv["Quantité livrée US"] * df_liv["Poids de l'US"]

    # --- 4. Fusion avec volumes ---
    df_merge = pd.merge(
        df_liv,
        df_vol[["Article", "Volume de l'US"]],
        on="Article",
        how="left"
    )

    # --- 5. Fusion avec clients ---
    df_merge = pd.merge(
        df_merge,
        df_clients[["Client", "Raison sociale"]],
        left_on="Client commande",
        right_on="Client",
        how="left"
    )

    # --- 6. Calcul final : nombre de livraisons et volumes totaux ---
    df_result = df_merge.groupby(["Client", "Raison sociale"], as_index=False).agg({
        "No livraison": "count",
        "Poids total ligne": "sum",
        "Volume de l'US": "sum"
    })

    df_result.rename(
        columns={
            "No livraison": "Nb livraisons",
            "Poids total ligne": "Poids total",
            "Volume de l'US": "Volume total"
        },
        inplace=True
    )

    # --- 7. Calcul taux d'occupation ---
    MAX_POIDS = 1550.0  # kg
    MAX_VOLUME = 4.608  # m3
    df_result["Taux d'occupation (%)"] = df_result.apply(
        lambda row: max(row["Poids total"]/MAX_POIDS, row["Volume total"]/MAX_VOLUME)*100,
        axis=1
    ).round(2)

    return df_result
