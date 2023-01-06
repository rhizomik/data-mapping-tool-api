from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from database import mongo
from models.prefix import PrefixModel
from utils.utils import get_user_by_username

prefixs_router = Blueprint('prefixes', __name__)

@prefixs_router.route("/<prefix>", methods=["GET"])
@jwt_required()
def get_prefix(prefix):
    identity = get_jwt_identity()
    current_user = get_user_by_username(identity)
    if 'Admin' in current_user['roles'] or identity == id:
        return jsonify(prefix=mongoi.db.prefix.find_one_or_404({'prefix': prefix}, {'_id': 0}))
    return jsonify(error=True), 400

@prefixs_router.route("/", methods=["POST"])
@jwt_required()
def add_prefix(prefix):
    body = request.json
    identity = get_jwt_identity()
    current_user = get_user_by_username(identity)
    if 'Admin' in current_user['roles'] or identity == id:
        prefix = PrefixModel(**body)
        mongo.db.prefix.insert_one(prefix.dict())
        return jsonify(prefix=prefix.dict()), 201
    return jsonify(error=True), 400
