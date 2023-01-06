from database import mongo
from models.prefix import PrefixModel


def create_or_return_prefix(prefix_body):
    results = mongo.db.prefix.find_one({'prefix': prefix_body['prefix'], 'url': prefix_body['url']})
    if results is None:
        prefix = PrefixModel(**prefix_body)
        insertion = mongo.db.prefix.insert_one(prefix.dict())
        inserted_id = insertion['inserted_id']
    else:
        inserted_id = results['_id']
    return inserted_id