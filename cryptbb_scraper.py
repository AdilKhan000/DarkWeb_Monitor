import time
import random
import urllib.parse
from pymongo import MongoClient
from bs4 import BeautifulSoup
from termcolor import colored
from scraper_utils import clean_text, extract_cookies, setup_requests_session, configure_webdriver
from classifier import classify_content  

start_url = "http://cryptbbtg65gibadeeo2awe3j7s6evg7eklserehqr4w4e2bis5tebid.onion/"
client = MongoClient("mongodb://localhost:27017/")
db = client["scraped_data"]
collection = db["cryptbb_posts"]

def scrape_post_content(session, post_url):
    """Scrape the content of a post."""
    try:
        response = session.get(post_url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            post_body = soup.find('div', class_='post_body')
            return clean_text(post_body.get_text(separator="\n")) if post_body else ""
    except Exception as e:
        print(colored(f"Failed to scrape post content at {post_url}: {e}", "red"))
    return ""

def scrape_forum(session, forum_url, stop_event=None):
    """Scrape all posts in a specific forum."""
    to_scrape = [forum_url]
    scraped = set()

    while to_scrape:
        # Check for stop event
        if stop_event and stop_event.is_set():
            print(colored("Scraping stopped by stop event", "yellow"))
            break

        url = to_scrape.pop(0)
        if url in scraped:
            continue

        try:
            response = session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                posts = soup.select('span.subject_old a')

                for post in posts:
                    # Check for stop event before processing each post
                    if stop_event and stop_event.is_set():
                        print(colored("Scraping stopped by stop event", "yellow"))
                        return

                    title = post.get_text(strip=True)
                    post_url = urllib.parse.urljoin(forum_url, post['href'])
                    print(colored(f"Scraping post: {title}", "cyan"))

                    content = scrape_post_content(session, post_url)
                    # Extract the author correctly
                    author_tag = post.find_parent('div').find_next('div', class_='author smalltext')
                    author = author_tag.get_text(strip=True) if author_tag else "Unknown"

                    # Classify content and store it
                    classification = classify_content(content)
                    print(f"Classification: {classification}")

                    post_data = {
                        "Title": title,
                        "Author": author,
                        "Content": content,
                        "Classification": classification,
                        "URL": post_url
                    }

                    if collection.count_documents({"URL": post_url}, limit=1) == 0:
                        collection.insert_one(post_data)
                        print(colored(f"Saved post: {title}", "green"))
                    else:
                        print(colored(f"Post already exists in database: {title}", "yellow"))

                # Pagination handling
                pagination_links = soup.select('div.pagination a.pagination_page')
                for link in pagination_links:
                    next_page = urllib.parse.urljoin(forum_url, link['href'])
                    if next_page not in to_scrape and next_page not in scraped:
                        to_scrape.append(next_page)

                scraped.add(url)
        except Exception as e:
            print(colored(f"Error scraping forum page {url}: {e}", "red"))

        # Add a small delay to prevent overwhelming the server
        time.sleep(random.uniform(1, 3))

def main(stop_event=None):
    """Main scraper function with stop event support."""
    driver = configure_webdriver()
    print(colored(f"Opening URL: {start_url}", "blue"))
    driver.get(start_url)
    print(colored("Waiting 60 seconds to establish session...", "yellow"))
    time.sleep(60)

    # Check for stop event after initial wait
    if stop_event and stop_event.is_set():
        print(colored("Scraping stopped before starting", "yellow"))
        driver.quit()
        return

    try:
        cookies = extract_cookies(driver)
        session = setup_requests_session(cookies)

        response = session.get(start_url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            forum_links = soup.select('strong > a[href^="forumdisplay.php"]')

            forums_to_scrape = [urllib.parse.urljoin(start_url, link['href']) for link in forum_links]
            print(colored(f"Found forums: {forums_to_scrape}", "green"))

            for forum_url in forums_to_scrape:
                # Check for stop event before each forum
                if stop_event and stop_event.is_set():
                    print(colored("Scraping stopped before forum", "yellow"))
                    break

                print(colored(f"Scraping forum: {forum_url}", "cyan"))
                scrape_forum(session, forum_url, stop_event)

    except Exception as e:
        print(colored(f"Error accessing CryptBB homepage: {e}", "red"))
    finally:
        # Ensure driver is closed
        driver.quit()

if __name__ == "__main__":
    main()