import requests
import re

def detect_server_leaks(target_url):
    """
    Detects server information leaks via exposed mod_status or similar interfaces.

    Args:
        target_url (str): The darkweb URL to query (must end with .onion).
    
    Returns:
        dict: A dictionary containing the detection results or an error message.
    """
    if not target_url.endswith(".onion"):
        return {"status": "error", "message": "Target URL must be a valid .onion address."}

    mod_status_endpoint = f"{target_url}/server-status"
    results = {"endpoint": mod_status_endpoint, "status_code": None, "leak_detected": False, "details": {}}

    try:
        response = requests.get(mod_status_endpoint, timeout=20)
        results["status_code"] = response.status_code

        if response.status_code == 200 and "Apache" in response.text:
            results["leak_detected"] = True
            server_version = re.search(r"ServerVersion:\s(.+)", response.text)
            ip_addresses = re.findall(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", response.text)

            if server_version:
                results["details"]["server_version"] = server_version.group(1)
            if ip_addresses:
                results["details"]["exposed_ips"] = ip_addresses
            results["details"]["raw_response"] = response.text
        else:
            results["message"] = "No server information leaked at this endpoint."

    except requests.exceptions.RequestException as e:
        results["status"] = "error"
        results["message"] = str(e)

    return results

if __name__ == "__main__":
    # User input
    target_url = "http://p53lf57qovyuvwsc6xnrppyply3vtqm7l6pcobkmyqsiofyeznfu5uqd.onion"
    log_file = f"server_info_leak_log_{int(time.time())}.txt"  # Unique log file name
    
    # Start detection
    detect_server_leaks(target_url, log_file)
    print(f"[INFO] Logs saved to {log_file}")