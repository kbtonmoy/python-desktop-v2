import requests

url = "http://64.176.199.218:4000/api/screenshot?resX=1920&resY=1080&outFormat=png&waitTime=100&isFullPage=false&dismissModals=true&url=http://onelittleweb.com"
output_file = "screenshot.jpg"

try:
    response = requests.get(url)
    if response.status_code == 200:
        with open(output_file, "wb") as file:
            file.write(response.content)
        print(f"Image saved as {output_file}")
    else:
        print(f"Failed to fetch the image. Status code: {response.status_code}")
except Exception as e:
    print(f"An error occurred: {str(e)}")
