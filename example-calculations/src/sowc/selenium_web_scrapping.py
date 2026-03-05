# pylint: disable=too-many-locals, too-many-branches, too-many-nested-blocks, consider-using-generator
import time
import os
import shutil
import tempfile
from datetime import datetime

import boto3
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# Local testing
DOWNLOAD_PATH = '/Users/ijauregi/Desktop/RozettaTech/2024/llm-testing'
GOOGLE_CHROME_VERSION = '130.0.6723.117'

# EC2 remote server
# DOWNLOAD_PATH = '/home/ec2-user/llm-testing'
# GOOGLE_CHROME_VERSION = '131.0.6778.85'


def handle_agree_page(driver):
    try:
        # Wait for the popup window
        time.sleep(2)  # Wait for popup to fully load

        # Switch to the popup window
        windows = driver.window_handles
        for window in windows:
            driver.switch_to.window(window)
            # Check if this is the popup by looking for the form
            if "showAnnouncementPDFForm" in driver.page_source:
                break

        # Find the form
        form = driver.find_element(By.NAME, "showAnnouncementPDFForm")

        # Find the Agree button within the form
        agree_button = form.find_element(By.CSS_SELECTOR, "input[value='Agree and proceed']")
        agree_button.click()

        # Wait for PDF to load
        time.sleep(2)

        return True

    except Exception as e:  # pylint: disable=broad-exception-raised, broad-exception-caught
        print(f"Error in handle_agree_page: {e}")
        # Print debugging info
        print("Current windows:", driver.window_handles)
        print("Current URL:", driver.current_url)
        return False


def wait_for_element(driver, by, value, timeout=20):
    """Wait for element to be present and return it"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except TimeoutException:
        print(f"Timeout waiting for element: {value}")
        return None


def download_announcements(download_dir_ticker, ticker, year):

    handle_page_found = False

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_experimental_option("prefs", {
        "download.default_directory": download_dir_ticker,
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "no-sandbox": True,
        "disable-dev-shm-usage": True,
        "disable-gpu": True
    })

    # Initialize WebDriver
    service = Service(ChromeDriverManager(driver_version=GOOGLE_CHROME_VERSION).install())
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 20)

    try:
        # Navigate to ASX announcements page
        url = "https://www.asx.com.au/asx/v2/statistics/announcements.do"
        driver.get(url)

        # Find the search input for ticker symbol
        search_input = wait.until(EC.presence_of_element_located((By.ID, "issuerCode")))
        search_input.clear()
        search_input.send_keys(ticker)  # Ticker symbol for Qantas

        # Set the year filter to 2024
        radio_button = driver.find_element(By.ID, 'timeframeType2')
        radio_button.click()

        search_input = wait.until(EC.presence_of_element_located((By.ID, "year")))
        driver.find_element(By.ID, "year").send_keys(year)

        # search_input.send_keys(Keys.RETURN)
        # Find and click the search button instead of using RETURN key
        try:

            search_button = wait_for_element(driver, By.XPATH, "//input[@value='Search']")

            if search_button:
                # Use JavaScript click for more reliable clicking
                driver.execute_script("arguments[0].click();", search_button)
            else:
                raise Exception("Could not find search button")  # pylint: disable=broad-exception-raised

            # # Wait for results to load
            # time.sleep(5)  # Increased wait time after search
            #
            # # Wait for the results table to appear
            # wait_for_element(driver, By.TAG_NAME, "tbody")

        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Error clicking search button: {e}")
            raise

        # Wait for results to load
        time.sleep(2)

        # Scroll and collect download links
        while True:

            try:
                # Find all announcement rows
                tbody = wait.until(EC.presence_of_element_located((By.TAG_NAME, "tbody")))
                # Find all table rows
                announcements = tbody.find_elements(By.TAG_NAME, "tr")
                for i, announcement in enumerate(announcements):
                    try:
                        # Find date in the html
                        date_str = announcement.find_element(By.XPATH, "td").text
                        # convert date to datetime
                        date = datetime.strptime(date_str.split('\n')[0].strip(), "%d/%m/%Y")
                        # Convert back to string
                        date_str = date.strftime("%Y_%m_%d")
                        # Find and click the download link
                        link = announcement.find_element(By.TAG_NAME, "a")
                        pdf_url = link.get_attribute("href")

                        if not handle_page_found:
                            link.click()
                            # Handle the agree page if it appears
                            handle_page_found = handle_agree_page(driver)
                            driver.switch_to.window(driver.window_handles[1])  # Switch to the new window

                        else:
                            # if handle_page_found:
                            driver.get(pdf_url)  # Download the PDF
                            time.sleep(2)  # Allow time for the file to start downloading

                        # Find the downloaded file
                        downloaded_files = os.listdir(download_dir_ticker)

                        # Assume the most recently modified file is our download
                        latest_file = max([os.path.join(download_dir_ticker, f) for f in downloaded_files],
                                          key=os.path.getctime)
                        # Construct the new file path with the desired name
                        new_file_path = os.path.join(download_dir_ticker, f'{ticker}_announcement_{i}_{date_str}.pdf')

                        # Rename the downloaded file
                        os.rename(latest_file, new_file_path)

                        if not handle_page_found:
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                        # driver.close()
                        # driver.switch_to.window(driver.window_handles[0])  # Switch back to the main window

                    except Exception as e:  # pylint: disable=broad-exception-raised, broad-exception-caught
                        print(f"Error downloading announcement: {e}")
                        driver.switch_to.window(driver.window_handles[0])  # Switch back to the main window
            except Exception as e:  # pylint: disable=broad-exception-raised, broad-exception-caught
                print('tbody exception')

            # Check if there is a "Next" button and click it
            try:
                next_button = driver.find_element(By.LINK_TEXT, "Next")
                if "disabled" in next_button.get_attribute("class"):
                    break  # Exit if the next button is disabled
                next_button.click()
                time.sleep(2)  # Wait for the next page to load
            except Exception as e:  # pylint: disable=broad-exception-raised, broad-exception-caught
                break  # No "Next" button found, exit the loop

    finally:
        # Quit the browser
        driver.quit()

    print(f"Announcements downloaded to {download_dir_ticker}")


def create_s3_client(profile_name='default'):
    session = boto3.Session(profile_name=profile_name)
    # session = boto3.Session()
    return session.client('s3')


def check_if_processed(ticker, year):
    s3 = create_s3_client('dse_general@dev1')
    try:
        response = s3.list_objects_v2(
            Bucket='cissa',
            Prefix=f'ASX_company_announcements/{ticker}/{year}/',
            MaxKeys=1  # We only need to know if anything exists
        )
        return 'Contents' in response
    except Exception as e:  # pylint: disable=broad-exception-raised, broad-exception-caught
        print(f"Error checking if processed: {e}")
        return False


def main():

    # List of years
    range_years = list(range(2000, 2025))

    # List of tickers
    df = pd.read_csv('data/benchmark_weights.csv')
    ticker_list = [name.split()[0] for name in df['ticker'].tolist()]
    ticker_list.reverse()

    for ticker in ticker_list:
        for year in range_years:

            if check_if_processed(ticker, year):
                continue

            temp_dir = tempfile.mkdtemp(prefix=f"{DOWNLOAD_PATH}/sowc_tmp")
            download_dir_ticker = f'{temp_dir}/{ticker}/{year}'
            os.makedirs(download_dir_ticker, exist_ok=True)
            print(f"Downloading announcements, Ticker -> {ticker}  Year -> {year}")
            download_announcements(download_dir_ticker, ticker, str(year))

            # Upload to s3
            s3 = create_s3_client('dse_general@dev1')
            for root, _, files in os.walk(download_dir_ticker):
                for file in files:
                    s3.upload_file(os.path.join(root, file),
                                   'cissa',
                                   f'ASX_company_announcements/{ticker}/{year}/{file}')

            # Remove local files
            # os.system(f'rm -rf {DOWNLOAD_PATH}/tmp')
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
