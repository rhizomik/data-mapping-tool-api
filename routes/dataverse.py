import json
import tempfile
from flask import Blueprint, jsonify, request, send_file
from pyDataverse.api import NativeApi, DataAccessApi
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename

dataverse_router = Blueprint('dataverses', __name__)


def __explore_dataset(dataset_data_list, datafiles_extensions):
    response = {
        'datafiles': [],
        'datasets': []
    }

    for element in dataset_data_list:
        if element['type'] == 'dataset':
            dataset_data = {
                'pid': element['pid'],
                'children': __explore_dataset(element['children'], datafiles_extensions)
            }
            response['datasets'].append(dataset_data)
        if element['type'] == 'datafile':
            name = element['label']
            if '.' in name:
                extension = element['label'].split('.')[1]
                if extension in datafiles_extensions or len(datafiles_extensions) == 0:
                    response['datafiles'].append({
                        'pid': element['pid'],
                        'label': element['label'],
                        'datafile_id': element['datafile_id'],
                        'filename': element['filename'],
                    })
    return response


@dataverse_router.route('/', methods=["GET"])
def retrieve_dataverses():
    dataverse_url = request.args['url']
    name = request.args['name']
    filter_by = request.args['filter_by'] if 'filter_by' in request.args else []
    filter_by.split(',')
    dataverse_api = NativeApi(dataverse_url)

    tree = dataverse_api.get_children(name, children_types=["datasets", "datafiles"])
    response = __explore_dataset(tree, filter_by)
    return jsonify(response), 200


@dataverse_router.route('/datafile/', methods=["GET"])
def download_datafile():
    dataverse_url = request.args['url']
    id_datafile = request.args['id']
    data_api = DataAccessApi(dataverse_url)
    dataverse_api = NativeApi(dataverse_url)
    datafile_metadata = json.loads(dataverse_api.get_datafile_metadata(id_datafile, False).content.decode('utf8').replace("'", '"'))
    response = data_api.get_datafile(id_datafile)

    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = temp_dir + '/' + secure_filename(datafile_metadata['label'])
        with open(file_path, "wb") as f:
            f.write(response.content)
        return send_file(file_path, attachment_filename=datafile_metadata['label'])

