import threading
import os
import pandas as pd
from flask import Flask, request, send_file, jsonify
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from dread_scraper import main as dread_scrape_main  # Import dread scraper
from cryptbb_scraper import main as cryptbb_scrape_main  # Import cryptbb scraper

app = Flask(__name__)

# MongoDB setup
client = MongoClient("mongodb://localhost:27017/")
db = client["scraped_data"]
dread_collection = db["posts"]
cryptbb_collection = db["cryptbb_posts"]

# Global scraping state
scraping_thread = None
is_scraping = False
scraping_forum = None
stop_event = threading.Event()

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    global is_scraping, scraping_thread, scraping_forum, stop_event
    
    # Check if scraping is already in progress
    if is_scraping:
        return jsonify({"status": "error", "message": "Scraping is already in progress"}), 400
    
    # Get forum name from request
    forum = request.json.get('forum', '').lower()
    
    # Validate forum name
    if forum not in ['dread', 'cryptbb']:
        return jsonify({"status": "error", "message": "Invalid forum. Choose 'dread' or 'cryptbb'"}), 400
    
    # Reset the database for new scraping session
    if forum == 'dread':
        dread_collection.delete_many({})
    else:
        cryptbb_collection.delete_many({})
    
    stop_event.clear() 

    # Start scraping in a separate thread
    def run_scraper():
        global is_scraping, scraping_forum
        try:
            is_scraping = True
            scraping_forum = forum
            
            # Select the appropriate scraping function based on forum
            if forum == 'dread':
                dread_scrape_main(stop_event)
            else:  # cryptbb
                cryptbb_scrape_main()
        except Exception as e:
            print(f"Scraping error for {forum}: {e}")
        finally:
            is_scraping = False
            scraping_forum = None
    
    scraping_thread = threading.Thread(target=run_scraper)
    scraping_thread.start()
    
    return jsonify({"status": "success", "message": f"Scraping {forum} started"}), 200

@app.route('/stop_scraping', methods=['GET'])
def stop_scraping():
    global is_scraping, stop_event, scraping_forum

    if not is_scraping:
        return jsonify({"status": "error", "message": "No scraping in progress"}), 400

    stop_event.set()  # Signal scraper to stop

    if scraping_thread and scraping_thread.is_alive():
        scraping_thread.join(timeout=40)  # Wait for thread to stop

    if scraping_forum == 'dread':
        df = pd.DataFrame(list(dread_collection.find()))
    else:  # cryptbb
        df = pd.DataFrame(list(cryptbb_collection.find()))

    if '_id' in df.columns:
        df = df.drop('_id', axis=1)

    csv_filename = f'{scraping_forum}_scraped_data.csv'
    df.to_csv(csv_filename, index=False)

    return send_file(csv_filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)