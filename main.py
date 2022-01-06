from os import stat
from google.cloud import datastore
from flask import Flask, request, jsonify
from google.cloud.datastore import query
from google.auth import transport
from google.oauth2 import id_token
import json
import string
import random
import requests


import constants,boat,load,errors

app = Flask(__name__)
app.register_blueprint(boat.bp)
app.register_blueprint(load.bp)
client = datastore.Client()


CLIENT_ID = ""
CLIENT_SECRET = ""
SCOPE = "https://www.googleapis.com/auth/userinfo.profile"
# "http://127.0.0.1:8080/oauth""https://portfolio-334206.uw.r.appspot.com/oauth"
RED_URI = "https://portfolio-334206.uw.r.appspot.com/oauth"
CERT_URL = 'https://www.googleapis.com/oauth2/v1/certs'
DEF_URL = "https://portfolio-334206.uw.r.appspot.com/"

@app.errorhandler(errors.SomeError)
def Some_Error(error):
    res = jsonify(error.to_dict())
    res.status_code = error.status_code
    return res

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'Error': '405 Method Not Allowed'}), 405

@app.route('/')
def index():
    rand_state = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

    new_state = datastore.entity.Entity(key=(client.key("states")))
    new_state.update({"state": rand_state})
    #client.put(new_state)

    auth_link = "https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id="+CLIENT_ID+"&redirect_uri="+RED_URI+"&scope="+SCOPE#+"&state="+rand_state

    return """
    <body>
    <hl>Welcome!</hl>
    <p><a href="""+auth_link+""">Click Here To Authenticate</a></p>
    </body>
    """

@app.route('/oauth', methods=['GET'])
def oauth_index():
    if request.method == "GET":

        #client_state = request.args.get('state')
        #query = client.query(kind="states")

        #state_fetch = list(query.fetch())
        #for s in state_fetch:
        #    if(s['state'] == client_state):
                g_auth_token = request.args.get('code')
                posturl = "https://oauth2.googleapis.com/token?code="+g_auth_token+"&client_id="+CLIENT_ID+"&client_secret="+CLIENT_SECRET+"&redirect_uri="+RED_URI+"&grant_type=authorization_code"
                access_info = requests.post(posturl).json()

                headers = {'Authorization': 'Bearer '+access_info['access_token'], }
                info_url = "https://people.googleapis.com/v1/people/me?personFields=names"
                g_info = requests.get(info_url,headers=headers).json()

                userName = g_info['names'][0]['unstructuredName']

                oauth_token = id_token.verify_oauth2_token(access_info['id_token'],request=transport.requests.Request(),audience=None)

                userQuery = client.query(kind=constants.users)
                userQuery.add_filter("oauth_id","=",oauth_token['sub'])
                queryRes = userQuery.fetch()
                
                for r in queryRes:
                    if(r['oauth_id'] == oauth_token['sub']):
                       ret_msg = "Welcome, " + userName  + "! Thank you for authenticating. Please navigate to /boats to use the API.<br><br>Your JWT is:<br>"+access_info['id_token'] + "<br><br>Your id is: "+ str(oauth_token['sub'])
                       return ret_msg
                else:
                    new_user = datastore.entity.Entity(key=client.key(constants.users))
                    new_user.update({"name": userName,"oauth_id": oauth_token['sub'],"owned_boats": None})
                    client.put(new_user)

                    #g_info['names'][0]['givenName']+" "+g_info['names'][0]['familyName']
                    ret_msg = "Welcome, " + userName  + "! Thank you for authenticating. Please navigate to /boats to use the API.<br><br>Your JWT is:<br>"+access_info['id_token'] + "<br><br>Your id is: "+ str(oauth_token['sub'])
                    return ret_msg
        #return "Invalid State, "+ client_state
    else:
         raise errors.SomeError(errors.err405, status_code=405)

@app.route('/users', methods=['GET'])
def user_get():
    if request.method == 'GET':
        if('application/json' in request.accept_mimetypes):
            query = client.query(kind=constants.users)
            res = list(query.fetch())

            return(json.dumps(res),200)
        else:
            raise errors.SomeError(errors.err406, status_code=406)
    else:
        raise errors.SomeError(errors.err405, status_code=405)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)