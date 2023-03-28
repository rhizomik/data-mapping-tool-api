import cgi
import datetime
import os
from urllib.parse import urlparse, unquote

from owlready2 import default_world
import owlready2 as owl
from py4j.java_gateway import launch_gateway, JavaGateway
from urllib.request import urlopen, urlretrieve

import requests
import tempfile
from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from owlready2 import rdfs_subclassof, Or, ThingClass

from database import mongo
from models.ontology import OntologyModel, VisibilityEnum
from models.prefix import PrefixModel
from utils.prefix import create_or_return_prefix
from utils.utils import get_user_by_username, parse_json, remove_file, get_file, define_ontology

ontology_router = Blueprint('ontology', __name__)


@ontology_router.route("/<id>/classes", methods=["GET"])
@jwt_required()
def get_classes(id):
    ontology = define_ontology(id)
    return jsonify(data=[{"label": str(i), "value": str(i)} for i in list(ontology.classes())])


@ontology_router.route("/<id>/relations", methods=["GET"])
@jwt_required()
def get_classes_relations(id):
    ontology = define_ontology(id)
    relations = [{"class": str(i), "relations": list(i._get_class_possible_relations()).__str__()[1:-1].split(',')} for
                 i in list(ontology.classes())]
    return jsonify(data=relations)


@ontology_router.route("/<id>/properties/<property_type>", methods=["GET"])
@jwt_required()
def get_object_properties(id, property_type):
    ontology = define_ontology(id)
    properties = []

    if property_type == 'data':
        properties = list(ontology.data_properties())

    if property_type == 'object':
        properties = list(ontology.object_properties())

    if property_type == 'annotation':
        properties = list(ontology.annotation_properties())

    if property_type == 'all':
        properties = list(ontology.properties())

    if 'classes' in request.args:
        classes = request.args['classes'].split(',')
        domains = set(classes)
        for stmt in ontology.get_triples(s=None, p=rdfs_subclassof, o=None):
            if str(ontology._get_by_storid(stmt.__getitem__(0))) in classes:
                domains.add(str(ontology._get_by_storid(stmt.__getitem__(2))))
        properties = [prop for prop in properties if applicable_domain(prop, domains)]

    return jsonify(
        data=[
            {"name": i.name,
             "value": str(i.domain)[1:-1] + ':' + i.name,
             "range": str(i.range)[1:-1],
             "domain": str(i.domain)[1:-1]} for i in properties])


def applicable_domain(prop, domains):
    if len(prop.domain) > 0:
        if isinstance(prop.domain[0], Or):
            coincidences = [cls for cls in prop.domain[0].Classes if str(cls) in domains]
            return len(coincidences) > 0
        elif isinstance(prop.domain[0], ThingClass):
            return str(prop.domain[0]) in domains
    return True


@ontology_router.route("/<id>/classes/relations", methods=["POST"])
@jwt_required()
def get_relations(id):
    req = request.json
    relations = {}
    ontology = define_ontology(id)

    if ontology is False:
        return jsonify(successful=False), 500

    for i in ontology.object_properties():
        if i.domain and i.range:
            if str(i.domain[0]) in req['classes'] and str(i.range[0]) in req['classes']:
                rel = {"from": str(i.domain[0]), "to": str(i.range[0]), "relation": str(i)}
                relations.update({str(i): rel})

    return jsonify(successful=True, relations=relations)


@ontology_router.route("/<id>/view", methods=["GET"])
def get_ontology_view(id):
    ontology = define_ontology(id)
    classes = [{'id': str(_class), 'data': {'label': str(_class)}, 'position': {'x': 0, 'y': 0}} for _class in
               ontology.classes()]

    relations = [
        {"source": str(i.domain[0]), "target": str(i.range[0]), "id": str(i), "label": str(i), 'type': 'smooth',
         'style': {'stroke': 'black'}, 'arrowHeadType': 'arrowclosed', 'animated': True} for i in
        ontology.object_properties()]

    return jsonify(classes=classes, relations=relations)


def _create_ontology_from_file(file, filename, identity, ontology_name, prefix = None):

    file_id = mongo.save_file(filename=filename, fileobj=file, kwargs={"owner": identity})

    ontology_model = OntologyModel(filename=filename, file_id=str(file_id), ontology_name=ontology_name,
                                   createdBy=identity, createdAt=datetime.datetime.utcnow(),
                                   visibility=VisibilityEnum.private, prefix=str(prefix))

    _id = mongo.db.ontologies.insert_one(ontology_model.dict())
    return str(_id.inserted_id)


@ontology_router.route("/<ontology>", methods=["POST"])
@jwt_required()
def create_ontology(ontology):
    identity = get_jwt_identity()

    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify(error="No file attached."), 400

    file = request.files['file']
    id_ontology = _create_ontology_from_file(file, file.filename, identity, ontology)

    return jsonify({"successful": True, "id": id_ontology})


@ontology_router.route("/", methods=["GET"])
@jwt_required()
def get_ontologies():
    identity = get_jwt_identity()
    user = get_user_by_username(identity)

    query = {} if 'Admin' in user['roles'] else {
        "$or": [{"visibility": VisibilityEnum.public}, {"createdBy": identity}]}
    ontologies = mongo.db.ontologies.find(query)

    return jsonify(data=parse_json(list(ontologies)))


@ontology_router.route("/<id>", methods=["GET"])
@jwt_required()
def get_ontology(id):
    identity = get_jwt_identity()
    user = get_user_by_username(identity)

    query = {"_id": ObjectId(id)} if 'Admin' in user['roles'] else {
        "$or": [{"visibility": VisibilityEnum.public}, {"createdBy": identity}]}
    ontologies = mongo.db.ontologies.find_one(query)

    return jsonify(data=parse_json(ontologies))


@ontology_router.route("/<id>", methods=['PATCH'])
@jwt_required()
def edit_ontology(id):
    identity = get_jwt_identity()
    user = get_user_by_username(identity)

    if user:
        query = {"_id": ObjectId(id)} if 'Admin' in user['roles'] else {"_id": ObjectId(id),
                                                                        "createdBy": identity}
        ontology_instance = mongo.db.ontologies.find_one(query, {"_id": 0})

        if ontology_instance:
            ontology_instance.update(**request.json)
            try:
                ontology = OntologyModel(**ontology_instance)
                mongo.db.ontologies.update_one({"_id": ObjectId(id)}, {"$set": ontology.dict()})
                return jsonify(successful=f"The ref.: {id} has been updated successfully.", instance=ontology.dict())
            except Exception as ex:
                return jsonify(error=str(ex)), 400
        return jsonify(successful=False, error="The references doesn't exist."), 400
    return jsonify(successful=False), 401


@ontology_router.route("/<id>", methods=["DELETE"])
@jwt_required()
def remove_ontology(id):
    identity = get_jwt_identity()
    user = get_user_by_username(identity)

    query = {"_id": ObjectId(id)} if 'Admin' in user['roles'] else {"_id": ObjectId(id),
                                                                    "createdBy": identity}
    ontology_instance = mongo.db.ontologies.find_one(query)

    if ontology_instance:
        mongo.db.ontologies.delete_one(query)
        remove_file(ontology_instance['file_id'])
        return jsonify()

    return jsonify(), 400


@ontology_router.route("/<id>/download", methods=["GET"])
@jwt_required()
def download_ontology(id):
    identity = get_jwt_identity()
    user = get_user_by_username(identity)

    query = {"_id": ObjectId(id)} if 'Admin' in user['roles'] else {
        "$or": [{"_id": ObjectId(id), "visibility": VisibilityEnum.public},
                {"_id": ObjectId(id), "createdBy": identity}]}

    ontology_instance = mongo.db.ontologies.find_one(query)

    if ontology_instance:
        return jsonify(data=get_file(ontology_instance['file_id']).getvalue())

    return jsonify(error="No access to file"), 401


def __determine_url_path(url):
    return unquote(urlparse(url).path.split("/")[-1])


@ontology_router.route("/create/remote/<vocab>", methods=["GET"])
@jwt_required()
def create_ontology_from_remote_source(vocab):
    identity = get_jwt_identity()
    url = "https://lov.linkeddata.es/dataset/lov/api/v2/vocabulary/info?vocab=" + vocab

    response = requests.get(url, allow_redirects=True)

    if response.status_code == 200:
        json_response = response.json()
        prefix = json_response['prefix']
        prefix_url = json_response['nsp']
        id_returned = create_or_return_prefix({'prefix': prefix, 'url': prefix_url})
        url_to_download = json_response['versions'][0]['fileURL']
        filename = os.path.basename(__determine_url_path(url_to_download))
        filename_extension = filename.split('.')[1]
        filename_no_extension = filename.split('.')[0]
        response = requests.get(url_to_download, allow_redirects=True)

        if filename_extension == "n3":
            conversion_from = "n3"
        elif filename_extension == "ttl":
            conversion_from = "ttl"
        else:
            return 500, "No format supported " + filename_extension

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_filename = tmp_dir_name + "/" + filename
            with open(tmp_filename, "wb") as file:
                file.write(response.content)

            os.system("python rdfconvert/rdfconvert.py {} --from {} --to nt > {}.owl"
                      .format(tmp_filename, conversion_from, filename_no_extension))

            with open(filename_no_extension+".owl", "rb") as file:
                id_ontology = _create_ontology_from_file(file, vocab + ".owl", identity, vocab, id_returned)
                return jsonify({"successful": True, "id": id_ontology})


@ontology_router.route("/mua/<vocab>", methods=["GET"])
@jwt_required()
def get_measure_ontology_details(vocab):
    owl.onto_path.append("/data/")
    go = owl.get_ontology("data/om.owl").load()

    a = list(default_world.sparql("""
               SELECT (?x AS ?nb)
               { 
                    ?x a owl:Class .                            
                                   }
        """))
    classes = [str(x[0]) for x in a]
    classes = [x for x in classes if x.startswith('om.') and '(' not in x and '|' not in x and vocab in x]

    return jsonify({"classes": classes})

