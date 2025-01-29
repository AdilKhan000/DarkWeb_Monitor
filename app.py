import threading
import os
import uuid
import pandas as pd
import queue
import threading
from flask import Flask, request, send_file, jsonify, Response
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from dread_scraper import main as dread_scrape_main
from scraper_utils import log_queue
from cryptbb_scraper import main as cryptbb_scrape_main  # Import cryptbb scraper
from flask_cors import CORS 
import traceback
import time
from Features.nmap import run_nmap
from Features.Directory_Scanner import WebDirectoryScanner
from Features.detect_server_leaks import detect_server_leaks


app = Flask(__name__)
CORS(app)

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


log_buffer = []
log_lock = threading.Lock()
# In-memory storage for task statuses of Nmap scans
tasks = {}

def perform_directory_scan(base_url, threads, task_id):
    """
    Perform directory scanning and update task status.
    """
    try:
        output_file = f"directory_scan_report/{task_id}_dir_scan_report.json"
        scanner = WebDirectoryScanner(base_url=base_url, threads=threads, verbose=True)
        scanner.run_scan(output_file)
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["report_file"] = output_file
        tasks[task_id]["message"] = "Directory scan completed successfully."
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["message"] = str(e)

def perform_scan(target, task_id):
    """
    Perform Nmap scan and update task status.
    """
    try:
        report_file = f"{task_id}_nmap_report.txt"
        result_message = run_nmap(target, report_file)
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["report_file"] = report_file
        tasks[task_id]["message"] = result_message
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["message"] = str(e)

@app.route('/stream_logs', methods=['GET'])
def stream_logs():
    def generate():
        while True:
            try:
                message = log_queue.get(timeout=1)  # Wait for logs from the queue
                yield f"data: {message}\n\n"  # Send the log as an SSE event
            except queue.Empty:
                continue  # No logs, keep the connection alive
            except GeneratorExit:
                print("Client disconnected from log stream.")
                break  # Exit the generator when the client disconnects

    return Response(generate(), content_type='text/event-stream')

def capture_logs():
    global log_buffer
    while True:
        try:
            message = log_queue.get(timeout=1)  # Wait for 1 second
            with log_lock:
                log_buffer.append(message)
        except queue.Empty:
            continue
        except Exception:
            break

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    global is_scraping, scraping_thread, scraping_forum, stop_event, log_buffer
    

    with log_lock:
        log_buffer.clear()
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
                cryptbb_scrape_main(stop_event)
        except Exception as e:
            print(f"Scraping error for {forum}: {e}")
        finally:
            is_scraping = False
            scraping_forum = None
    
    scraping_thread = threading.Thread(target=run_scraper)
    scraping_thread.start()

    # Start log capture thread
    log_capture_thread = threading.Thread(target=capture_logs, daemon=True)
    log_capture_thread.start()
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

@app.route('/nmap_scan', methods=['POST'])
def nmap_scan():
    """
    Start an Nmap scan asynchronously.
    """
    data = request.get_json()
    target = data.get('target')

    if not target:
        return jsonify({"status": "error", "message": "Target URL is required"}), 400

    # Generate a unique task ID
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "in_progress", "message": "Scan started"}

    # Start the scan in a separate thread
    threading.Thread(target=perform_scan, args=(target, task_id), daemon=True).start()

    return jsonify({"status": "success", "task_id": task_id}), 202

@app.route('/nmap_status/<task_id>', methods=['GET'])
def nmap_status(task_id):
    """
    Get the status of an Nmap scan.
    """
    task = tasks.get(task_id)

    if not task:
        return jsonify({"status": "error", "message": "Task ID not found"}), 404

    if task["status"] == "completed":
        return jsonify({
            "status": "success",
            "message": task["message"],
            "download_url": f"/nmap_report/{task_id}"
        })
    elif task["status"] == "failed":
        return jsonify({"status": "error", "message": task["message"]})

    return jsonify({"status": "in_progress", "message": task["message"]})

@app.route('/nmap_report/<task_id>', methods=['GET'])
def nmap_report(task_id):
    """
    Download the Nmap report.
    """
    task = tasks.get(task_id)

    if not task or task["status"] != "completed":
        return jsonify({"status": "error", "message": "Report not available"}), 404

    report_file = task.get("report_file")
    if not report_file or not os.path.exists(report_file):
        return jsonify({"status": "error", "message": "Report file not found"}), 404

    return send_file(report_file, as_attachment=True)


@app.route('/directory_scan', methods=['POST'])
def directory_scan():
    """
    Start a directory scan asynchronously.
    """
    data = request.get_json()
    target_url = data.get('target_url')
    threads = int(data.get('threads', 10))

    if not target_url:
        return jsonify({"status": "error", "message": "Target URL is required"}), 400

    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "in_progress", "message": "Scan started"}

    threading.Thread(
        target=perform_directory_scan,
        args=(target_url, threads, task_id),
        daemon=True
    ).start()

    return jsonify({"status": "success", "task_id": task_id}), 202

@app.route('/directory_status/<task_id>', methods=['GET'])
def directory_status(task_id):
    """
    Get the status of a directory scan.
    """
    task = tasks.get(task_id)

    if not task:
        return jsonify({"status": "error", "message": "Task ID not found"}), 404

    if task["status"] == "completed":
        return jsonify({
            "status": "success",
            "message": task["message"],
            "download_url": f"/directory_report/{task_id}"
        })
    elif task["status"] == "failed":
        return jsonify({"status": "error", "message": task["message"]})

    return jsonify({"status": "in_progress", "message": task["message"]})

@app.route('/directory_report/<task_id>', methods=['GET'])
def directory_report(task_id):
    """
    Download the directory scan report.
    """
    task = tasks.get(task_id)

    if not task or task["status"] != "completed":
        return jsonify({"status": "error", "message": "Report not available"}), 404

    report_file = task.get("report_file")
    if not report_file or not os.path.exists(report_file):
        return jsonify({"status": "error", "message": "Report file not found"}), 404

    return send_file(report_file, as_attachment=True)

@app.route('/server_leak', methods=['POST'])
def server_leak():
    """
    Endpoint to detect server leaks in a single request.
    """
    data = request.get_json()
    target_url = data.get('target_url')
    if not target_url:
        return jsonify({"status": "error", "message": "Target URL is required"}), 400

    # Remove trailing slash if present
    if target_url.endswith('/'):
        target_url = target_url[:-1]
        
    # Run the detection
    results = detect_server_leaks(target_url)
    # Return results as a response
    if results.get("status") == "error":
        return jsonify(results), 400
    return jsonify({"status": "success", "results": results}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)