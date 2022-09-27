from flask import Blueprint, jsonify, request
from pyDataverse.api import NativeApi, DataAccessApi
from flask_jwt_extended import jwt_required

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
                        'filename': element['filename'],
                    })
    return response


@dataverse_router.route('/', methods=["GET"])
@jwt_required()
def retrieve_dataverses():
    dataverse_url = request.args['url']
    filter_by = request.args['filter_by'] if 'filter_by' in request.args else []
    filter_by.split(',')
    dataverse_api = NativeApi(dataverse_url)

    tree = dataverse_api.get_children("UDL", children_types=["datasets", "datafiles"])
    response = __explore_dataset(tree, filter_by)
    return jsonify(response), 200
