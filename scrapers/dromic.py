# Scrape pages

import os, time, requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://dromic.dswd.gov.ph/category/situation-reports/"  # starting list page
DOWNLOAD_DIR = "./downloads"
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
    """Convert Google Docs 'edit' link to a direct .docx export URL if applicable."""
    if "/document/d/" in url:
        file_id = url.split("/document/d/")[1].split("/")[0]
        return f"https://docs.google.com/document/d/{file_id}/export?format=docx"
    return url

def download_file(url: str):
    """Download a file from a direct link."""
    try:
        filename = url.split("/")[-1].split("?")[0]
        path = os.path.join(DOWNLOAD_DIR, filename)
        print(f"⬇️  Downloading {filename}")
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            with open(path, "wb") as f:
                f.write(r.content)
            print(f"✅ Saved: {filename}")
        else:
            print(f"⚠️  Skipped (HTTP {r.status_code}): {url}")
    except Exception as e:
        print(f"❌ Error downloading {url}: {e}")

def extract_first_download_link():
    """
    Looks for the *first* valid download link in multiple possible locations:
    1. <a href="..."> containing .pdf, .docx, .doc
    2. Google Docs links
    3. Links inside embed sections or .wp-block-file
    """
    selectors = [
        "div.post-content a[href*='.pdf']",
        "div.post-content a[href*='.docx']",
        "div.post-content a[href*='.doc']",
        "div.post-content a[href*='docs.google.com']",
        ".wp-block-file a[href]",
        "p.embed_download a[href]",
    ]
    for sel in selectors:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        if elems:
            href = elems[0].get_attribute("href")
            if href:
                return make_direct_download_link(href)
    return None

def handle_page():
    """Click through all 'Read More' links and download the first document per post."""
    read_mores = driver.find_elements(By.XPATH, "//a[contains(.,'Read More')] | //button[contains(.,'Read More')]")
    print(f"Found {len(read_mores)} posts on this page.")
    
    for i in range(len(read_mores)):
        read_mores = driver.find_elements(By.XPATH, "//a[contains(.,'Read More')] | //button[contains(.,'Read More')]")
        if i >= len(read_mores):
            break
        btn = read_mores[i]

        driver.execute_script("arguments[0].scrollIntoView();", btn)
        btn.click()

        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.post-content")))
            file_url = extract_first_download_link()
            if file_url:
                download_file(file_url)
            else:
                print("⚠️  No downloadable link found on this post.")
        except Exception as e:
            print("❌ Error processing post:", e)

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
    print(f"\n📄 Processing page {page}...")
    handle_page()
    page += 1
    if not goto_page(page):
        print("\n✅ All pages processed.")
        break

driver.quit()
