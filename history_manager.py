"""
History Manager - Backend for Past Chats Landing Page

This service provides:
- Retrieval of archived conversations (is_active = False)
- Preview/summary view of archived chats
- Full conversation log retrieval
- Search/filter functionality by company name

Note: This module does NOT use any AI/Gemini functions - it is strictly for database retrieval.
"""

from typing import List, Dict, Optional
from datetime import datetime
from db_service import get_database, CONVERSATIONS_COLLECTION


def _generate_title(workflow_type: str, metadata: Dict) -> str:
    """
    Generates a title for a conversation based on workflow type and metadata.
    
    Args:
        workflow_type: Either 'SEC' or 'UPLOAD'
        metadata: Polymorphic metadata dictionary
    
    Returns:
        str: Generated title string
    """
    company = metadata.get('company', 'Unknown Company')
    doc_type = metadata.get('doc_type', 'Document')
    
    if workflow_type == 'SEC':
        filing_date = metadata.get('filing_date', 'Unknown Date')
        return f"{company} - {doc_type} ({filing_date})"
    elif workflow_type == 'UPLOAD':
        year = metadata.get('year', 'Unknown Year')
        return f"{company} - {doc_type} ({year})"
    else:
        return f"{company} - {doc_type}"


def _convert_to_preview(conversation: Dict) -> Dict:
    """
    Converts a full conversation document to a preview object.
    
    Args:
        conversation: Full conversation document from MongoDB
    
    Returns:
        Dict: Preview object with chat_id, title, source_type, created_at, and metadata
    
    Raises:
        KeyError: If conversation is missing required '_id' field
    """
    # Ensure _id exists
    if '_id' not in conversation:
        raise KeyError("Conversation missing required '_id' field")
    
    chat_id = str(conversation['_id'])
    workflow_type = conversation.get('workflow_type', 'UNKNOWN')
    
    # Ensure metadata is a dict (defensive programming)
    metadata = conversation.get('metadata', {})
    if not isinstance(metadata, dict):
        metadata = {}
    
    created_at = conversation.get('created_at')
    
    # Map workflow_type to source_type for display
    source_type = 'SEC' if workflow_type == 'SEC' else 'Upload'
    
    # Generate title from metadata
    title = _generate_title(workflow_type, metadata)
    
    # Build preview object
    preview = {
        'chat_id': chat_id,
        'title': title,
        'source_type': source_type,
        'created_at': created_at,
        'metadata': metadata.copy() if isinstance(metadata, dict) else {}  # Include all polymorphic metadata
    }
    
    return preview


def get_archived_chats(query: Optional[str] = None) -> List[Dict]:
    """
    Retrieves all archived conversations (where is_active is False).
    Returns a list of preview objects suitable for the Past Chats landing page.
    
    Args:
        query: Optional search string to filter by company name (case-insensitive)
    
    Returns:
        List[Dict]: List of preview objects, each containing:
            - chat_id: The conversation ID
            - title: Generated title (e.g., "Apple Inc. - 10-K (2024-01-15)")
            - source_type: Either 'SEC' or 'Upload'
            - created_at: Creation timestamp
            - metadata: Full polymorphic metadata (Company Name, Year, CIK, etc.)
    
    Results are sorted by created_at descending (newest first).
    
    Raises:
        Exception: If database query fails
    """
    try:
        db = get_database()
        collection = db[CONVERSATIONS_COLLECTION]
        
        # Build query filter: is_active = False (archived chats only)
        filter_query = {'is_active': False}
        
        # Add company name filter if query is provided and not empty
        if query and query.strip():
            # Case-insensitive search on metadata.company field
            filter_query['metadata.company'] = {'$regex': query.strip(), '$options': 'i'}
        
        # Find all archived conversations, sorted by created_at descending
        cursor = collection.find(filter_query).sort('created_at', -1)
        
        # Convert to preview objects
        previews = []
        for conversation in cursor:
            try:
                # Convert ObjectId to string
                conversation['_id'] = str(conversation['_id'])
                preview = _convert_to_preview(conversation)
                previews.append(preview)
            except (KeyError, TypeError) as e:
                # Skip conversations with invalid structure
                continue
        
        return previews
    
    except Exception as e:
        # Re-raise with context for debugging
        raise Exception(f"Failed to retrieve archived chats: {e}") from e


def get_chat_details(chat_id: str) -> Optional[Dict]:
    """
    Retrieves the full conversation log (all messages) for a specific chat.
    
    Args:
        chat_id: The conversation ID
    
    Returns:
        Optional[Dict]: Full conversation document with messages array, or None if not found.
            The returned dict includes:
            - _id: chat_id (as string)
            - workflow_type: 'SEC' or 'UPLOAD'
            - metadata: Polymorphic metadata
            - messages: Full array of message objects [{ role, content, timestamp }, ...]
            - is_active: Boolean status
            - created_at: Creation timestamp
            - updated_at: Last update timestamp
    
    Raises:
        ValueError: If chat_id format is invalid or empty
        Exception: If database query fails
    """
    # Validate input
    if not chat_id or not isinstance(chat_id, str) or not chat_id.strip():
        raise ValueError("chat_id cannot be empty")
    
    try:
        db = get_database()
        collection = db[CONVERSATIONS_COLLECTION]
        
        from bson import ObjectId
        from bson.errors import InvalidId
        
        try:
            # Convert string chat_id to ObjectId
            object_id = ObjectId(chat_id.strip())
        except InvalidId:
            raise ValueError(f"Invalid chat_id format: {chat_id}")
        
        # Find the conversation
        conversation = collection.find_one({'_id': object_id})
        
        if not conversation:
            return None
        
        # Convert ObjectId to string for JSON serialization
        conversation['_id'] = str(conversation['_id'])
        
        # Ensure messages field exists (defensive programming)
        if 'messages' not in conversation:
            conversation['messages'] = []
        
        # Ensure metadata is a dict
        if 'metadata' not in conversation or not isinstance(conversation.get('metadata'), dict):
            conversation['metadata'] = {}
        
        return conversation
    
    except ValueError:
        # Re-raise ValueError as-is
        raise
    except Exception as e:
        # Re-raise with context for debugging
        raise Exception(f"Failed to retrieve chat details: {e}") from e

