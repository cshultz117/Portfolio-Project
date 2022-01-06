from flask.json import jsonify


err404 = "The resource you are looking for does not exist"
err400 = "The request object is missing at least one of the required attributes"
err401 = "Invalid or missing JWT"
err403 = "The load is already assigned to a boat"
err401_2 = "You either do not own that boat, or it is private"
err404_2 = "That load is not on this boat"
err405 = "Method Not Allowed"
err406 = "MIME type requested not supported"

class SomeError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["Error"] = self.message
        return rv