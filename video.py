import httplib2
import os
import sys
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow
import random
import time
import tkinter as tk
from tkinter import simpledialog, messagebox

httplib2.RETRIES = 1


MAX_RETRIES = 10


RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)

RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

CLIENT_SECRETS_FILE = "keys/client_secret.json"

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0

To make this sample run you will need to populate the client_secrets.json file
found at:

   %s

with information from the API Console
https://console.cloud.google.com/

For more information about the client_secrets.json file format, please visit:
https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
""" % os.path.abspath(os.path.join(os.path.dirname(__file__),
                                   CLIENT_SECRETS_FILE))

VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")


def get_verification_code(auth_uri):
    """Function to display a Tkinter dialog for copying the auth URL and inputting the verification code."""
    root = tk.Tk()
    root.title("Authentication Required")

    # Create a read-only text widget with the URL
    text = tk.Text(root, height=4, width=80)
    text.insert(tk.END, auth_uri)
    text.config(state=tk.DISABLED, wrap=tk.WORD)
    text.pack(padx=10, pady=10)

    # Entry field for verification code
    verification_code_entry = tk.Entry(root)
    verification_code_entry.pack(pady=5)

    # Variable to store the verification code
    code = None

    def on_submit():
        nonlocal code
        code = verification_code_entry.get()
        root.quit()  # Stop the mainloop but don't destroy the window yet

    # Button to submit the verification code
    submit_button = tk.Button(root, text="Submit Verification Code", command=on_submit)
    submit_button.pack(pady=5)

    root.mainloop()
    root.destroy()  # Destroy the window after exiting mainloop
    return code

def get_authenticated_service(args):
    flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE,
                                   scope=YOUTUBE_UPLOAD_SCOPE,
                                   message=MISSING_CLIENT_SECRETS_MESSAGE,
                                   redirect_uri='urn:ietf:wg:oauth:2.0:oob')

    storage = Storage("%s-oauth2.json" % sys.argv[0])
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        auth_uri = flow.step1_get_authorize_url()
        code = get_verification_code(auth_uri)
        if code:
            credentials = flow.step2_exchange(code)
            storage.put(credentials)
        else:
            print("Authentication was cancelled.")
            sys.exit(1)

    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                 http=credentials.authorize(httplib2.Http()))


def initialize_upload(youtube, options):
    tags = None
    if options.keywords:
        tags = options.keywords.split(",")

    body = dict(
        snippet=dict(
            title=options.title,
            description=options.description,
            tags=tags,
            categoryId=options.category
        ),
        status=dict(
            privacyStatus=options.privacyStatus
        )
    )

    # Call the API's videos.insert method to create and upload the video.
    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(options.file, chunksize=-1, resumable=True)
    )

    resumable_upload(insert_request)


def resumable_upload(insert_request):
    response = None
    error = None
    retry = 0
    while response is None:
        try:
            print("Uploading file...")
            status, response = insert_request.next_chunk()
            if response is not None:
                if 'id' in response:
                    print("Video id '%s' was successfully uploaded." %
                          response['id'])
                    return response['id']
                else:
                    exit("The upload failed with an unexpected response: %s" % response)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = "A retriable HTTP error %d occurred:\n%s" % (e.resp.status, e.content)
            else:
                messagebox.showerror("HTTP Error", f"An HTTP error occurred:\n{e.content}")
                raise
        except RETRIABLE_EXCEPTIONS as e:
            messagebox.showerror("Error", f"A retriable error occurred: {e}")
            error = f"A retriable error occurred: {e}"

        if error is not None:
            print(error)
            retry += 1
            if retry > MAX_RETRIES:
                exit("No longer attempting to retry.")

            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            print("Sleeping %f seconds and then retrying..." % sleep_seconds)
            time.sleep(sleep_seconds)

def upload_yt_video(file, title, description, category, keywords, privacyStatus):
    class Options:
        def __init__(self, file, title, description, category, keywords, privacyStatus):
            self.file = file
            self.title = title
            self.description = description
            self.category = category
            self.keywords = keywords
            self.privacyStatus = privacyStatus
            self.logging_level = "ERROR"  # Add a default logging level
            self.noauth_local_webserver = True

    options = Options(file, title, description, category, keywords, privacyStatus)

    try:
        youtube = get_authenticated_service(options)
        video_id = initialize_upload(youtube, options)
        messagebox.showerror('error',video_id)
        return video_id  # Return the video ID
    except HttpError as e:
        error_message = f"An HTTP error {e.resp.status} occurred:\n{e.content}"
        messagebox.showerror("Upload Error", error_message)
        print(error_message)
    except Exception as e:
        messagebox.showerror("Error", str(e))
        print(f"Error: {str(e)}")



if __name__ == '__main__':
    # The code here will only execute if the script is run directly
    args = argparser.parse_args()
    if not os.path.exists(args.file):
        exit("Please specify a valid file using the --file= parameter.")

    youtube = get_authenticated_service(args)
    try:
        initialize_upload(youtube, args)
    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred:\n{e.content}")
