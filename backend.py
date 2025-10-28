import pandas as pd

class DeliveryProcessor:
    def __init__(self, df_livraisons):
        self.df = df_livraisons.copy()
        self.clean_data()

    def clean_data(self):
        # Vérification de la colonne Ville
        if "ADR_LIV_VILLE" in self.df.columns:
            self.df["ADR_LIV_VILLE"] = (
                self.df["ADR_LIV_VILLE"]
                .astype(str)
                .str.strip()
                .str.upper()
            )

        # Convertir volume si existe
        if "Volume_de_l_US" in self.df.columns:
            self.df["Volume_de_l_US"] = (
                pd.to_numeric(
                    self.df["Volume_de_l_US"],
                    errors="coerce"
                ).fillna(0)
            )

    def count_by_day(self):
        if "Date" in self.df.columns:
            self.df["Date"] = pd.to_datetime(self.df["Date"], errors="coerce")
            return (
                self.df.groupby(self.df["Date"].dt.date)["N° BL"]
                .count()
                .reset_index(name="Nb Livraisons")
            )
        return pd.DataFrame(columns=["Date", "Nb Livraisons"])

    def volume_by_day(self):
        if "Date" in self.df.columns and "Volume_de_l_US" in self.df.columns:
            self.df["Date"] = pd.to_datetime(self.df["Date"], errors="coerce")
            return (
                self.df.groupby(self.df["Date"].dt.date)["Volume_de_l_US"]
                .sum()
                .reset_index(name="Volume Total (m3)")
            )
        return pd.DataFrame(columns=["Date", "Volume Total (m3)"])

    def count_by_city(self):
        if "ADR_LIV_VILLE" in self.df.columns:
            return (
                self.df.groupby("ADR_LIV_VILLE")["N° BL"]
                .count()
                .reset_index(name="Nb Livraisons")
            )
        return pd.DataFrame(columns=["ADR_LIV_VILLE", "Nb Livraisons"])

    def volume_by_city(self):
        if "ADR_LIV_VILLE" in self.df.columns and "Volume_de_l_US" in self.df.columns:
            return (
                self.df.groupby("ADR_LIV_VILLE")["Volume_de_l_US"]
                .sum()
                .reset_index(name="Volume Total (m3)")
            )
        return pd.DataFrame(columns=["ADR_LIV_VILLE", "Volume Total (m3)"])
