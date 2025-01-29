import requests
import os
import logging
import time
from urllib.parse import urljoin                    
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

class WebDirectoryScanner:
    def __init__(self, base_url, wordlist_path=None, threads=10, verbose=True):
        self.base_url = base_url.rstrip('/')
        self.threads = threads
        self.verbose = verbose

        # Set up logging
        logging.basicConfig(
            level=logging.INFO if verbose else logging.ERROR,
            format='%(asctime)s - %(levelname)s: %(message)s',
            handlers=[
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # Default wordlist if not provided
        if wordlist_path is None:
            # wordlist_path = '/usr/share/dirb/wordlists/common.txt'
            wordlist_path = '/home/kali/Desktop/DarkwebMonitor/Features/test.txt'

        
        if not os.path.exists(wordlist_path):
            self.logger.error(f"Wordlist not found: {wordlist_path}")
            raise FileNotFoundError(f"Wordlist file not found: {wordlist_path}")
        
        with open(wordlist_path, 'r') as f:
            self.wordlist = [line.strip() for line in f if line.strip()]
        
        self.logger.info(f"Loaded {len(self.wordlist)} entries from wordlist")

    def scan_url(self, path):
        full_url = urljoin(self.base_url, path)
        try:
            response = requests.head(full_url, allow_redirects=True, timeout=20)
            if response.status_code in [200, 204, 301, 302, 307]:
                result = {
                    'url': full_url,
                    'status': response.status_code,
                    'exists': True
                }
                self.logger.info(f"Found: {full_url} (Status: {response.status_code})")
                return result
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Error scanning {full_url}: {e}")
        return None

    def run_scan(self, output_file):
        self.logger.info(f"Starting scan on {self.base_url}")
        start_time = time.time()
        discovered_paths = []

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {executor.submit(self.scan_url, path): path for path in self.wordlist}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    discovered_paths.append(result)

        end_time = time.time()
        self.logger.info(f"Scan complete. Found {len(discovered_paths)} paths in {end_time - start_time:.2f} seconds")

        # Save results to a JSON file
        with open(output_file, 'w') as f:
            json.dump(discovered_paths, f, indent=4)

        return output_file

def main():
    target_url = ""  
    scanner = WebDirectoryScanner(
        base_url=target_url, 
        verbose=True,
        threads=15
    )
    results = scanner.run_scan()
    
    # Optional: Print detailed results
    for path in results:
        print(f"Path: {path['url']} (Status: {path['status']})")

if __name__ == "__main__":
    main()