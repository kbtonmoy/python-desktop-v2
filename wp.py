import requests
import json

# The URL for the API endpoint
url = 'https://gymnearx.com/blog/wp-json/wp/v2/posts'

# Your WordPress username
username = 'admin@onelittleweb.com'

# The application password you generated
password = "UVmX Sb70 yl5V sikD 0khs LAHc"

# The post data
data = {
    'title': 'My New Post',
    'content': 'This is the content of my new post.',
    'status': 'publish'  # Use 'draft' to save the post as a draft
}

# Send the HTTP request
response = requests.post(url, auth=(username, password), json=data)

# Check the response
if response.status_code == 201:
    print('Post created successfully')
else:
    print('Failed to create post: ' + response.text)