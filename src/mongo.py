from pymongo import MongoClient
from datetime import datetime
from collections import OrderedDict


def hourDataFound(mongo_uri, db_name, collection_name, source):
    # Create a MongoDB client
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]

    # Get the start and end of the current hour
    now = datetime.utcnow()
    start_of_hour = now.replace(minute=0, second=0, microsecond=0)
    end_of_hour = now.replace(minute=59, second=59, microsecond=999999)

    try:
        # Check if a record from the same source exists within the current hour
        existing_record = collection.find_one({
            "source": source, 
            "timestamp": {"$gte": start_of_hour, "$lt": end_of_hour}
        })

        return existing_record is not None
    
    except Exception as error:
        print(f"[ERROR {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking Mongo Hour Interval: {error}")



def insert_mongo_data(mongo_uri, db_name, collection_name, data, deviceName):
    # Create a MongoDB client
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]

    # Proceed with saving the new data
    try:
        ordered_data = OrderedDict()
        ordered_data["source"] = data.get("source")
        ordered_data["timestamp"] = datetime.utcnow()
        ordered_data["temperature"] = data.get("temperature")
        ordered_data["pressure"] = data.get("pressure")
        ordered_data["humidity"] = data.get("humidity")
        ordered_data["wind"] = data.get("wind")
        ordered_data["deviceName"] = deviceName

        collection.insert_one(ordered_data)
    except Exception as error:
        print(f"[ERROR {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] MongoDB query/save error: {error}")

    client.close()  # Close the client