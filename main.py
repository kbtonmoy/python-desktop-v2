import re
import shutil
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error
from requests.auth import HTTPBasicAuth
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import csv
import queue
import cv2
from moviepy.editor import VideoFileClip
from threading import Thread, Semaphore
import os
import requests

load_dotenv()
class DatabaseApp:
    def __init__(self, root):

        self.root = root
        self.root.title("Database Connection App")
        self.connection_details = {}
        self.connection = None  # Database connection instance variable
        self.create_connection_frame()
        self.completed_threads = 0
        self.total_chunks = 0
        self.completed_chunks = 0
        self.current_chunk_index = -1
        self.thread_semaphore = Semaphore(4)
        self.failed_urls = []


# All Frames are here

    def create_connection_frame(self):
        self.connection_frame = tk.Frame(self.root)
        self.connection_frame.pack(padx=10, pady=10)

        tk.Label(self.connection_frame, text="Host:").grid(row=0, column=0, sticky="w")
        self.host_entry = tk.Entry(self.connection_frame)
        self.host_entry.grid(row=0, column=1, pady=5)

        tk.Label(self.connection_frame, text="User:").grid(row=1, column=0, sticky="w")
        self.user_entry = tk.Entry(self.connection_frame)
        self.user_entry.grid(row=1, column=1, pady=5)

        tk.Label(self.connection_frame, text="Password:").grid(row=2, column=0, sticky="w")
        self.password_entry = tk.Entry(self.connection_frame, show="*")
        self.password_entry.grid(row=2, column=1, pady=5)

        tk.Label(self.connection_frame, text="Database:").grid(row=3, column=0, sticky="w")
        self.database_entry = tk.Entry(self.connection_frame)
        self.database_entry.grid(row=3, column=1, pady=5)

        tk.Button(self.connection_frame, text="Connect", command=self.connect_to_database).grid(row=4, columnspan=2,
                                                                                                pady=10)

    def show_success_frame(self):
        self.create_option_buttons()

    def take_screenshots_frame(self):
        self.clear_all_widgets()
        self.create_upload_csv_button()


# All Buttons are here

    def create_option_buttons(self):
        # New method to create buttons for "Take Screenshots", "Prepare Videos", "Upload on YouTube"
        tk.Button(self.root, text="Take Screenshots", command=self.take_screenshots_frame).pack(padx=10, pady=10)
        tk.Button(self.root, text="Prepare Videos", command=self.open_video_preparation_frame).pack(padx=10, pady=10)
        tk.Button(self.root, text="Upload on Video Server", command=self.process_and_upload_videos).pack(padx=10, pady=10)
        tk.Button(self.root, text="Generate WP Pages ", command=self.open_wp_page_generate_frame).pack(padx=10, pady=10)

    def create_screenshot_button(self):
        self.screenshot_button = tk.Button(self.root, text="Start Capturing", command=self.take_screenshots)
        self.screenshot_button.pack(pady=10)

    def create_upload_csv_button(self):
        tk.Button(self.root, text="Upload CSV", command=self.upload_csv).pack(pady=5)


# ALl logical Functions are here
    def connect_to_database(self):
        host = os.getenv("HOST")
        user = os.getenv("USER")
        password = os.getenv("PASSWORD")
        database = os.getenv("DATABASE")

        try:
            self.connection = mysql.connector.connect(host=host, user=user, password=password, database=database)
            self.host = host
            self.user = user
            self.password = password
            self.database = database
            if self.connection.is_connected():
                self.connection_frame.destroy()
                self.show_success_frame()
        except Error as e:
            messagebox.showerror("Error", f"Error connecting to MySQL Database: {e}")

    def upload_csv(self):
        filename = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if filename:
            self.process_csv(filename)

    def check_duplicates_in_database(self, urls):
        cursor = self.connection.cursor()
        query = "SELECT root_domain FROM url_screenshots WHERE root_domain IN (%s)"
        format_strings = ','.join(['%s'] * len(urls))
        cursor.execute(query % format_strings, tuple(urls))
        result = cursor.fetchall()
        cursor.close()
        return [item[0] for item in result]

    def process_csv(self, filename):
        chunk_size = 500  # Set the chunk size
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            chunk = []
            self.total_chunks = 0
            self.completed_chunks = 0
            for row in reader:
                chunk.append(row['url'])
                if len(chunk) == chunk_size:
                    self.process_chunk(chunk)
                    chunk = []
                    self.total_chunks += 1
            if chunk:
                self.process_chunk(chunk)
                self.total_chunks += 1

    def process_chunk(self, urls):
        self.failed_urls.clear()
        duplicates = self.check_duplicates_in_database(urls)
        urls = list(set(urls) - set(duplicates))
        self.start_screenshot_process(urls)

    def start_screenshot_process(self, urls):
        self.current_chunk_index += 1
        self.render_label = tk.Label(self.root, text="Screenshot taking process is running. Please hold tight.")
        self.render_label.pack(pady=5)

        # Reset the completed threads for this batch of URLs
        self.completed_threads = 0
        self.total_chunks = len(urls)  # Assuming each URL is treated as a chunk here

        # Start processing URLs in a separate thread to avoid blocking the GUI
        process_thread = threading.Thread(target=self.process_urls, args=(urls,))
        process_thread.start()

    def process_urls(self, urls):
        self.queue = queue.Queue()
        for url in urls:
            self.thread_semaphore.acquire()
            thread = threading.Thread(target=self.take_screenshots, args=(url, self.queue))
            thread.start()

        # After processing all URLs, check for completion
        self.check_queue()

    def check_queue(self):
        try:
            while True:
                message = self.queue.get_nowait()
                if message == "progress":
                    self.completed_threads += 1
        except queue.Empty:
            pass

        # Schedule this method to be called again after a short delay
        self.root.after(100, self.check_queue)

        # Check if the processing of all chunks is completed
        if self.completed_threads >= self.total_chunks:
            self.render_label.config(text="Screenshot taking process completed.")
            messagebox.showinfo("Info", "Screenshots taken for all URLs and database updated")
            self.clear_all_widgets()
            self.create_option_buttons()
        # Otherwise, continue checking

    def take_screenshots(self, url, queue):
        max_retries = 3  # Maximum number of retries for each URL
        success = False

        for attempt in range(max_retries):
            driver = None  # Initialize driver to None
            try:
                # Set up Chrome options for headless browsing
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--ignore-certificate-errors")
                chrome_options.add_argument("--start-maximized")
                chrome_options.add_argument("--window-size=1920,1080")
                chrome_options.add_argument("--hide-scrollbars")

                # Suppress the verbose logging
                chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
                chrome_options.add_argument("--log-level=3")  # This sets the logging level to SEVERE

                # Initialize the Chrome WebDriver
                driver = webdriver.Chrome(options=chrome_options)
                driver.set_page_load_timeout(10)  # Setting a timeout for page load

                # Ensure the screenshots directory exists
                os.makedirs('screenshots', exist_ok=True)

                # Function to attempt to load the URL and take a screenshot
                def attempt_load_and_capture(url_with_protocol):
                    try:
                        driver.get(url_with_protocol)
                        driver.implicitly_wait(5)  # Adjust the timeout as needed
                        screenshot_filename = f"{url.replace('http://', '').replace('https://', '').replace('www.', '').replace('/', '_')}.png"
                        screenshot_path = os.path.join('screenshots', screenshot_filename)
                        driver.save_screenshot(screenshot_path)
                        self.update_database(url, screenshot_path)
                        return True
                    except TimeoutException:
                        print(f"Timeout while accessing {url_with_protocol}")
                        return False  # Indicates a timeout occurred
                    except Exception as e:
                        print(f"Error taking screenshot of {url_with_protocol}: {e}")
                        return False

                # Try loading and capturing the URL
                if not url.startswith(('http://', 'https://')):
                    # Try with various URL prefixes
                    for prefix in ['https://', 'https://www.', 'http://']:
                        if attempt_load_and_capture(prefix + url):
                            success = True
                            break  # Exit if successful

                if success:
                    break  # Exit the retry loop if successful

            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {url}: {e}")

            finally:
                if driver:
                    driver.quit()

        if not success:
            # If all retries fail, use external API
            success = self.take_screenshot_with_external_api(url)

        # Put a 'progress' message in the queue when a screenshot task is completed
        self.queue.put("progress")
        self.thread_semaphore.release()

    def take_screenshot_with_external_api(self, url):
        api_url = f"http://64.176.199.218:4000/api/screenshot?resX=1920&resY=1080&outFormat=jpg&waitTime=100&isFullPage=false&dismissModals=true&url=http://{url}"
        sanitized_url = url.replace('http://', '').replace('https://', '').replace('www.', '').replace('/', '_')
        output_file = f"screenshots/{sanitized_url}.jpg"

        try:
            response = requests.get(api_url)
            if response.status_code == 200:
                with open(output_file, "wb") as file:
                    file.write(response.content)
                print(f"Image saved as {output_file}")
                self.update_database(url, output_file)  # Update the database
                return True
            else:
                print(f"Failed to fetch the image for {url}. Status code: {response.status_code}")
                return False
        except Exception as e:
            print(f"An error occurred while fetching {url}: {str(e)}")
            return False

    def retry_failed_urls(self):
        if self.failed_urls:
            print("Retrying failed URLs...")

            # Make a copy of failed_urls to iterate over
            urls_to_retry = self.failed_urls.copy()
            self.failed_urls.clear()

            for url in urls_to_retry:
                self.thread_semaphore.acquire()
                thread = Thread(target=self.take_screenshots, args=(url, self.queue))
                thread.start()

            # After retrying, check the failed_urls list again
            self.root.after(100, self.check_failed_urls_after_retry)

    def check_failed_urls_after_retry(self):
        if self.failed_urls:
            # If there are still failed URLs, use the external API for these
            for url in self.failed_urls.copy():
                self.take_screenshot_with_external_api(url)
            self.failed_urls.clear()

        # Check if all chunks are processed and update the UI accordingly
        if self.completed_chunks == self.total_chunks:
            messagebox.showinfo("Info", "Screenshots taken for all URLs in all chunks and database updated")
            self.clear_all_widgets()
            self.create_option_buttons()
        else:
            self.root.after(100, self.check_queue)

    def update_database(self, url, screenshot_path):
        try:
            cursor = self.connection.cursor()
            query = "INSERT INTO url_screenshots (root_domain, location) VALUES (%s, %s) ON DUPLICATE KEY UPDATE location = VALUES(location)"
            cursor.execute(query, (url, screenshot_path))
            self.connection.commit()
            cursor.close()
        except Error as e:
            messagebox.showerror("Database Error", f"Error updating the database: {e}")

    # Video Generation Logics are here
    def initialize_video_render_progress_bar(self):
        self.render_label = tk.Label(self.root, text="Rendering in progress...")
        self.render_label.pack(pady=5)
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=300, mode='determinate')
        self.progress.pack(pady=5)


    def destroy_video_render_progress_bar(self):
        if self.progress:
            self.progress.destroy()
            self.progress = None  # Set to None to avoid referencing a destroyed object

    def update_progress(self, value):
        self.progress['value'] = value

    def update_video_database(self, root_domain, full_output_path, cursor, connection):
        try:
            with open("video_description.txt", "r") as desc_file:
                description_template = desc_file.read()

            with open("video_title.txt", "r") as title_file:
                title_template = title_file.read()
            # Fetch dynamic data from ecom_platform1
            table_name = self.table_var.get()
            dynamic_data = self.get_dynamic_data(table_name, root_domain, cursor)

            # Format the description
            video_description = self.format_description(description_template, dynamic_data)

            video_title = self.format_description(title_template, dynamic_data)

            # Insert into url_videos table with description
            add_video_query = "INSERT INTO url_videos (root_domain, location, yt_video_description, yt_video_title) VALUES (%s, %s, %s, %s)"
            cursor.execute(add_video_query, (root_domain, full_output_path, video_description, video_title))
            connection.commit()
        except Exception as e:
            messagebox.showinfo("Info", f"Error updating database: {e}")

    def process_video(self, screenshot_path, video_path, output_path, temp_folder, image2_path, image3_path, timeline2, timeline3):
        def convert_to_seconds(timeline):
            mm, ss, ms = map(int, timeline.split(':'))
            converted_time = mm * 60 + ss + ms / 1000
            return converted_time

        # Convert timelines for additional images
        timeline2_seconds = convert_to_seconds(timeline2)
        timeline3_seconds = convert_to_seconds(timeline3)

        # Load the screenshots
        screenshot1 = cv2.imread(screenshot_path)
        screenshot2 = cv2.imread(image2_path)
        screenshot3 = cv2.imread(image3_path)

        facecam_video = VideoFileClip(video_path)

        def process_frame(frame, current_time=[0]):
            # Increment current time for this frame
            current_time[0] += 1 / facecam_video.fps

            if current_time[0] < timeline2_seconds:
                current_screenshot = screenshot1
            elif current_time[0] < timeline3_seconds:
                current_screenshot = screenshot2
            else:
                current_screenshot = screenshot3

            # Convert frame to RGB (OpenCV uses BGR by default)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Create a mask where black pixels ([0,0,0]) are detected in the frame
            mask = cv2.inRange(frame_rgb, (0, 0, 0), (10, 10, 10))
            # Invert mask to get parts that are not black
            mask_inv = cv2.bitwise_not(mask)
            # Use the mask to extract the facecam area (excluding black background)
            facecam_area = cv2.bitwise_and(frame_rgb, frame_rgb, mask=mask_inv)
            # Resize current screenshot to frame size
            resized_screenshot = cv2.resize(current_screenshot, (frame.shape[1], frame.shape[0]))
            # Combine the facecam area and the resized screenshot
            combined = cv2.bitwise_and(resized_screenshot, resized_screenshot, mask=mask)
            combined = cv2.add(combined, facecam_area)
            # Convert back to BGR for MoviePy
            final_frame = cv2.cvtColor(combined, cv2.COLOR_RGB2BGR)
            return final_frame

            # Wrapper function to track time


        # Apply the process_frame function to each frame of the video
        processed_video = facecam_video.fl_image(process_frame)
        # Reset the current_time for potential reusability
        self.current_time = 0
        # Use user-selected export directory
        output_dir = self.export_dir if self.export_dir else 'videos'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Generate the full output path
        full_output_path = os.path.join(output_dir, output_path)

        # Write the processed video to the full output path
        processed_video.write_videofile(full_output_path, fps=facecam_video.fps)

    def video_processing_thread(self, data, cursor, total_threads):
        local_connection = mysql.connector.connect(host=self.host, user=self.user, password=self.password,
                                                   database=self.database)
        local_cursor = local_connection.cursor()
        try:
            total_videos = len(data)
            for index, (screenshot_path, video_path, output_path, root_domain, image2_path, image3_path, timeline2,
                        timeline3) in enumerate(data):
                # Unique temporary folder for each video processing
                temp_folder = f"temp_{root_domain}_{threading.get_ident()}"
                os.makedirs(temp_folder, exist_ok=True)

                self.process_video(screenshot_path, video_path, output_path, temp_folder, image2_path, image3_path,
                                   timeline2, timeline3)
                full_output_path = os.path.join(self.export_dir if self.export_dir else 'videos', output_path)
                # Clean up the temporary folder after processing this video

                self.update_video_database(root_domain, full_output_path, local_cursor, local_connection)
                shutil.rmtree(temp_folder)
                # Update progress bar
                progress_percent = (index + 1) / total_videos * 100
                self.root.after(100, lambda p=progress_percent: self.update_progress(p))

        finally:
            local_cursor.close()
            local_connection.close()
            with threading.Lock():
                self.completed_threads += 1
                if self.completed_threads == total_threads:
                    self.root.after(100, self.on_all_threads_complete)

    def on_all_threads_complete(self):
        # This method is called when all threads are done
        self.clear_all_widgets()
        self.create_option_buttons()


    def prepare_videos_frame(self):
        cursor = self.connection.cursor()

        select_query = """
        SELECT s.root_domain, s.location
        FROM url_screenshots s
        WHERE NOT EXISTS (
            SELECT 1 FROM url_videos v WHERE v.root_domain = s.root_domain
        )
        """
        cursor.execute(select_query)
        screenshots = cursor.fetchall()

        if not screenshots:
            messagebox.showinfo("Info", "No records found. Ending process.")
            cursor.close()
            return
        self.clear_all_widgets()
        self.initialize_video_render_progress_bar()
        self.progress['value'] = 0
        self.completed_threads = 0  # Reset the counter

        total_threads = 5
        threads = []

        # Constant path for the video
        video_path = self.video_path if self.video_path else 'video.mp4'
        output_paths = [f"{root_domain}.mp4" for root_domain, _ in screenshots]

        for i in range(total_threads):
            thread_screenshots = screenshots[i::total_threads]
            thread_output_paths = output_paths[i::total_threads]

            # Include additional image paths and timelines
            thread_data = [(s[1], video_path, op, s[0], self.image2_path_var.get(), self.image3_path_var.get(),
                            self.timeline2_var.get(), self.timeline3_var.get()) for s, op in
                           zip(thread_screenshots, thread_output_paths)]

            thread = Thread(target=self.video_processing_thread, args=(thread_data, cursor, total_threads))
            threads.append(thread)
            thread.start()

        cursor.close()

    def open_video_preparation_frame(self):
        # New window (or frame) for video preparation settings
        self.clear_all_widgets()
        # Dropdown for table selection
        tk.Label(self.root, text="Select a table:").pack(pady=5)
        self.table_var = tk.StringVar()
        tables = self.get_tables()
        table_dropdown = tk.OptionMenu(self.root, self.table_var, *tables)
        table_dropdown.pack(pady=5)

        # Input field for video file
        tk.Label(self.root, text="Select a video file:").pack(pady=5)
        self.video_path_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.video_path_var, state='readonly').pack(pady=5)
        tk.Button(self.root, text="Browse", command=self.select_video_file).pack(pady=5)

        # Input field for export directory
        tk.Label(self.root, text="Select export directory:").pack(pady=5)
        self.export_dir_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.export_dir_var, state='readonly').pack(pady=5)
        tk.Button(self.root, text="Browse", command=self.select_export_directory).pack(pady=5)

        # Input fields for additional images
        self.image2_path_var = tk.StringVar()
        tk.Label(self.root, text="Upload second image:").pack(pady=5)
        tk.Entry(self.root, textvariable=self.image2_path_var, state='readonly').pack(pady=5)
        tk.Button(self.root, text="Browse", command=lambda: self.select_file(self.image2_path_var)).pack(pady=5)

        self.image3_path_var = tk.StringVar()
        tk.Label(self.root, text="Upload third image:").pack(pady=5)
        tk.Entry(self.root, textvariable=self.image3_path_var, state='readonly').pack(pady=5)
        tk.Button(self.root, text="Browse", command=lambda: self.select_file(self.image3_path_var)).pack(pady=5)

        # Input fields for image display timelines
        tk.Label(self.root, text="Set timeline for second image (mm:ss:ms):").pack(pady=5)
        self.timeline2_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.timeline2_var).pack(pady=5)

        tk.Label(self.root, text="Set timeline for third image (mm:ss:ms):").pack(pady=5)
        self.timeline3_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.timeline3_var).pack(pady=5)

        # Submit button
        tk.Button(self.root, text="Submit", command=self.save_video_settings).pack(pady=5)

    def show_video_duration(self, duration):
        duration_label = tk.Label(self.root, text=f"Video Duration: {duration:.2f} seconds")
        duration_label.pack(pady=5)

    def select_file(self, path_var):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg;*.jpeg;*.png")])
        path_var.set(file_path)

    def select_video_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4;*.avi;*.mov")])
        self.video_path_var.set(file_path)

        if file_path:
            try:
                video_clip = VideoFileClip(file_path)
                video_duration = video_clip.duration
                video_clip.close()

                self.show_video_duration(video_duration)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load video: {str(e)}")

    def select_export_directory(self):
        # Open directory dialog to select an export directory
        directory = filedialog.askdirectory()
        if directory:
            self.export_dir_var.set(directory)

    def save_video_settings(self):

        # Assign video_path and export_dir from user input
        self.video_path = self.video_path_var.get()
        self.export_dir = self.export_dir_var.get()

        # Call the function to start processing videos
        self.prepare_videos_frame()

    def get_tables(self):
        cursor = self.connection.cursor()
        cursor.execute("SHOW TABLES")
        return [table[0] for table in cursor.fetchall()]

    def get_dynamic_data(self, table_name, root_domain, cursor):
        query = f"SELECT * FROM {table_name} WHERE root_domain = %s"
        cursor.execute(query, (root_domain,))
        result = cursor.fetchone()
        if result:
            # Assuming `cursor.description` contains the column names
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, result))
        return {}

    def format_description(self, template, data):
        def replace(match):
            key = match.group(1)
            return str(data.get(key, match.group(0)))

        import re
        description = re.sub(r'\{([^}]+)\}', replace, template)
        return description

# MediaCMS Video Uploading Logics are here

    def fetch_video_records(self):
        query = "SELECT root_domain, location, yt_video_description, yt_video_title FROM url_videos WHERE youtube_link IS NULL"
        cursor = self.connection.cursor()
        cursor.execute(query)
        return cursor.fetchall()  # Returns a list of tuples (location, yt_video_description)

    def upload_video_thread(self, semaphore, record, progress_queue):
        with semaphore:
            root_domain, location, description, title = record
            try:
                print("Uploading...")
                auth = (os.getenv("video_server_username"), os.getenv("video_server_password"))
                base_url = os.getenv("video_server_base_url")
                upload_url = f"{base_url}/api/v1/media"

                with open(location, 'rb') as media_file:
                    response = requests.post(
                        url=upload_url,
                        files={'media_file': media_file},
                        data={'title': title, 'description': description},
                        auth=auth
                    )

                if response.status_code == 201:
                    response_data = response.json()
                    live_url = response_data.get('url')

                    # Use the new function to extract the first frame of the video as a thumbnail
                    thumbnail_location = self.extract_thumbnail(location, root_domain)

                    self.update_youtube_link_in_db(root_domain, live_url, thumbnail_location)
                    # Consider uncommenting the next line to remove the video file after successful upload
                    os.remove(location)
                else:
                    print(f"Error during upload. Status code: {response.status_code}, Details: {response.text}")

            except Exception as e:
                print(f"Failed to upload {title}. Error: {str(e)}")

            finally:
                progress_queue.put(None)  # Signal completion

    def process_and_upload_videos(self):
        self.connection.close()
        self.connection = mysql.connector.connect(host=self.host, user=self.user, password=self.password,
                                                  database=self.database)

        # Now fetch the video records with the refreshed connection
        records = self.fetch_video_records()

        if not records:
            messagebox.showinfo("Info", "No videos to upload.")
            return

        if not messagebox.askyesno("Confirmation", f"{len(records)} videos will be uploaded. Do you wish to continue?"):
            print("Upload canceled.")
            return

        self.progress_bar = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.progress_bar.pack(pady=20)
        self.completed_threads = 0
        semaphore = Semaphore(4)
        progress_queue = queue.Queue()

        def update_progress():
            while not progress_queue.empty():
                progress_queue.get()
                self.completed_threads += 1
                self.progress_bar['value'] = 100 * self.completed_threads / len(records)

            if self.completed_threads == len(records):
                self.progress_bar.pack_forget()  # Remove progress bar
                messagebox.showinfo("Success", "All videos uploaded successfully.")
                self.on_all_threads_complete()
            else:
                self.root.after(100, update_progress)  # Schedule the next check

        threads = [Thread(target=self.upload_video_thread, args=(semaphore, record, progress_queue)) for record in records]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        update_progress()

    def extract_thumbnail(self, video_path, root_domain):
        # Open the video file
        cap = cv2.VideoCapture(video_path)
        success, image = cap.read()
        cap.release()

        if success:
            # Ensure 'thumbnails' directory exists
            os.makedirs('thumbnails', exist_ok=True)
            thumbnail_filename = f"thumbnails/{root_domain}.jpg"

            # Save the first frame as a JPEG file
            cv2.imwrite(thumbnail_filename, image)

            return thumbnail_filename

        return None  # Return None if unable to extract the thumbnail

    def update_youtube_link_in_db(self, root_domain, youtube_link, thumbnail_location):
        cursor = self.connection.cursor()
        try:
            update_query = "UPDATE url_videos SET youtube_link = %s, thumbnail_location = %s WHERE root_domain = %s"
            cursor.execute(update_query, (youtube_link, thumbnail_location, root_domain))
            self.connection.commit()
        except Exception as e:
            print(f"Error updating database: {e}")
        finally:
            cursor.close()


#Generate Wp Pages Logic are here

    def open_wp_page_generate_frame(self):
        # New window (or frame) for video preparation settings
        self.clear_all_widgets()
        # Dropdown for table selection
        tk.Label(self.root, text="Select a table:").pack(pady=5)
        self.table_var = tk.StringVar()
        tables = self.get_tables()
        table_dropdown = tk.OptionMenu(self.root, self.table_var, *tables)
        table_dropdown.pack(pady=5)

        # Submit button
        tk.Button(self.root, text="Submit", command=self.generate_wp_pages).pack(pady=5)

    def generate_wp_pages(self):
        selected_table = self.table_var.get()
        query = "SELECT root_domain, youtube_link FROM url_videos WHERE wp_link IS NULL"
        cursor = self.connection.cursor()
        cursor.execute(query)
        records = cursor.fetchall()

        if not records:
            messagebox.showinfo("No Records", "There are no records to upload.")
            return

        if not messagebox.askyesno("Confirmation",
                                   f"{len(records)} records will be uploaded. Do you wish to continue?"):
            messagebox.showinfo("Cancelled", "Operation cancelled by the user.")
            return

        # Create a Semaphore with a maximum of 4 threads
        semaphore = Semaphore(4)
        threads = []

        for record in records:
            thread = threading.Thread(target=self.threaded_record_processing, args=(record, selected_table, semaphore))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        cursor.close()
        messagebox.showinfo("Success", "All records have been successfully uploaded.")

    def create_new_connection(self):
        try:
            return mysql.connector.connect(host=self.host, database=self.database,
                                           user=self.user, password=self.password)
        except Error as e:
            print(f"Error while connecting to MySQL: {e}")
            return None

    def threaded_record_processing(self, record, selected_table, semaphore):
        with semaphore:
            try:
                # Establish a new connection for each thread
                connection = self.create_new_connection()  # Replace with your connection method
                cursor = connection.cursor()

                root_domain, youtube_link = record
                additional_query = f"SELECT * FROM {selected_table} WHERE root_domain = %s"
                cursor.execute(additional_query, (root_domain,))
                additional_data_tuple = cursor.fetchone()
                additional_data_columns = [column[0] for column in cursor.description]
                additional_data = dict(zip(additional_data_columns, additional_data_tuple))

                modified_html_content = self.modify_html(additional_data, youtube_link)
                wp_page_link = self.create_wp_page(modified_html_content)

                if wp_page_link:
                    update_query = "UPDATE url_videos SET wp_link = %s WHERE root_domain = %s"
                    cursor.execute(update_query, (wp_page_link, root_domain))
                    connection.commit()

                cursor.close()
                connection.close()
            except Exception as e:
                print(f"Error processing record {record}: {e}")

    def modify_html(self, data, youtube_link):
        # Load your HTML file
        with open("wp_template.html", "r") as file:
            html_content = file.read()

        # Replace placeholders in the HTML file with data from the selected table
        for key, value in data.items():
            placeholder = "{" + key + "}"  # Adjusted placeholder format
            html_content = html_content.replace(placeholder, str(value))

        # Additionally replace the {youtube_link} placeholder
        html_content = html_content.replace("{youtube_link}", youtube_link)

        return html_content

    def create_wp_page(self, youtube_link):
        # Load WP REST API credentials from .env file
        print('Gerenrating page in  Wordpress...')
        wp_url = os.getenv("wp_site_url")
        wp_user = os.getenv("wp_site_username")
        wp_password = os.getenv("wp_site_application_password")

        # Prepare request for WP REST API
        headers = {'Content-Type': 'application/json'}
        auth = HTTPBasicAuth(wp_user, wp_password)
        data = {"title": "test-title", "content": youtube_link, "status": "publish"}

        # Send request to WP REST API
        response = requests.post(f"{wp_url}/wp-json/wp/v2/pages", headers=headers, auth=auth, json=data)

        if response.status_code == 201:
            return response.json().get("link")
        else:
            print(f"Failed to create WP page for {youtube_link}: {response.status_code}")
            return None

# Global Functions are here

    def clear_all_widgets(self):

        for widget in root.winfo_children():
            widget.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = DatabaseApp(root)
    root.mainloop()


 # def create_scrollable_frame(self):
    #     canvas = Canvas(self.root)
    #     scrollbar = Scrollbar(self.root, orient="vertical", command=canvas.yview)
    #     self.scrollable_frame = Frame(canvas)
    #
    #     self.scrollable_frame.bind(
    #         "<Configure>",
    #         lambda e: canvas.configure(
    #             scrollregion=canvas.bbox("all")
    #         )
    #     )
    #     canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
    #     canvas.configure(yscrollcommand=scrollbar.set)
    #
    #     canvas.pack(side="left", fill="both", expand=True)
    #     scrollbar.pack(side="right", fill="y")