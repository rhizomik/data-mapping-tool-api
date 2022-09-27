import bcrypt
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from password_strength import PasswordPolicy
from pyDataverse.api import NativeApi, DataAccessApi

from database import mongo
from models.user import UserModel
from utils import get_user_by_username


dataverse_router = Blueprint('dataverse', __name__)

policy = PasswordPolicy.from_names(
    length=8,  # min length: 8
    uppercase=1,  # need min. 1 uppercase letters
    numbers=1,  # need min. 1 digits
    special=1,  # need min. 1 special characters
)

BASE_URL = "https://dataverse.csuc.cat"
dataverse_api = NativeApi(BASE_URL)
data_api = DataAccessApi(BASE_URL)

ALLOWED_EXTENSIONS = ['xls', 'csv', 'tsv']


def __explore_dataset(dataset_data_list):
    response = {
        'datafiles': [],
        'datasets': []
    }

    for element in dataset_data_list:
        if element['type'] == 'dataset':
            dataset_data = {
                'pid': element['pid'],
                'children': __explore_dataset(element['children'])
            }
            response['datasets'].append(dataset_data)
        if element['type'] == 'datafile':
            name = element['label']
            if '.' in name:
                extension = element['label'].split('.')[1]
                if extension in ALLOWED_EXTENSIONS:
                    response['datafiles'].append({
                        'pid': element['pid'],
                        'label': element['label'],
                        'filename': element['filename'],
                    })
    return response


@dataverse_router.route("/", methods=["GET"])
def get_users():

    tree = dataverse_api.get_children("UDL", children_types=["datasets", "datafiles"])
    response = __explore_dataset(tree)
    return jsonify(response), 200
