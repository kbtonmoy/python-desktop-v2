import requests

auth = ('michael' ,'uAmPg8uQiGDGnm8ntJy')
upload_url = "https://server.inventoryboss.video/api/v1/media"
title = 'x title'
description = 'x description'
media_file = 'videos/bolt.com.mp4'

# Performing the POST request
response = requests.post(
    url=upload_url,
    files={'media_file': open(media_file, 'rb')},
    data={'title': title, 'description': description},
    auth=auth
)

# Ensure the request was successful
if response.status_code == 201:
    # Extracting the URL from the response
    response_data = response.json()
    live_url = response_data.get('thumbnail_url')
    print("thumb:", live_url)
else:
    print("Error during upload. Status code:", response.status_code)