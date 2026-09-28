import logging
import os
from typing import Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError


logger = logging.getLogger(__name__)
_client: Optional[MongoClient] = None


def create_client() -> MongoClient:
	"""Create a MongoDB client using environment configuration."""
	uri = os.getenv("MONGO_DB_SERVER", "mongodb://localhost:27017")
	username = os.getenv("MONGO_DB_USER")
	password = os.getenv("MONGO_DB_PASSWORD")
	return MongoClient(
		uri,
		username=username,
		password=password,
		serverSelectionTimeoutMS=10000,
	)


def connect_to_mongo() -> MongoClient:
	"""Create the shared client and verify the MongoDB connection."""
	global _client
	if _client is None:
		logger.info("Connecting to MongoDB...")
		_client = create_client()
	_client.admin.command("ping")
	return _client


def get_collection(collection_name: str) -> Collection:
	"""Return a collection from the configured database."""
	database_name = os.getenv("MONGO_DB_NAME", "fiap-pos-ia-db")
	return connect_to_mongo()[database_name][collection_name]


def test_connection() -> bool:
	"""Ping MongoDB and return True when the connection is available."""
	try:
		connect_to_mongo()
		logger.info("MongoDB connection successful.")
		return True
	except PyMongoError as error:
		logger.error("MongoDB connection failed: %s", error)
		return False
