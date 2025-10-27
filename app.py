from backend import DeliveryProcessor

# Dans votre route de traitement des uploads
@app.route('/process-uploads', methods=['POST'])
def process_uploads():
    try:
        # Récupérer les fichiers uploadés
        liv_file = request.files['liv_file']
        ydlogist_file = request.files['ydlogist_file']
        wcliegps_file = request.files['wcliegps_file']
        
        # Sauvegarder temporairement les fichiers
        liv_path = "temp/liv.xlsx"
        ydlogist_path = "temp/ydlogist.xlsx"
        wcliegps_path = "temp/wcliegps.xlsx"
        
        liv_file.save(liv_path)
        ydlogist_file.save(ydlogist_path)
        wcliegps_file.save(wcliegps_path)
        
        # Traiter les données
        processor = DeliveryProcessor()
        results = processor.process_delivery_data(
            liv_path,
            ydlogist_path,
            wcliegps_path
        )
        
        # Sauvegarder les résultats
        output_path = "output/Voyages_par_estafette_optimisé_avec_taux_clients_representants.xlsx"
        processor.export_results(results, output_path)
        
        return jsonify({
            "success": True,
            "message": "Traitement terminé avec succès",
            "output_file": output_path
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500