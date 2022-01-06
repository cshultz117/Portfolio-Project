from os import stat
from datetime import date
from google.cloud import datastore
from flask import Flask, request, jsonify, Blueprint
import json

from google.auth import transport
from google.oauth2 import id_token
from google.cloud.datastore import query
from pyasn1.type.univ import Null
from werkzeug.exceptions import InternalServerError

from werkzeug.wrappers import response
import constants
import errors

client = datastore.Client()
bp = Blueprint("load", __name__, url_prefix='/loads')


@bp.errorhandler(errors.SomeError)
def Some_Error(error):
    res = jsonify(error.to_dict())
    res.status_code = error.status_code
    return res

@bp.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'Error': '405 Method Not Allowed'}), 405

@bp.route('', methods=['POST','GET'])
def loads_get_post():
    if request.method == 'POST':
        if('application/json' in request.accept_mimetypes):
            content = request.get_json()
            cur_date = date.today()
            date_str = cur_date.strftime("%m/%d/%Y")

            try:
                if(not(content["volume"] and content["content"])):
                    raise errors.SomeError(errors.err400, status_code=400);
            except KeyError:
                raise errors.SomeError(errors.err400, status_code=400);

            new_load = datastore.entity.Entity(key=client.key(constants.loads))
            new_load.update({"volume": content["volume"]});
            new_load.update({"content": content["content"]});
            client.put(new_load)

            new_load.update({"id": new_load.key.id,"carrier": None,"creation_date": date_str})
            client.put(new_load)

            new_load.update({"self": request.url+'/'+str(new_load.key.id)})

            return (new_load,201)
        else:
            raise errors.SomeError(errors.err406, status_code=406)
    elif request.method == 'GET':
        if('application/json' in request.accept_mimetypes):
            query = client.query(kind=constants.loads)
            q_limit = int(request.args.get('limit', '5'))
            q_offset = int(request.args.get('offset', '0'))
            g_iterator = query.fetch(limit=q_limit, offset=q_offset)
            pages = g_iterator.pages
            res = list(next(pages))

            if g_iterator.next_page_token:
                next_offset = q_offset + q_limit
                next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
            else:
                next_url = None

            for e in res:
                e["id"] = e.key.id
                e["self"] = request.url+'/'+str(e.key.id)
            output = {"loads": res}
            if next_url:
                output["next"] = next_url
            return (json.dumps(output),200)
        else:
            raise errors.SomeError(errors.err406, status_code=406)
    else:
        raise errors.SomeError(errors.err405, status_code=405)

@bp.route('/<id>', methods=['DELETE','GET','PATCH'])
def loads_get_delete(id):
    if request.method == "DELETE":
        load_key = client.key(constants.loads, int(id))
        load = client.get(key=load_key)

        if (load == None):
            raise errors.SomeError(errors.err404, status_code=404)

        if(load['carrier'] != None):
            boat_key = client.key(constants.boats, int(load['carrier']))
            boat = client.get(key=boat_key);


            if (boat != None):
                try:
                    bearer = request.headers['Authorization']
                    id_tok = bearer.split(' ')[1]

                    oauth_token = id_token.verify_oauth2_token(id_tok,request=transport.requests.Request(),audience=None)
                    if(boat['owner'] == oauth_token['sub']):
                        boat['loads'].remove(int(id))
                        client.put(boat)
                    else:
                        raise errors.SomeError(errors.err401_2, status_code=401)

                except(ValueError,KeyError):
                    raise errors.SomeError(errors.err401,status_code=401)

        client.delete(load_key)
        return ('',204)
    elif request.method == "GET":
        if('application/json' in request.accept_mimetypes):
            load_key = client.key(constants.loads, int(id))
            load = client.get(key=load_key)

            if (load == None):
                raise errors.SomeError(errors.err404, status_code=404)

            load.update({'self': request.url})
            return (load,200)
        else:
            raise errors.SomeError(errors.err406, status_code=406)
    elif request.method == "PATCH":
        if('application/json' in request.accept_mimetypes):
            content = request.get_json()
            load_key = client.key(constants.loads, int(id))
            load = client.get(key=load_key)

            if (load == None):
                raise errors.SomeError(errors.err404, status_code=404)

            if(load['carrier']):
                boat_key = client.key(constants.boats, int(load['carrier']))
                boat = client.get(key=boat_key);

                if(boat == None):
                    for p in content:
                        if((load[p] != content[p]) and (p in constants.loads_editable)):
                            load.update({p:content[p]})
                            client.put(load)
                elif(boat != None):
                    try:
                        bearer = request.headers['Authorization']
                        id_tok = bearer.split(' ')[1]

                        oauth_token = id_token.verify_oauth2_token(id_tok,request=transport.requests.Request(),audience=None)
                        if(boat['owner'] == oauth_token['sub']):
                            for p in content:
                                if((load[p] != content[p]) and (p in constants.loads_editable)):
                                    load.update({p:content[p]})
                                    client.put(load)
                        else:
                            raise errors.SomeError(errors.err401_2, status_code=401)
                    except(ValueError,KeyError):
                        raise errors.SomeError(errors.err401,status_code=401)
            else:
                for p in content:
                    if((load[p] != content[p]) and (p in constants.loads_editable)):
                        load.update({p:content[p]})
                        client.put(load)

            load.update({'self': request.url})
            return(load,200)
        else:
            raise errors.SomeError(errors.err406, status_code=406)
    else:
        raise errors.SomeError(errors.err405, status_code=405)