"""
Google Docs MCP Server

This module implements an MCP server for Google Docs integration using FastMCP.
It provides tools to interact with Google Docs for document management and manipulation.
"""

import os
from typing import Any, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
import httpx

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("Google Docs MCP Server")

# Google API configuration
GOOGLE_ACCESS_TOKEN = os.getenv("GOOGLE_ACCESS_TOKEN")
DOCS_API_BASE = "https://docs.googleapis.com/v1"
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"


def get_access_token() -> str:
    """
    Get Google access token from environment.

    Returns:
        str: Google OAuth access token

    Raises:
        ValueError: If GOOGLE_ACCESS_TOKEN is not set
    """
    token = os.getenv("GOOGLE_ACCESS_TOKEN")
    if not token:
        raise ValueError(
            "Missing GOOGLE_ACCESS_TOKEN environment variable. "
            "Please set it in your .env file or environment."
        )
    return token


async def make_api_request(
    method: str, 
    url: str, 
    headers: dict[str, str] | None = None,
    **kwargs
) -> dict[str, Any] | bytes | None:
    """
    Make authenticated request to Google API.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Full URL to request
        headers: Optional headers to include
        **kwargs: Additional arguments for httpx request

    Returns:
        Response data as dict or bytes, or None on error
    """
    token = get_access_token()
    
    default_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    if headers:
        default_headers.update(headers)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await getattr(client, method.lower())(
                url, 
                headers=default_headers, 
                **kwargs
            )
            response.raise_for_status()
            
            # Return bytes for binary content (exports)
            if response.headers.get("content-type", "").startswith("application/"):
                return response.content
            
            # Return JSON for structured data
            return response.json()
            
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        raise Exception(f"Google API error {e.response.status_code}: {error_detail}")
    except Exception as e:
        raise Exception(f"Request failed: {str(e)}")


@mcp.tool()
async def list_documents(max_results: int = 10) -> dict[str, Any]:
    """
    List user's Google Docs documents.

    Args:
        max_results: Maximum number of documents to return (default: 10, max: 1000)

    Returns:
        Dictionary containing:
        - files: List of documents with id, name, createdTime, modifiedTime, webViewLink
        - message: Success message with count
    """
    try:
        params = {
            "q": "mimeType='application/vnd.google-apps.document'",
            "pageSize": min(max_results, 1000),
            "fields": "files(id,name,createdTime,modifiedTime,webViewLink,thumbnailLink,owners)"
        }

        result = await make_api_request(
            "GET",
            f"{DRIVE_API_BASE}/files",
            params=params
        )

        files = result.get("files", [])
        
        return {
            "files": files,
            "count": len(files),
            "message": f"Successfully listed {len(files)} documents"
        }

    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to list documents"
        }


@mcp.tool()
async def get_document(document_id: str) -> dict[str, Any]:
    """
    Get detailed content and structure of a Google Docs document.

    Args:
        document_id: The Google Docs document ID

    Returns:
        Dictionary containing:
        - documentId: Document ID
        - title: Document title
        - body: Document body with content structure
        - message: Success message
    """
    try:
        result = await make_api_request(
            "GET",
            f"{DOCS_API_BASE}/documents/{document_id}"
        )

        return {
            "documentId": result.get("documentId"),
            "title": result.get("title"),
            "body": result.get("body"),
            "message": f"Successfully retrieved document: {result.get('title')}"
        }

    except Exception as e:
        return {
            "error": str(e),
            "document_id": document_id,
            "message": f"Failed to retrieve document {document_id}"
        }


@mcp.tool()
async def create_document(title: str) -> dict[str, Any]:
    """
    Create a new Google Docs document.

    Args:
        title: Title for the new document

    Returns:
        Dictionary containing:
        - documentId: ID of created document
        - title: Document title
        - webViewLink: URL to view the document
        - message: Success message
    """
    try:
        document_data = {
            "title": title
        }

        result = await make_api_request(
            "POST",
            f"{DOCS_API_BASE}/documents",
            json=document_data
        )

        doc_id = result.get("documentId")
        
        # Get the web view link from Drive API
        drive_info = await make_api_request(
            "GET",
            f"{DRIVE_API_BASE}/files/{doc_id}",
            params={"fields": "webViewLink"}
        )

        return {
            "documentId": doc_id,
            "title": result.get("title"),
            "webViewLink": drive_info.get("webViewLink"),
            "message": f"Successfully created document: {title}"
        }

    except Exception as e:
        return {
            "error": str(e),
            "title": title,
            "message": f"Failed to create document '{title}'"
        }


@mcp.tool()
async def insert_text(
    document_id: str, 
    text: str, 
    index: int = 1
) -> dict[str, Any]:
    """
    Insert text into a Google Docs document at specified position.

    Args:
        document_id: The Google Docs document ID
        text: Text content to insert
        index: Position to insert text (default: 1, which is the start of document)

    Returns:
        Dictionary containing:
        - documentId: Document ID
        - message: Success message
        - replies: API response with updated document info
    """
    try:
        requests_data = {
            "requests": [
                {
                    "insertText": {
                        "location": {"index": index},
                        "text": text
                    }
                }
            ]
        }

        result = await make_api_request(
            "POST",
            f"{DOCS_API_BASE}/documents/{document_id}:batchUpdate",
            json=requests_data
        )

        return {
            "documentId": document_id,
            "message": f"Successfully inserted text at position {index}",
            "replies": result.get("replies", [])
        }

    except Exception as e:
        return {
            "error": str(e),
            "document_id": document_id,
            "message": f"Failed to insert text into document {document_id}"
        }


@mcp.tool()
async def replace_text(
    document_id: str, 
    old_text: str, 
    new_text: str
) -> dict[str, Any]:
    """
    Replace all occurrences of text in a Google Docs document.

    Args:
        document_id: The Google Docs document ID
        old_text: Text to find and replace
        new_text: Replacement text

    Returns:
        Dictionary containing:
        - documentId: Document ID
        - message: Success message
        - occurrences_changed: Number of replacements made
    """
    try:
        requests_data = {
            "requests": [
                {
                    "replaceAllText": {
                        "containsText": {
                            "text": old_text,
                            "matchCase": False
                        },
                        "replaceText": new_text
                    }
                }
            ]
        }

        result = await make_api_request(
            "POST",
            f"{DOCS_API_BASE}/documents/{document_id}:batchUpdate",
            json=requests_data
        )

        # Extract number of occurrences changed from response
        occurrences = 0
        replies = result.get("replies", [])
        if replies and "replaceAllText" in replies[0]:
            occurrences = replies[0]["replaceAllText"].get("occurrencesChanged", 0)

        return {
            "documentId": document_id,
            "message": f"Successfully replaced {occurrences} occurrence(s) of '{old_text}' with '{new_text}'",
            "occurrences_changed": occurrences
        }

    except Exception as e:
        return {
            "error": str(e),
            "document_id": document_id,
            "message": f"Failed to replace text in document {document_id}"
        }


@mcp.tool()
async def format_text(
    document_id: str,
    start_index: int,
    end_index: int,
    bold: bool | None = None,
    italic: bool | None = None,
    underline: bool | None = None
) -> dict[str, Any]:
    """
    Format text in a Google Docs document.

    Args:
        document_id: The Google Docs document ID
        start_index: Start position of text to format
        end_index: End position of text to format
        bold: Make text bold (optional)
        italic: Make text italic (optional)
        underline: Make text underlined (optional)

    Returns:
        Dictionary containing:
        - documentId: Document ID
        - message: Success message
        - formatting_applied: List of formatting options applied
    """
    try:
        text_style = {}
        formatting_applied = []
        
        if bold is not None:
            text_style["bold"] = bold
            formatting_applied.append(f"bold={bold}")
        if italic is not None:
            text_style["italic"] = italic
            formatting_applied.append(f"italic={italic}")
        if underline is not None:
            text_style["underline"] = underline
            formatting_applied.append(f"underline={underline}")

        if not text_style:
            return {
                "error": "No formatting options provided",
                "document_id": document_id,
                "message": "At least one formatting option (bold, italic, underline) must be specified"
            }

        requests_data = {
            "requests": [
                {
                    "updateTextStyle": {
                        "range": {
                            "startIndex": start_index,
                            "endIndex": end_index
                        },
                        "textStyle": text_style,
                        "fields": ",".join(text_style.keys())
                    }
                }
            ]
        }

        result = await make_api_request(
            "POST",
            f"{DOCS_API_BASE}/documents/{document_id}:batchUpdate",
            json=requests_data
        )

        return {
            "documentId": document_id,
            "message": f"Successfully formatted text from index {start_index} to {end_index}",
            "formatting_applied": formatting_applied
        }

    except Exception as e:
        return {
            "error": str(e),
            "document_id": document_id,
            "message": f"Failed to format text in document {document_id}"
        }


@mcp.tool()
async def insert_image(
    document_id: str, 
    image_url: str, 
    index: int = 1
) -> dict[str, Any]:
    """
    Insert an image into a Google Docs document.

    Args:
        document_id: The Google Docs document ID
        image_url: Publicly accessible URL of the image to insert
        index: Position to insert image (default: 1, which is the start of document)

    Returns:
        Dictionary containing:
        - documentId: Document ID
        - message: Success message
        - image_url: URL of inserted image
    """
    try:
        requests_data = {
            "requests": [
                {
                    "insertInlineImage": {
                        "location": {"index": index},
                        "uri": image_url
                    }
                }
            ]
        }

        result = await make_api_request(
            "POST",
            f"{DOCS_API_BASE}/documents/{document_id}:batchUpdate",
            json=requests_data
        )

        return {
            "documentId": document_id,
            "message": f"Successfully inserted image at position {index}",
            "image_url": image_url
        }

    except Exception as e:
        return {
            "error": str(e),
            "document_id": document_id,
            "message": f"Failed to insert image into document {document_id}"
        }


@mcp.tool()
async def export_document(
    document_id: str, 
    export_format: str = "pdf"
) -> dict[str, Any]:
    """
    Export a Google Docs document to specified format.

    Args:
        document_id: The Google Docs document ID
        export_format: Export format (pdf, docx, odt, rtf, txt, html, epub). Default: pdf

    Returns:
        Dictionary containing:
        - documentId: Document ID
        - format: Export format used
        - content_length: Size of exported content in bytes
        - message: Success message
        - download_info: Information about how to download (note: actual bytes not returned in MCP response)
    """
    try:
        mime_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "odt": "application/vnd.oasis.opendocument.text",
            "rtf": "application/rtf",
            "txt": "text/plain",
            "html": "text/html",
            "epub": "application/epub+zip"
        }

        if export_format not in mime_types:
            return {
                "error": f"Unsupported export format: {export_format}",
                "supported_formats": list(mime_types.keys()),
                "message": f"Format '{export_format}' is not supported"
            }

        mime_type = mime_types[export_format]
        
        content = await make_api_request(
            "GET",
            f"{DRIVE_API_BASE}/files/{document_id}/export",
            params={"mimeType": mime_type}
        )

        content_length = len(content) if isinstance(content, bytes) else 0

        return {
            "documentId": document_id,
            "format": export_format,
            "content_length": content_length,
            "message": f"Successfully exported document as {export_format} ({content_length} bytes)",
            "download_info": "Export completed. Content available via Google Drive API."
        }

    except Exception as e:
        return {
            "error": str(e),
            "document_id": document_id,
            "message": f"Failed to export document {document_id}"
        }


@mcp.tool()
async def delete_document(document_id: str) -> dict[str, Any]:
    """
    Delete a Google Docs document (moves to trash).

    Args:
        document_id: The Google Docs document ID to delete

    Returns:
        Dictionary containing:
        - documentId: Document ID
        - message: Success message
    """
    try:
        await make_api_request(
            "DELETE",
            f"{DRIVE_API_BASE}/files/{document_id}"
        )

        return {
            "documentId": document_id,
            "message": f"Successfully deleted document {document_id}"
        }

    except Exception as e:
        return {
            "error": str(e),
            "document_id": document_id,
            "message": f"Failed to delete document {document_id}"
        }


if __name__ == "__main__":
    mcp.run()

