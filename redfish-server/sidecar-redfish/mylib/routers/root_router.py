from flask_restx import Namespace, Resource, fields

root_ns = Namespace('', description='Redfish')

@root_ns.route("")
class Redfish(Resource):
    def get(self):
        root = {
            "@odata.id": "/redfish",
            "@odata.type": "#RedfishVersionCollection.RedfishVersionCollection",
            "Name": "Redfish Service Versions",
            "Members@odata.count": 1,
            "Members": [
                { "@odata.id": "/redfish/v1" }
            ]
        }
        return root, 200