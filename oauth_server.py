from flask import Flask, request, redirect
import requests

app = Flask(__name__)

CLIENT_ID = "Mzh3dcCXZ519YzXls40ULCqKpRvxtP_qB39XwgdC1uSgTeanPDtakEXqlwx5NvCo"
CLIENT_SECRET = "QzWp9M1rWAagl4FYtLHWlnDOdq93gzN_Yua8QAWI239kaMXgXsRrWi7A33iMkky"
REDIRECT_URI = "http://localhost/callback"
TOKEN_URL = "https://www.patreon.com/api/oauth2/token"

@app.route('/callback')
def patreon_callback():
    code = request.args.get('code')  # Get the authorization code from the URL
    if code:
        # Exchange the code for an access token
        data = {
            'code': code,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code'
        }

        response = requests.post(TOKEN_URL, data=data)
        access_token = response.json()['access_token']

        # Now you can use this access token to get Patreon user data
        return f"Access Token: {access_token}"

    return "Error: No code provided."

if __name__ == '__main__':
    app.run(debug=True)
