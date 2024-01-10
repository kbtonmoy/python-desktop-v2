import logging
import os
import csv
import sys
import requests
import mysql.connector
import concurrent.futures
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure the 'logs' and 'screenshots' directory exists
if not os.path.exists('logs'):
    os.makedirs('logs')

if not os.path.exists('screenshots'):
    os.makedirs('screenshots')    

logging.basicConfig(filename='logs/screenshot.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

# Database connection
db_config = {
    'host': os.getenv('HOST'),
    'user': os.getenv('USER'),
    'password': os.getenv('PASSWORD'),
    'database': os.getenv('DATABASE')
}

def connect_db():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        logging.error(f"Database connection error: {err}")

def bulk_check_existing_domains(root_domains):
    db = connect_db()
    cursor = db.cursor()
    format_strings = ','.join(['%s'] * len(root_domains))
    query = f"SELECT root_domain FROM url_screenshots WHERE root_domain IN ({format_strings})"
    cursor.execute(query, tuple(root_domains))
    existing_domains = [item[0] for item in cursor.fetchall()]
    cursor.close()
    db.close()
    return [domain for domain in root_domains if domain not in existing_domains]

def sanitize_root_domain(root_domain):
    return root_domain.replace('http://', '').replace('https://', '').replace('www.', '').replace('/', '_')

def get_screenshot(root_domain):
    logging.info(f"Start capturing {root_domain}")
    print(f"Start capturing {root_domain}")
    sanitized_domain = sanitize_root_domain(root_domain)
    api_url = f"http://74.50.70.82:4000/api/screenshot?resX=1920&resY=1080&outFormat=png&waitTime=100&isFullPage=false&dismissModals=true&url=http://{sanitized_domain}"
    response = requests.get(api_url)
    if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
        file_name = f'screenshots/{sanitized_domain}.png'
        with open(file_name, 'wb') as file:
            file.write(response.content)

        logging.info(f"Image saved as {file_name}")
        print(f"Image saved as {file_name}")
        return sanitized_domain
    else:
        print(f"Invalid Domain {root_domain}")
        logging.error(f"Failed to capture {root_domain}. Invalid Domain")
    return None

def save_to_db(root_domain, location):
    db = connect_db()
    cursor = db.cursor()
    query = "INSERT INTO url_screenshots (root_domain, location) VALUES (%s, %s) ON DUPLICATE KEY UPDATE location = VALUES(location)"
    cursor.execute(query, (root_domain, location))
    db.commit()
    cursor.close()
    db.close()

def process_root_domain(root_domain):
    sanitized_domain = get_screenshot(root_domain)
    if sanitized_domain:
        save_to_db(root_domain, f'screenshots/{sanitized_domain}.png')

def process_batch(root_domains):
    domains_to_process = bulk_check_existing_domains(root_domains)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_root_domain, domains_to_process)

def test_db_connection():
    try:
        db = connect_db()
        cursor = db.cursor()
        cursor.execute("SELECT VERSION()")
        results = cursor.fetchone()
        print(f"Database connected successfully. MySQL version: {results}")
        cursor.close()
        db.close()
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")
        sys.exit(1)

def main():
    test_db_connection()
    input_file = input("Enter the path to the CSV file: ")
    batch_size = 1000  # Adjust based on system capability

    with open(input_file, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        batch = []

        for row in reader:
            batch.append(row['url'])
            if len(batch) >= batch_size:
                process_batch(batch)
                batch = []

        if batch:  # Process any remaining URLs
            process_batch(batch)

    logging.info("All URLs have been processed.")
    print("All URLs have been processed.")
    input("Press Enter to exit...")  # Wait for user input before exiting

if __name__ == "__main__":
    main()
