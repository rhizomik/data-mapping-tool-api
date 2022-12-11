import json
import os
import tempfile
from io import StringIO
from typing import Dict

import numpy as np
import pandas as pd
from bson import json_util
from flask import Blueprint, request, jsonify
from tableschema import Table, infer
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from database import mongo
from models.inference import InferenceModel, FieldInfo
from models.key import KeyModel
from utils.subtypes import infere_sub_type
from utils.utils import allowed_files

files_router = Blueprint('files', __name__)

ALLOWED_EXTENSIONS = ['csv']


def __save_file(file, filename, identity, inference):
    if file and allowed_files(filename=filename, allowed_extensions=ALLOWED_EXTENSIONS):
        mongo.save_file(filename=filename, fileobj=file, kwargs={"owner": identity, "inference": inference})


def __get_subtype(inference, values):
    sub_type = None
    if inference['type'] == 'string':
        sub_type = infere_sub_type(values)
    inference['subtype'] = sub_type


@files_router.route("/upload", methods=["POST"])
@jwt_required()
def upload_file():
    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify(error="No file attached."), 400

    file = request.files['file']
    identity = get_jwt_identity()
    handle, output = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(handle, "wb") as f:
        f.write(file.read())
    csv_pandas = pd.read_csv(output)

    inference = infer(output)
    body = {
        "filename": file.filename,
        "inferences": inference['fields']
    }

    for inference_value in inference['fields']:
        __get_subtype(inference_value, csv_pandas.loc[:, inference_value['name']])

    inferences = InferenceModel(**body)
    mongo.db.inferences.update_one({'filename': file.filename}, {"$set": inferences.dict()}, upsert=True)
    file.stream.seek(0)
    __save_file(file, file.filename, identity, inference['fields'])
    return jsonify(successful=True)


@files_router.route("/download/<filename>", methods=["GET"])
@jwt_required()
def download_file(filename):
    identity = get_jwt_identity()
    has_access = mongo.db.fs.files.find_one({"kwargs.owner": identity, "filename": filename})
    if has_access:
        return mongo.send_file(filename=filename)
    return jsonify(error="No access to file"), 401


@files_router.route("/<filename>", methods=["GET"])
@jwt_required()
def get_columns(filename):
    identity = get_jwt_identity()

    has_access = mongo.db.fs.files.find_one({"kwargs.owner": identity, "filename": filename})
    if has_access:
        file = mongo.send_file(filename=filename)
        file_str = file.response.file.read().decode('utf-8')
        df = pd.read_csv(StringIO(file_str), sep=',')
        df = df.astype(object).replace(np.nan, 'None')
        return jsonify(columns=list(df.columns), sample=df.head(25).to_dict(orient="records"))
    return jsonify(error="No access to file"), 401


@files_router.route("/inferences/<filename>", methods=["GET"])
@jwt_required()
def get_inferences(filename):
    identity = get_jwt_identity()

    has_access = mongo.db.fs.files.find_one({"kwargs.owner": identity, "filename": filename})
    if has_access:
        inferences = mongo.db.inferences.find_one({'filename': filename})
        return jsonify(inferences['inferences'])
    return jsonify(error="No access to file"), 401


@files_router.route("/inferences/<filename>", methods=["POST"])
@jwt_required()
def update_inferences(filename):
    identity = get_jwt_identity()
    has_access = mongo.db.fs.files.find_one({"kwargs.owner": identity, "filename": filename})
    if has_access:
        body = {
            "filename": filename,
            "inferences": request.json["inferences"]
        }
        inference_model = InferenceModel(**body)
        mongo.db.inferences.update_one({'filename': filename}, {"$set": inference_model.dict()})
        return jsonify(inference_model.dict())
    return jsonify(error="No access to file"), 401


@files_router.route("/key/<filename>", methods=["POST"])
@jwt_required()
def update_primary_key(filename):
    identity = get_jwt_identity()
    has_access = mongo.db.fs.files.find_one({"kwargs.owner": identity, "filename": filename})
    if has_access:
        body = {
            "filename": filename,
            "key": request.json["key"] if "key" in request.json else None
        }
        key_model = KeyModel(**body)
        mongo.db.keys.update_one({'filename': filename}, {"$set": key_model.dict()}, upsert=True)
        return jsonify(key_model.dict())
    return jsonify(error="No access to file"), 401


@files_router.route("/key/<filename>", methods=["GET"])
@jwt_required()
def get_primary_key(filename):
    identity = get_jwt_identity()
    has_access = mongo.db.fs.files.find_one({"kwargs.owner": identity, "filename": filename})
    if has_access:
        instance = mongo.db.keys.find_one({"filename": filename})
        return jsonify(instance["key"])
    return jsonify(error="No access to file"), 401


@files_router.route("/keys/<filename>", methods=["GET"])
@jwt_required()
def get_keys(filename):
    identity = get_jwt_identity()

    has_access = mongo.db.fs.files.find_one({"kwargs.owner": identity, "filename": filename})
    if has_access:
        file = mongo.send_file(filename=filename)
        file_str = file.response.file.read().decode('utf-8')
        df = pd.read_csv(StringIO(file_str), sep=',')
        df = df.astype(object).replace(np.nan, 'None')
        unique_columns_set = set()
        for name, values in df.iteritems():
            unique_columns_set.add(name.strip()) if len(values) == len(set(values)) else None

        response = dict()
        response['columns'] = list(unique_columns_set)

        return jsonify(response)
    return jsonify(error="No access to file"), 401

