import os
from pymongo import MongoClient

MONGO_URI = "mongodb+srv://zenitha2026_db_user:XcTad72Wsa1pLufY@cluster0.la5cscc.mongodb.net/?appName=Cluster0"

def check_db():
    try:
        client = MongoClient(MONGO_URI)
        db = client["mumms_inventory"]
        
        print("--- USERS ---")
        for u in db["users"].find({}, {"_id": 0}):
            print(u)
            
        print("\n--- EVENTS ---")
        for e in db["events"].find({}, {"_id": 0}):
            print(e)
            
        print("\n--- ATTENDANCE ---")
        for a in db["attendance"].find({}).sort("timestamp", -1).limit(10):
            a['_id'] = str(a['_id'])
            print(a)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
