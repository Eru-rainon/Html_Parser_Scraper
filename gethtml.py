import csv
import time
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Your custom parsers
from htmlParser import parse_products
from reviewParser import parse_reviews

driver = webdriver.Chrome()

try:
    driver.get("https://www.amazon.in")
    wait = WebDriverWait(driver, 10)

    with open("dummydata.csv", newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            keyword = row["main_search_term"].strip()
            print(f"\n--- Searching for: {keyword} ---")

            # Search
            search_box = wait.until(
                EC.presence_of_element_located((By.ID, "twotabsearchtextbox"))
            )
            search_box.clear()
            search_box.send_keys(keyword)
            search_box.send_keys(Keys.RETURN)

            # Wait for results
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-main-slot"))
            )

            # Parse product list page
            html = driver.page_source
            filename = parse_products(html, keyword)
            print(f"Saved: {filename}")

            time.sleep(2)

            # Get all clickable image elements
            images = driver.find_elements(
                By.XPATH,
                "//a[.//img[@class='s-image']]"
            )

            print(f"Found {len(images)} products")

            # Loop through images
            for i in range(len(images)):
                try:
                    # Re-fetch elements to avoid stale reference 
                    # (Amazon lazy-loads, so scrolling changes the DOM)
                    images = driver.find_elements(
                        By.XPATH,
                        "//a[.//img[@class='s-image']]"
                    )
                    img = images[i]

                    # Scroll into view (centered is usually safer for clicking)
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", img)
                    time.sleep(1)

                    # --- Window Handling Start ---
                    
                    # 1. Save the main search page window handle
                    original_window = driver.current_window_handle
                    current_window_count = len(driver.window_handles)

                    # 2. Click product (Opens in a new tab)
                    img.click()

                    # 3. Wait for the new tab to open
                    wait.until(EC.number_of_windows_to_be(current_window_count + 1))

                    # 4. Switch Selenium's focus to the new tab
                    for window_handle in driver.window_handles:
                        if window_handle != original_window:
                            driver.switch_to.window(window_handle)
                            break
                    
                    # Nested try-finally to guarantee the new tab gets closed
                    try:
                        # Wait for product page to load
                        wait.until(EC.presence_of_element_located((By.ID, "productTitle")))

                        current_url = driver.current_url
                        asin_match = re.search(r"B0[A-Z0-9]{8}", current_url)
                        
                        # Fallback just in case the URL doesn't have a standard ASIN
                        product_asin = asin_match.group(0) if asin_match else "UNKNOWN_ASIN"
                        print(f"  -> Extracted ASIN: {product_asin}")

                        time.sleep(2) 

                        # Get reviews section HTML
                        try:
                            print(f"  -> Looking for review element on page...")
                            # 1. Test the XPath
                            review_element = wait.until(
                                EC.presence_of_element_located((
                                    By.XPATH,
                                    '//*[@id="reviewsMedley"]/div/div[2]/div/div[2]/div[3]/span/div/div'
                                ))
                            )
                            
                            print(f"  -> Element found! Getting HTML...")
                            review_html = review_element.get_attribute("outerHTML")

                            print(f"  -> Passing HTML to parser...")
                            # 2. Test the Parser
                            parse_reviews(review_html, product_asin)
                            print(f"  -> Successfully scraped reviews for item {i+1}")

                        except TimeoutException:
                            # This happens if the WebDriverWait finishes without finding the XPath
                            print(f"❌ XPATH ISSUE for item {i+1}: Selenium could not find the element.")
                            
                        except Exception as e:
                            # This happens if Selenium found it, but your parser crashed
                            print(f"❌ PARSER ISSUE for item {i+1}: Element was found, but parser failed.")
                            print(f"   Exact Error: {e}")

                    finally:
                        # 5. Close the current tab (the product page)
                        driver.close()
                        
                        # 6. Switch focus back to the original search results tab
                        driver.switch_to.window(original_window)
                        
                    # --- Window Handling End ---

                except Exception as e:
                    print(f"Error at index {i+1}: {e}")
                    
                    # Failsafe: If something broke heavily and we are stuck with multiple tabs, 
                    # close the extras and return to the main window so the loop can continue.
                    if len(driver.window_handles) > 1:
                        for handle in driver.window_handles:
                            if handle != original_window:
                                driver.switch_to.window(handle)
                                driver.close()
                        driver.switch_to.window(original_window)
                    continue

            time.sleep(3)

finally:
    driver.quit()