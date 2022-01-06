from os import stat
from google.cloud import datastore
from flask import Flask, request, jsonify, Blueprint
import json

from google.auth import transport
from google.oauth2 import id_token
import requests
import string
from google.cloud.datastore import query
from pyasn1.type.univ import Null
from werkzeug.exceptions import InternalServerError
from json2html import *

from werkzeug.wrappers import response
import constants
import errors

client = datastore.Client()
bp = Blueprint("boat", __name__, url_prefix='/boats')


@bp.errorhandler(errors.SomeError)
def Some_Error(error):
    res = jsonify(error.to_dict())
    res.status_code = error.status_code
    return res

@bp.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'Error': '405 Method Not Allowed'}), 405

@bp.route('', methods=['POST','GET'])
def boats_get_post():
    if request.method == 'POST':
        if('application/json' in request.accept_mimetypes):
            try:    
                    bearer = request.headers['Authorization']
                    id_tok = bearer.split(' ')[1]

                    oauth_token = id_token.verify_oauth2_token(id_tok,request=transport.requests.Request(),audience=None)
                    content = request.get_json()

                    try:
                        if(not(content["name"] and content["type"] and content["length"])):
                            raise errors.SomeError(errors.err400, status_code=400);
                    except KeyError:
                        raise errors.SomeError(errors.err400, status_code=400);

                    new_boat = datastore.entity.Entity(key=client.key(constants.boats))
                    new_boat.update({"name": content["name"], "type": content["type"], "length": content["length"],"public": content["public"], "owner": oauth_token["sub"]});
                    client.put(new_boat)

                    new_boat.update({"id": new_boat.key.id})
                    client.put(new_boat)

                    userQuery = client.query(kind=constants.users)
                    userQuery.add_filter("oauth_id","=",oauth_token['sub'])
                    queryRes = userQuery.fetch()
            
                    for r in queryRes:
                        if(r['oauth_id'] == oauth_token['sub']):
                            user = client.get(key=r.key)
                            if(user['owned_boats'] == None):
                                user['owned_boats'] = [new_boat.key.id]
                                client.put(user)
                            else:
                                user['owned_boats'].append(new_boat.key.id)
                                client.put(user)
            
                    new_boat.update({"self": request.url+'/'+str(new_boat.key.id)})

                    return (new_boat,201);
            except (ValueError,KeyError):
                raise errors.SomeError(errors.err401,status_code=401)
        else:
            raise errors.SomeError(errors.err406, status_code=406)
    elif request.method == 'GET':
        if('application/json' in request.accept_mimetypes):
            try:
                bearer = request.headers['Authorization']
                id_tok = bearer.split(' ')[1]

                oauth_token = id_token.verify_oauth2_token(id_tok,request=transport.requests.Request(),audience=None)

                query = client.query(kind=constants.boats)
                query.add_filter("owner","=",oauth_token['sub'])
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

                output = {"boats": res}

                if next_url:
                    output["next"] = next_url
                return (json.dumps(output),200)
            except:
                query = client.query(kind=constants.boats)
                query.add_filter("public","=",True)

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

                output = {"public boats": res}

                if next_url:
                    output["next"] = next_url
                return (json.dumps(output),200)
        else:
            raise errors.SomeError(errors.err406, status_code=406)
    else:
        raise errors.SomeError(errors.err405, status_code=405)

@bp.route('/<id>', methods=['DELETE','GET','PATCH'])
def boats_id_get_delete_patch(id):
    if request.method == "GET":
        if('application/json' in request.accept_mimetypes):
            boat_key = client.key(constants.boats, int(id))
            boat = client.get(key=boat_key)

            if (boat == None):
                raise errors.SomeError(errors.err404, status_code=404)

            if (boat['public'] == True):
                boat.update({"self": request.url})
                return (boat,200)
            else:
                try:
                    bearer = request.headers['Authorization']
                    id_tok = bearer.split(' ')[1]

                    oauth_token = id_token.verify_oauth2_token(id_tok,request=transport.requests.Request(),audience=None)

                    if (boat['owner'] == oauth_token['sub']):
                        boat.update({"self": request.url})
                        return (boat,200)
                    else:
                        raise errors.SomeError(errors.err401_2, status_code=401)
                except(ValueError,KeyError):
                    raise errors.SomeError(errors.err401,status_code=401)
        else:
            raise errors.SomeError(errors.err406, status_code=406)
    elif request.method == "DELETE":
        if('application/json' in request.accept_mimetypes):
            boat_key = client.key(constants.boats, int(id))
            boat = client.get(key=boat_key)

            if (boat == None):
                raise errors.SomeError(errors.err404, status_code=404)

            try:
                bearer = request.headers['Authorization']
                id_tok = bearer.split(' ')[1]

                oauth_token = id_token.verify_oauth2_token(id_tok,request=transport.requests.Request(),audience=None)

                if(boat['owner'] == oauth_token['sub']):
                    if('loads' in boat.keys()):
                        for load_id in boat['loads']:
                            load_key = client.key(constants.loads, int(load_id))
                            load = client.get(key=load_key)
                            load.update({'carrier': None})
                            client.put(load)
                
                    userQuery = client.query(kind=constants.users)
                    userQuery.add_filter("oauth_id","=",oauth_token['sub'])
                    queryRes = userQuery.fetch()

                    for r in queryRes:
                        if(r['oauth_id'] == oauth_token['sub']):
                            user = client.get(key=r.key)
                            user['owned_boats'].remove(int(id))
                            client.put(user)
                    client.delete(boat_key)
                    return ('',204)
                else:
                    raise errors.SomeError(errors.err401_2, status_code=401)
            except(ValueError,KeyError):
                    raise errors.SomeError(errors.err401,status_code=401)
        else:
            raise errors.SomeError(errors.err406, status_code=406)
    elif request.method == 'PATCH':
        if('application/json' in request.accept_mimetypes):
            content = request.get_json()
            boat_key = client.key(constants.boats, int(id))
            boat = client.get(key=boat_key)

            if (boat == None):
                raise errors.SomeError(errors.err404, status_code=404)
            try:
                bearer = request.headers['Authorization']
                id_tok = bearer.split(' ')[1]

                oauth_token = id_token.verify_oauth2_token(id_tok,request=transport.requests.Request(),audience=None)

                if(boat['owner'] == oauth_token['sub']):
                    for p in content:
                        if((boat[p] != content[p]) and (p in constants.boats_editable)):
                            boat.update({p: content[p]})
                            client.put(boat)
                else:
                    raise errors.SomeError(errors.err401_2, status_code=401)

                boat.update({'self':request.url})
                return (boat,200)
            except(ValueError,KeyError):
                    raise errors.SomeError(errors.err401,status_code=401)
        else:
            raise errors.SomeError(errors.err406, status_code=406)
    else:
        raise errors.SomeError(errors.err405, status_code=405)

@bp.route('/<b_id>/loads/<l_id>', methods=['PUT','DELETE'])
def boats_loads_put_delete(b_id,l_id):
    if request.method == "PUT":
        if('application/json' in request.accept_mimetypes):
            boat_key = client.key(constants.boats, int(b_id))
            boat = client.get(key=boat_key)

            load_key = client.key(constants.loads, int(l_id))
            load = client.get(key=load_key)


            if (boat == None or load == None):
                raise errors.SomeError(errors.err404, status_code=404);

            try:
                bearer = request.headers['Authorization']
                id_tok = bearer.split(' ')[1]

                oauth_token = id_token.verify_oauth2_token(id_tok,request=transport.requests.Request(),audience=None)

                if (load["carrier"] != None):
                    raise errors.SomeError(errors.err403, status_code=403)

                if(boat['owner'] == oauth_token['sub']):
                    load.update({"carrier": boat.id})
                    if 'loads' in boat.keys():
                        boat['loads'].append(load.id)
                    else:
                        boat['loads'] = [load.id]

                    client.put(boat)
                    client.put(load)

                    return ('', 204)
                else:
                    raise errors.SomeError(errors.err401_2, status_code=401)
            except(ValueError,KeyError):
                    raise errors.SomeError(errors.err401,status_code=401)
        else:
            raise errors.SomeError(errors.err406, status_code=406)
    elif request.method == "DELETE":
        if('application/json' in request.accept_mimetypes):
            boat_key = client.key(constants.boats, int(b_id))
            boat = client.get(key=boat_key)

            load_key = client.key(constants.loads, int(l_id))
            load = client.get(key=load_key)

            if (boat == None or load == None):
                raise errors.SomeError(errors.err404, status_code=404);

            try:
                bearer = request.headers['Authorization']
                id_tok = bearer.split(' ')[1]

                oauth_token = id_token.verify_oauth2_token(id_tok,request=transport.requests.Request(),audience=None)

                if(not(load.id in boat['loads'])):
                    raise errors.SomeError(errors.err404_2, status_code=404)
                if(boat['owner'] == oauth_token['sub']):
                    if 'loads' in boat.keys():
                        boat['loads'].remove(int(l_id))
                        client.put(boat)

                    if 'carrier' in load.keys():
                        load.update({'carrier': None})
                        client.put(load)
                    return ('',204)
                else:
                    raise errors.SomeError(errors.err401_2, status_code=401)
            except(ValueError,KeyError):
                    raise errors.SomeError(errors.err401,status_code=401)
        else:
            raise errors.SomeError(errors.err406, status_code=406)
    else:
        raise errors.SomeError(errors.err405, status_code=405)