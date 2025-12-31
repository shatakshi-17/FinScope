"""
Database Service - MongoDB Session and Conversation Management

This service provides:
- Persistent storage for conversations (SEC and UPLOAD workflows)
- Temporary active_sessions collection with TTL (1 hour expiration)
- Session cleanup logic that deletes local files when sessions end
- Session locking to prevent multiple concurrent sessions
"""

import os
from datetime import datetime
from typing import Dict, List, Optional, Literal
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection string from environment
MONGODB_URI = os.getenv('MONGODB_URI')
if not MONGODB_URI:
    raise ValueError(
        "MONGODB_URI not found in environment variables. "
        "Please create a .env file with MONGODB_URI=your_connection_string"
    )

# Database and collection names
DB_NAME = "finscope"
CONVERSATIONS_COLLECTION = "conversations"
ACTIVE_SESSIONS_COLLECTION = "active_sessions"

# TTL duration: 3600 seconds (1 hour)
TTL_SECONDS = 3600

# Global MongoDB client and database references
_client: Optional[MongoClient] = None
_db = None


def get_database():
    """
    Returns the MongoDB database instance, creating connection if needed.
    Initializes TTL index on first call.
    
    Returns:
        Database: MongoDB database instance
    
    Raises:
        ConnectionFailure: If unable to connect to MongoDB
    """
    global _client, _db
    
    if _db is not None:
        return _db
    
    try:
        # Create MongoDB client
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        
        # Test connection
        _client.admin.command('ping')
        
        # Get database
        _db = _client[DB_NAME]
        
        # Initialize TTL index on startup
        _initialize_ttl_index()
        
        print(f"✓ Connected to MongoDB: {DB_NAME}")
        return _db
        
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        raise ConnectionFailure(
            f"Failed to connect to MongoDB: {e}. "
            f"Please check your MONGODB_URI in .env file."
        )


def _initialize_ttl_index():
    """
    Creates a TTL index on the 'createdAt' field in active_sessions collection.
    Documents will automatically expire after TTL_SECONDS (1 hour).
    
    This is called automatically on database connection.
    """
    db = get_database()
    collection = db[ACTIVE_SESSIONS_COLLECTION]
    
    # Check if index already exists
    existing_indexes = collection.list_indexes()
    index_names = [idx['name'] for idx in existing_indexes]
    
    if 'createdAt_1' not in index_names:
        # Create TTL index on createdAt field
        collection.create_index(
            [("createdAt", ASCENDING)],
            expireAfterSeconds=TTL_SECONDS,
            name="createdAt_1"
        )
        print(f"✓ Created TTL index on {ACTIVE_SESSIONS_COLLECTION}.createdAt (expires after {TTL_SECONDS}s)")
    else:
        print(f"✓ TTL index already exists on {ACTIVE_SESSIONS_COLLECTION}.createdAt")


def is_session_active() -> bool:
    """
    Checks if there is an active session in the active_sessions collection.
    Used for session locking - prevents starting a new chat if a session is active.
    
    Returns:
        bool: True if any active session exists, False otherwise
    """
    db = get_database()
    collection = db[ACTIVE_SESSIONS_COLLECTION]
    
    count = collection.count_documents({})
    return count > 0


def create_conversation(
    workflow_type: Literal['SEC', 'UPLOAD'],
    metadata: Dict,
    initial_message: Optional[Dict] = None
) -> str:
    """
    Creates a new conversation record in the conversations collection.
    
    Args:
        workflow_type: Either 'SEC' or 'UPLOAD'
        metadata: Polymorphic metadata based on workflow_type:
            - For 'SEC': { company, cik, filing_date, doc_type }
            - For 'UPLOAD': { company, year, doc_type, original_filename }
        initial_message: Optional first message { role, content, timestamp }
    
    Returns:
        str: The chat_id (MongoDB _id as string) of the created conversation
    
    Raises:
        ValueError: If workflow_type is invalid or metadata is missing required fields
    """
    db = get_database()
    collection = db[CONVERSATIONS_COLLECTION]
    
    # Validate workflow type
    if workflow_type not in ['SEC', 'UPLOAD']:
        raise ValueError(f"Invalid workflow_type: {workflow_type}. Must be 'SEC' or 'UPLOAD'")
    
    # Validate metadata based on workflow type
    if workflow_type == 'SEC':
        required_fields = ['company', 'cik', 'filing_date', 'doc_type']
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Missing required field for SEC workflow: {field}")
    elif workflow_type == 'UPLOAD':
        required_fields = ['company', 'year', 'doc_type', 'original_filename']
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Missing required field for UPLOAD workflow: {field}")
    
    # Build conversation document
    conversation = {
        "workflow_type": workflow_type,
        "metadata": metadata,
        "messages": [],
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Add initial message if provided
    if initial_message:
        if 'timestamp' not in initial_message:
            initial_message['timestamp'] = datetime.utcnow()
        conversation["messages"].append(initial_message)
    
    # Insert into database
    result = collection.insert_one(conversation)
    chat_id = str(result.inserted_id)
    
    print(f"✓ Created conversation: {chat_id} (workflow: {workflow_type})")
    return chat_id


def create_active_session(chat_id: str, temp_file_paths: List[str]) -> None:
    """
    Creates an active session record with temporary file paths.
    This session will automatically expire after TTL_SECONDS (1 hour).
    
    Args:
        chat_id: The conversation ID this session belongs to
        temp_file_paths: List of local file paths that should be deleted when session ends
    """
    db = get_database()
    collection = db[ACTIVE_SESSIONS_COLLECTION]
    
    session = {
        "chat_id": chat_id,
        "temp_file_paths": temp_file_paths,
        "createdAt": datetime.utcnow()
    }
    
    collection.insert_one(session)
    print(f"✓ Created active session for chat_id: {chat_id} with {len(temp_file_paths)} file(s)")


def add_message_to_conversation(chat_id: str, role: str, content: str) -> None:
    """
    Adds a message to an existing conversation.
    
    Args:
        chat_id: The conversation ID
        role: Either 'user' or 'assistant'
        content: The message content
    
    Raises:
        ValueError: If chat_id is invalid or conversation not found
    """
    db = get_database()
    collection = db[CONVERSATIONS_COLLECTION]
    
    from bson import ObjectId
    
    try:
        object_id = ObjectId(chat_id)
    except Exception as e:
        raise ValueError(f"Invalid chat_id format: {chat_id}. Error: {str(e)}")
    
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow()
    }
    
    result = collection.update_one(
        {"_id": object_id},
        {
            "$push": {"messages": message},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    if result.matched_count == 0:
        raise ValueError(f"Conversation not found for chat_id: {chat_id}")
    
    if result.modified_count == 0:
        print(f"Warning: Message not added to conversation {chat_id} (conversation may not exist or message already present)")
    
    print(f"✓ Added {role} message to conversation: {chat_id}")


def add_file_to_session(chat_id: str, file_path: str) -> None:
    """
    Adds a temporary file path to an existing active session.
    
    Args:
        chat_id: The conversation ID
        file_path: Path to a local file that should be deleted when session ends
    """
    db = get_database()
    collection = db[ACTIVE_SESSIONS_COLLECTION]
    
    collection.update_one(
        {"chat_id": chat_id},
        {"$push": {"temp_file_paths": file_path}}
    )
    print(f"✓ Added file to session: {file_path}")


def end_chat_session(chat_id: str) -> None:
    """
    The 'Cleaning Crew' function - ends a chat session and cleans up local files.
    
    This function:
    1. Looks up temp_file_paths in active_sessions
    2. Uses os.remove() to physically delete every file in that list
    3. Sets is_active = False in the conversations record
    4. Deletes the record from active_sessions
    
    Args:
        chat_id: The conversation ID to end
    """
    db = get_database()
    sessions_collection = db[ACTIVE_SESSIONS_COLLECTION]
    conversations_collection = db[CONVERSATIONS_COLLECTION]
    
    from bson import ObjectId
    
    # Step 1: Look up temp_file_paths in active_sessions
    session = sessions_collection.find_one({"chat_id": chat_id})
    
    if not session:
        print(f"⚠ No active session found for chat_id: {chat_id}")
        return
    
    temp_file_paths = session.get("temp_file_paths", [])
    
    # Step 2: Delete every file in temp_file_paths
    deleted_count = 0
    failed_count = 0
    
    for file_path in temp_file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"✓ Deleted file: {file_path}")
                deleted_count += 1
            else:
                print(f"⚠ File not found (already deleted?): {file_path}")
        except Exception as e:
            print(f"✗ Failed to delete file {file_path}: {e}")
            failed_count += 1
    
    print(f"✓ Cleanup complete: {deleted_count} deleted, {failed_count} failed")
    
    # Step 3: Set is_active = False in conversations record
    conversations_collection.update_one(
        {"_id": ObjectId(chat_id)},
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }
        }
    )
    print(f"✓ Archived conversation: {chat_id}")
    
    # Step 4: Delete the record from active_sessions
    sessions_collection.delete_one({"chat_id": chat_id})
    print(f"✓ Removed active session: {chat_id}")


def get_conversation(chat_id: str) -> Optional[Dict]:
    """
    Retrieves a conversation by chat_id.
    
    Args:
        chat_id: The conversation ID
    
    Returns:
        Dict: The conversation document, or None if not found
    """
    db = get_database()
    collection = db[CONVERSATIONS_COLLECTION]
    
    from bson import ObjectId
    
    conversation = collection.find_one({"_id": ObjectId(chat_id)})
    
    if conversation:
        # Convert ObjectId to string for JSON serialization
        conversation["_id"] = str(conversation["_id"])
    
    return conversation


def delete_conversation(chat_id: str) -> bool:
    """
    Permanently deletes a conversation from the database.
    Also cleans up any associated active session if it exists.
    
    Args:
        chat_id: The conversation ID to delete
    
    Returns:
        bool: True if conversation was deleted, False if not found
    
    Raises:
        ValueError: If chat_id format is invalid
    """
    db = get_database()
    conversations_collection = db[CONVERSATIONS_COLLECTION]
    sessions_collection = db[ACTIVE_SESSIONS_COLLECTION]
    
    from bson import ObjectId
    from bson.errors import InvalidId
    
    # Validate chat_id format
    try:
        object_id = ObjectId(chat_id.strip())
    except InvalidId:
        raise ValueError(f"Invalid chat_id format: {chat_id}")
    
    # Check if conversation exists
    conversation = conversations_collection.find_one({"_id": object_id})
    if not conversation:
        return False
    
    # If conversation has an active session, clean up temp files first
    session = sessions_collection.find_one({"chat_id": chat_id})
    if session:
        temp_file_paths = session.get("temp_file_paths", [])
        for file_path in temp_file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"✓ Deleted file: {file_path}")
            except Exception as e:
                print(f"⚠ Failed to delete file {file_path}: {e}")
        
        # Delete the active session
        sessions_collection.delete_one({"chat_id": chat_id})
        print(f"✓ Removed active session: {chat_id}")
    
    # Delete the conversation
    result = conversations_collection.delete_one({"_id": object_id})
    
    if result.deleted_count > 0:
        print(f"✓ Deleted conversation: {chat_id}")
        return True
    else:
        return False


if __name__ == "__main__":
    """
    Quick verification: Test database connection and TTL index initialization.
    Run this file directly to verify MongoDB connection is working.
    """
    print("Testing MongoDB connection and TTL index initialization...")
    try:
        db = get_database()
        print("\n✓ Database service is ready!")
        print(f"   Database: {DB_NAME}")
        print(f"   Collections: {CONVERSATIONS_COLLECTION}, {ACTIVE_SESSIONS_COLLECTION}")
        print(f"   TTL expiration: {TTL_SECONDS} seconds (1 hour)")
    except Exception as e:
        print(f"\n✗ Connection failed: {e}")
        import sys
        sys.exit(1)
