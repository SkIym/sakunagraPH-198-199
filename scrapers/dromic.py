# Scrape pages

import os, time, requests
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import sys
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

# === Setup logging ===
LOG_FILE = f"scraper_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)  # also print to console
    ]
)

log = logging.getLogger()

BASE_URL = "https://dromic.dswd.gov.ph/category/situation-reports/2021"  # starting list page
DOWNLOAD_DIR = "../data/dromic/2021"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# === Setup Selenium ===
opts = webdriver.ChromeOptions()
prefs = {
    "download.default_directory": os.path.abspath(DOWNLOAD_DIR),
    "download.prompt_for_download": False,
    "safebrowsing.enabled": True
}
opts.add_experimental_option("prefs", prefs)
# opts.add_argument("--headless=new")  # uncomment for silent run
driver = webdriver.Chrome(options=opts)
wait = WebDriverWait(driver, 10)

driver.get(BASE_URL)

# === Helpers ===

def make_direct_download_link(url: str):
    """
    Convert Google Docs links (edit/viewer) or viewer wrappers into a direct file URL.
    """
    # Case 1: Google Docs "document/d/" edit link → export
    if "/document/d/" in url:
        file_id = url.split("/document/d/")[1].split("/")[0]
        return f"https://docs.google.com/document/d/{file_id}/export?format=docx"

    # Case 2: Google viewer wrapper → extract actual file URL from query
    if "docs.google.com/viewer" in url:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "url" in qs:
            actual_url = unquote(qs["url"][0])
            log.info(f"🔍 Extracted direct file URL: {actual_url}")
            return actual_url

    # Default: return as-is
    return url
def download_file(url: str, filename_hint: str = None):
    """Download a file, preserving the actual filename from the server or URL."""
    try:
        r = requests.get(url, timeout=30, allow_redirects=True)

        if r.status_code != 200:
            log.warning(f"⚠️  Skipped (HTTP {r.status_code}): {url}")
            return

        from urllib.parse import unquote
        filename = None

        # --- Try to get filename from response headers ---
        content_disp = r.headers.get("content-disposition", "")
        if content_disp:

            # Try RFC 5987 encoded form first (filename*=UTF-8''...)
            match_star = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", content_disp)
            match_normal = re.search(r'filename="?([^";]+)"?', content_disp)

            if match_star:
                filename = unquote(match_star.group(1))
            elif match_normal:
                filename = unquote(match_normal.group(1))

        print(f"filename_hint: {filename_hint}, filename: {filename}, url: {url}")
        # --- If still no filename, use last part of URL ---
        if not filename:
            print("getting filname from url")
            filename = os.path.basename(url.split("?")[0])

        # --- Only if *still* no filename (very rare), fall back to hint ---
        if not filename or filename.lower() in ("", "download", "viewer", "open in new tab"):
            filename = filename_hint or f"downloaded_{int(time.time())}"

        # Only sanitize illegal filesystem characters (not spaces)
        filename = re.sub(r'[<>:"/\\|?*]+', '', filename).strip()

        # --- Guess extension if missing ---
        if not os.path.splitext(filename)[1]:
            ctype = r.headers.get("content-type", "")
            if "pdf" in ctype:
                filename += ".pdf"
            elif "word" in ctype or ".doc" in url:
                filename += ".docx"
            else:
                filename += ".bin"

        path = os.path.join(DOWNLOAD_DIR, filename)

        log.info(f"⬇️  Downloading {filename}")
        with open(path, "wb") as f:
            f.write(r.content)
        log.info(f"✅ Saved as: {filename}")

    except Exception as e:
        log.error(f"❌ Error downloading {url}: {e}")


def extract_first_download_link():
    """
    Looks for the *first* valid download link in multiple possible locations.
    Returns (url, filename_text)
    """
    selectors = [
        "div.post-content a[href*='.pdf']",
        "div.post-content a[href*='.docx']",
        "div.post-content a[href*='.doc']",
        "div.post-content a[href*='docs.google.com']",
        ".wp-block-file a[href]",
        "p.embed_download a[href]",
    ]

    # print title

    title = driver.find_element(By.CSS_SELECTOR, "h1.post-title")
    log.info(f"{title.text.strip()}")
    
    for sel in selectors:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        if elems:
            elem = elems[0]
            href = elem.get_attribute("href")
            text = elem.text.strip() or "downloaded_file"
            if href:
                return make_direct_download_link(href), text
    return None, None


def handle_page():
    """Click through all 'Read More' links and download the first document per post."""
    read_mores = driver.find_elements(By.XPATH, "//a[contains(.,'Read More')] | //button[contains(.,'Read More')]")
    log.info(f"Found {len(read_mores)} posts on this page.")
    
    for i in range(len(read_mores)):
        read_mores = driver.find_elements(By.XPATH, "//a[contains(.,'Read More')] | //button[contains(.,'Read More')]")
        if i >= len(read_mores):
            break
        btn = read_mores[i]

        driver.execute_script("arguments[0].scrollIntoView(true); window.scrollBy(0, -150);", btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", btn)

        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.post-content")))
            file_url, file_name = extract_first_download_link()
            if file_url:
                download_file(file_url, file_name)
            else:
                log.warning("⚠️  No downloadable link found on this post.")
        except Exception as e:
            log.error("❌ Error processing post:", e)

        # Go back to listing
        driver.back()
        wait.until(EC.presence_of_all_elements_located((By.XPATH, "//a[contains(.,'Read More')] | //button[contains(.,'Read More')]")))
        time.sleep(1)

def goto_page(page_num):
    """Click pagination button by visible number."""
    try:
        pagination_el = wait.until(EC.element_to_be_clickable((
            By.XPATH, f"//ul[contains(@class,'pagination')]//li//*[normalize-space()='{page_num}']"
        )))
        driver.execute_script("arguments[0].scrollIntoView();", pagination_el)
        pagination_el.click()
        wait.until(EC.presence_of_all_elements_located((By.XPATH, "//a[contains(.,'Read More')]")))
        return True
    except:
        return False

# === MAIN LOOP ===
page = 1
while True:
    log.info(f"\n📄 Processing page {page}...")
    handle_page()
    page += 1
    if not goto_page(page):
        log.info("\n✅ All pages processed.")
        break

driver.quit()
