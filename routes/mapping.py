from typing import List

from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

import utils.transformations as transform
from database import mongo
from models.inference import FieldInfo
from utils.utils import get_user_by_username
from collections import defaultdict

PREFIXES = """
prefixes:
  ex: http://www.example.com/
  e: http://myontology.com/
  dbo: http://dbpedia.org/ontology/
  grel: http://users.ugent.be/~bjdmeest/function/grel.ttl#

"""

mapping_router = Blueprint('mapping', __name__)


def __generate_prefix_dict(prefix_response):
    return {prefix_response['prefix']: prefix_response['url']}

def build_column_mapping_dictionary(mappings):
    inverse_dict = dict()
    for key, element in mappings.items():
        for column in element['columns']:
            if column in inverse_dict:
                inverse_dict[column] .append(key)
            else:
                inverse_dict[column] = [key]
    return inverse_dict

@mapping_router.route("/", methods=["POST"])
@jwt_required()
def generate_mapping_config():
    identity = get_jwt_identity()
    user = get_user_by_username(identity)
    req = request.json
    if '_id' in req.keys() and 'classes' in req.keys() and req['classes']:
        query = {'_id': ObjectId(req['_id'])} if 'Admin' in user['roles'] else {'_id': ObjectId(req['_id']), "createdBy": identity}
        instance = mongo.db.instances.find_one(query, {"_id": 0})
        assigned_ontology = mongo.db.ontologies.find_one({'_id': ObjectId(instance['current_ontology'])})
        inferences: List[FieldInfo] = mongo.db.inferences.find_one({'filename': instance['filenames'][0]})

        prefix_dict = dict()
        for inference in inferences['inferences']:
            if inference['prefix']:
                prefix = inference['prefix']['prefix']
                uri = inference['prefix']['uri']
                prefix_dict.update({prefix: uri})

        if assigned_ontology and 'prefix' in assigned_ontology and assigned_ontology['prefix'] is not None:
            prefix = mongo.db.prefix.find_one({'_id': ObjectId(assigned_ontology['prefix'])})
            prefix_dict.update(__generate_prefix_dict(prefix))

        else:
            prefix = None


        yaml = ""
        yaml += transform.add_prefixes(prefix_dict)
        yaml += transform.init_mappings()

        mapping_dict = build_column_mapping_dictionary(instance['mapping'])

        for element in req['classes']:
            element_split = element.split('.')
            yaml += transform.add_mapping(element_split[-1].lower())
            yaml += transform.init_sources()
            yaml += transform.add_source(f"{instance['mapping'][element]['fileSelected']}")
            prefix = element_split[0]
            column_name = instance['mapping'][element]['subject']
            if 'mapping' in instance and element in instance['mapping'] and 'subject' in instance['mapping'][element]:
                yaml += transform.add_simple_subject(f"{element}", column_name)
            # if not 'suggest_ontology' in instance:
            #     prefix = 'bigg:'
            #     yaml += transform.add_simple_subject(f"{prefix + element}", instance['mapping'][element]['subject'])
            # elif not instance['suggest_ontology']:
            #     prefix = 'bigg:'
            #     yaml += transform.add_simple_subject(f"{prefix + element}", instance['mapping'][element]['subject'])
            if inferences:
                for inference in inferences['inferences']:
                    if inference['name'] == column_name:
                        inference_type = inference['type']
                        inference_sub_type = inference['subtype']
                        inference_annotation = inference['annotation']
                        if inference_type:
                            yaml += transform.add_type(inference_type)
                        if inference_sub_type:
                            yaml += transform.add_sub_type(inference_sub_type)
                        if inference_annotation:
                            inference_annotation_splitted = inference_annotation.split('.')
                            inference_annotation_prefix = inference_annotation_splitted[0]
                            inference_annotation_name = inference_annotation_splitted[1]
                            yaml += transform.add_annotation(inference_annotation_prefix, inference_annotation_name)

            mapping_element = instance['mapping'][element]

            first_time = False

            # Property objects
            for key, value in mapping_element['columns'].items():
                if not first_time:
                    yaml += transform.init_predicate_object()
                    yaml += transform.add_predicate_object_simple('a', f"schema:{element}")
                    first_time = True
                yaml += transform.add_predicate_object_simple(f"schema:{key}", f"$({value})")

            for key, value in instance['relations'].items():
                if value['selected'] and value['from'] == element and value['to'] in req['classes']:
                    yaml += transform.link_entities(f"{prefix}:{key}",
                                                    value['to'].split('.')[-1].lower(), "equal",
                                                    f"$({value['from_rel']})", f"$({value['to_rel']})")

            yaml += "\n"

        return jsonify(successful=True, yaml=yaml)

    return jsonify(successful=False), 400
