"""
FinScope API Server - FastAPI Backend for React Frontend

This API server exposes the FinScope functionality as REST endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
import history_manager

# Import Flask app from master_controller (rename to avoid conflict)
from master_controller import app as flask_app

# Create FastAPI app
app = FastAPI(
    title="FinScope API",
    description="Financial Document Analysis Platform API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoints (both with and without /api prefix)
@app.get("/health")
async def health_check_direct():
    """Health check endpoint (direct access)"""
    return {"status": "online"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify the API is running"""
    return {"status": "online"}


# FastAPI routes with /api prefix - these are checked BEFORE the Flask mount
@app.get("/api/history/recent")
async def get_recent_history_endpoint(query: Optional[str] = None):
    """
    Get recent/archived chat history with full message history.
    
    Args:
        query: Optional search string to filter by company name (case-insensitive)
    
    Returns:
        List of chat objects, each containing:
            - company_name: Company name
            - ticker: Ticker symbol (if available, otherwise null)
            - type: Either 'sec' or 'upload'
            - timestamp: Creation timestamp (ISO format string)
            - session_id: Chat/conversation ID
            - metadata: Full metadata object
            - chats: Array of message objects with role, content, and timestamp
    """
    try:
        chats = history_manager.get_recent_history(query=query)
        return chats
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to retrieve recent history: {str(e)}")


@app.get("/api/history/chat/{session_id}")
async def get_chat_detail_endpoint(session_id: str):
    """
    Get full chat details for a specific session.
    
    Args:
        session_id: The chat/conversation ID
    
    Returns:
        Chat detail object containing:
            - _id: chat_id (as string)
            - workflow_type: 'SEC' or 'UPLOAD'
            - metadata: Polymorphic metadata
            - messages: Full array of message objects [{ role, content, timestamp }, ...]
            - created_at: Creation timestamp
            - updated_at: Last update timestamp
    """
    try:
        chat_details = history_manager.get_chat_details(session_id)
        if not chat_details:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found")
        return chat_details
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat details: {str(e)}")


@app.delete("/api/history/chat/{session_id}")
async def delete_chat_endpoint(session_id: str):
    """
    Delete a chat conversation permanently from the database.
    
    Args:
        session_id: The chat/conversation ID to delete
    
    Returns:
        JSON response with success status and message
    """
    try:
        deleted = history_manager.delete_chat(session_id)
        if not deleted:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found")
        return {"success": True, "message": f"Chat session {session_id} deleted successfully"}
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to delete chat: {str(e)}")


# Mount Flask app (Master Controller) at /api
# FastAPI routes are checked first, then unmatched /api/* requests go to Flask
# Flask routes are at /search-company and /get-filings (no /api prefix)
app.mount("/api", WSGIMiddleware(flask_app))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)

