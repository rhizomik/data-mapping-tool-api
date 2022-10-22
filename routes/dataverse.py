import json
import tempfile
from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from pyDataverse.api import NativeApi, DataAccessApi
from pyDataverse.utils import dataverse_tree_walker
from werkzeug.utils import secure_filename

from routes.ontology import _create_ontology_from_file

dataverse_router = Blueprint('dataverses', __name__)


@dataverse_router.route('/', methods=["GET"])
def retrieve_dataverses():
    dataverse_url = request.args['url']
    name = request.args['name']
    filter_by = request.args['filter_by'] if 'filter_by' in request.args else []
    if len(filter_by) > 0:
        filter_by.split(',')
    dataverse_api = NativeApi(dataverse_url)
    tree = dataverse_api.get_children(name, children_types=["datasets", "datafiles", "dataverses"])
    dataverses, datasets, datafiles = dataverse_tree_walker(tree)
    response = {
        'dataverses': dataverses,
        'datafiles': datafiles,
        'datasets': datasets
    }

    return jsonify(response), 200


@dataverse_router.route('/dataset/', methods=["GET"])
def explore_dataset():
    dataverse_url = request.args['url']
    id_dataset = request.args['id']
    dataverse_api = NativeApi(dataverse_url)
    metadata = dataverse_api.get_datafiles_metadata(id_dataset).content
    metadata_dict = json.loads(metadata.decode("utf8"))['data']

    response = {
        'files': []
    }
    for file in metadata_dict:
        response['files'].append(
            {
                'id': file['dataFile']['id'],
                'persistentId': file['dataFile']['persistentId'],
                'response': file['dataFile']['response'],
                'fileName': file['dataFile']['filename'],
                'contentType': file['dataFile']['contentType'],
                'creationDate': file['dataFile']['creationDate'],
            }
        )

    return jsonify(response), 200


@dataverse_router.route('/datafile/', methods=["GET"])
def download_datafile():
    dataverse_url = request.args['url']
    id_datafile = request.args['id']
    data_api = DataAccessApi(dataverse_url)
    dataverse_api = NativeApi(dataverse_url)

    datafile_metadata = json.loads(dataverse_api
                                   .get_datafile_metadata(id_datafile, False)
                                   .content
                                   .decode('utf8').replace("'", '"'))
    response = data_api.get_datafile(id_datafile)

    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = temp_dir + '/' + secure_filename(datafile_metadata['label'])
        with open(file_path, "wb") as f:
            f.write(response.content)
        return send_file(file_path, attachment_filename=datafile_metadata['label'])


@dataverse_router.route('/ontology/', methods=["GET"])
@jwt_required()
def retrieve_dataverseas():
    identity = get_jwt_identity()
    dataverse_url = request.args['url']
    id_datafile = request.args['id']
    ontology_name = request.args['ontology_name']
    data_api = DataAccessApi(dataverse_url)
    dataverse_api = NativeApi(dataverse_url)

    datafile_metadata = json.loads(dataverse_api
                                   .get_datafile_metadata(id_datafile, False)
                                   .content
                                   .decode('utf8').replace("'", '"'))
    response = data_api.get_datafile(id_datafile)
    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = temp_dir + '/' + secure_filename(datafile_metadata['label'])
        with open(file_path, "wb") as f:
            f.write(response.content)

        with open(file_path, "rb") as f:
            _create_ontology_from_file(f, datafile_metadata['label'], identity, ontology_name)
    return jsonify(successful=True)
