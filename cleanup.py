import os
import mysql.connector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
db_config = {
    'user': os.getenv('USER'),
    'password': os.getenv('PASSWORD'),
    'host': os.getenv('HOST'),
    'database': os.getenv('DATABASE')
}

# Path to the screenshots folder
screenshots_folder = 'screenshots'

def get_small_files(folder):
    small_files = []
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path) and os.path.getsize(file_path) < 2048:  # less than 2KB
            small_files.append(filename)
    return small_files

def delete_files_and_db_entries(files):
    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        for file in files:
            domain = file.replace('.png', '')

            # Delete from database
            query = "DELETE FROM url_screenshots WHERE root_domain = %s"
            cursor.execute(query, (domain,))

            # Delete file
            os.remove(os.path.join(screenshots_folder, file))

        connection.commit()
    except mysql.connector.Error as error:
        print(f"Error: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()

small_files = get_small_files(screenshots_folder)

if small_files:
    response = input(f"Are you sure you want to delete {len(small_files)} items? (yes/no): ")
    if response.lower() == 'yes':
        delete_files_and_db_entries(small_files)
        print("Small files and corresponding database entries deleted successfully.")
    else:
        print("Deletion cancelled.")
else:
    print("No small files found to delete.")