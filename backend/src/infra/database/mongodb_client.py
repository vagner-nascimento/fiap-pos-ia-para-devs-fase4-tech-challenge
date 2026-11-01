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


def get_database(database_name: Optional[str] = None):
	"""Return the configured or specified MongoDB database."""
	db_name = database_name or os.getenv("MONGO_DB_NAME", "fiap-pos-ia-db")
	return connect_to_mongo()[db_name]


def get_collection(collection_name: str) -> Collection:
	"""Return a collection from the configured database."""
	return get_database()[collection_name]


def set_client(client: Optional[MongoClient]) -> None:
	"""Set the global client instance (useful for testing and dependency injection)."""
	global _client
	_client = client


def close_connection() -> None:
	"""Close the shared MongoDB client connection if open."""
	global _client
	if _client is not None:
		_client.close()
		_client = None


def test_connection() -> bool:
	"""Ping MongoDB and return True when the connection is available."""
	try:
		connect_to_mongo()
		logger.info("MongoDB connection successful.")
		return True
	except PyMongoError as error:
		logger.error("MongoDB connection failed: %s", error)
		return False
