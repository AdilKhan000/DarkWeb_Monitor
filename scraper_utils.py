import re
import requests
from selenium import webdriver

proxy_host = "127.0.0.1"
proxy_port = 8118

def clean_text(text):
    """Clean text by removing unwanted characters."""
    text = re.sub(r'[\n\r]+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def extract_cookies(driver):
    """Extract cookies from a Selenium driver."""
    cookies = driver.get_cookies()
    driver.quit()
    return {cookie['name']: cookie['value'] for cookie in cookies}

def setup_requests_session(cookies):
    """Set up a requests session with the given cookies."""
    session = requests.Session()
    session.proxies = {'http': f'http://{proxy_host}:{proxy_port}', 'https': f'http://{proxy_host}:{proxy_port}'}
    session.cookies.update(cookies)
    return session

def configure_webdriver():
    """Configure and return a Selenium WebDriver."""
    options = webdriver.FirefoxOptions()
    options.set_preference("network.proxy.type", 1)
    options.set_preference("network.proxy.http", proxy_host)
    options.set_preference("network.proxy.http_port", proxy_port)
    options.set_preference("network.proxy.ssl", proxy_host)
    options.set_preference("network.proxy.ssl_port", proxy_port)
    options.set_preference("network.proxy.socks", proxy_host)
    options.set_preference("network.proxy.socks_port", proxy_port)
    options.set_preference("network.proxy.socks_version", 5)
    options.set_preference("network.proxy.no_proxies_on", "")
    return webdriver.Firefox(options=options)
