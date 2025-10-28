import pandas as pd

class DeliveryProcessor:

    @staticmethod
    def load_data(file):
        try:
            if file.name.endswith(".csv"):
                df = pd.read_csv(file, dtype=str)
            else:
                df = pd.read_excel(file, dtype=str)
            return df
        except Exception as e:
            raise Exception(f"Erreur import fichier : {e}")

    @staticmethod
    def clean_data(df):
        # Convertir toutes les colonnes en string pour éviter l'erreur .str
        df = df.astype(str)

        # Uniformisation noms de villes
        if "Ville" in df.columns:
            df["Ville"] = df["Ville"].str.strip().str.upper()
        else:
            raise Exception("❌ Colonne 'Ville' manquante dans le fichier Livraisons")

        # Gestion du volume
        if "Volume (m3)" in df.columns:
            df["Volume (m3)"] = pd.to_numeric(df["Volume (m3)"], errors="coerce").fillna(0)
        else:
            raise Exception("❌ Colonne 'Volume (m3)' manquante")

        return df

    @staticmethod
    def compute_metrics(df):
        try:
            livraisons_par_ville = df.groupby("Ville").size().reset_index(name="Nb Livraisons")
            volume_par_ville = df.groupby("Ville")["Volume (m3)"].sum().reset_index(name="Volume Total")
            return livraisons_par_ville, volume_par_ville
        except Exception as e:
            raise Exception(f"Erreur lors du calcul des KPI : {e}")
