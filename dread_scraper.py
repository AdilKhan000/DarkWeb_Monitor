import random
import time
import requests
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from pymongo import MongoClient
from bs4 import BeautifulSoup
from termcolor import colored
import urllib.parse
import re
from classifier import classify_content
from scraper_utils import clean_text, extract_cookies, setup_requests_session, configure_webdriver


# Proxy and MongoDB setup
proxy_host = "127.0.0.1"
proxy_port = 8118
client = MongoClient("mongodb://localhost:27017/")
db = client["scraped_data"]
dread_collection = db["posts"]

# Target URL (you might want to make this dynamic or configurable)
start_url = "http://dreadytofatroptsdj6io7l3xptbet6onoyno2yv7jicoxknyazubrad.onion"

# Scrape post content
def scrape_post_content(session, post_url, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            response = session.get(post_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                content = soup.find('div', class_='postContent').get_text(separator="\n")
                return clean_text(content)
            else:
                print(colored(f"Warning: Failed to retrieve content from {post_url}", "yellow"))
        except requests.exceptions.RequestException as e:
            attempt += 1
            print(colored(f"Connection error on {post_url}, retry {attempt}/{retries}: {e}", "red"))
            time.sleep(5)  # Wait before retrying
    return ""

# Scrape a page and retrieve post data
def scrape_page(session, url, scraped_posts, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            response = session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                posts = [
                    post for post in soup.find_all('div', class_='item')
                    if post.find('a', class_='title') and post.find('div', class_='voteCount')
                ]

                for post in posts:
                    try:
                        title = post.find('a', class_='title').get_text(strip=True)
                        post_link = post.find('a', class_='title')['href']
                        full_post_link = urllib.parse.urljoin(url, post_link)

                        # Skip post if already processed
                        if full_post_link in scraped_posts:
                            print(colored(f"Skipping duplicate post: {title}", "yellow"))
                            continue

                        upvotes = int(post.find('div', class_='voteCount').get_text(strip=True))

                        # Process the author name and area, removing /u/
                        author_tag = post.find('div', class_='author').find('a')
                        author = author_tag.get_text(strip=True).replace('/u/', '')
                        area = post.find('div', class_='author').find_all('a')[1].get_text(strip=True)

                        print(colored(f"Scraping post: {title} | URL: {full_post_link}", "cyan"))
                        
                        # Scrape post content and clean it
                        post_content = scrape_post_content(session, full_post_link)
                        classification = classify_content(post_content)
                        print("Model Response: ", classification)
                        # Document to insert into MongoDB
                        post_document = {
                            "Title": title,
                            "Author": author,
                            "Area": area,
                            "Upvotes": upvotes,
                            "Content": post_content,
                            "Classification": classification,
                            "URL": full_post_link
                        }

                        if dread_collection.count_documents({"URL": full_post_link}, limit=1) == 0:
                            dread_collection.insert_one(post_document)
                            print(colored(f"Post saved: {title}", "green"))
                        else:
                            print(colored(f"Post already exists in database: {title}", "yellow"))
                        
                        scraped_posts[full_post_link] = True

                    except Exception as e:
                        print(colored(f"Error parsing post: {e}", "red"))

                pagination_links = soup.select('div.pagination a')
                next_pages = [urllib.parse.urljoin(url, link['href']) for link in pagination_links if link.get('href')]
                print(colored(f"Found pagination links: {next_pages}", "blue"))

                return next_pages
            else:
                print(colored(f"Failed to scrape {url}, status code: {response.status_code}", "red"))
        except requests.exceptions.RequestException as e:
            attempt += 1
            print(colored(f"Connection error on {url}, retry {attempt}/{retries}: {e}", "red"))
            time.sleep(5)
    return []


def main(stop_event=None):
    try:
        options = Options()
        options.set_preference("network.proxy.type", 1)
        options.set_preference("network.proxy.http", proxy_host)
        options.set_preference("network.proxy.http_port", proxy_port)
        options.set_preference("network.proxy.ssl", proxy_host)
        options.set_preference("network.proxy.ssl_port", proxy_port)
        options.set_preference("network.proxy.socks", proxy_host)
        options.set_preference("network.proxy.socks_port", proxy_port)
        options.set_preference("network.proxy.socks_version", 5)
        options.set_preference("network.proxy.no_proxies_on", "")
        driver = webdriver.Firefox(options=options)

        print(colored(f"Opening URL: {start_url}", "blue"))
        driver.get(start_url)
        print(colored("Waiting 30 seconds to ensure the session is established...", "yellow"))
        time.sleep(30)

        cookies = extract_cookies(driver)
        session = setup_requests_session(cookies)

        to_scrape = [start_url]
        scraped = set()
        scraped_posts = {}

        while to_scrape:
            if stop_event and stop_event.is_set():  # Check for stop signal
                print(colored("Stop signal received. Exiting scraping loop...", "yellow"))
                break

            url = to_scrape.pop(0)
            if url not in scraped:
                print(colored(f"Scraping page: {url}", "magenta"))
                new_links = scrape_page(session, url, scraped_posts)

                to_scrape.extend(link for link in new_links if link not in scraped and link not in to_scrape)
                scraped.add(url)

                time.sleep(random.uniform(5, 15))

    except Exception as e:
        print(colored(f"Error in main scraping function: {e}", "red"))

if __name__ == "__main__":
    main()