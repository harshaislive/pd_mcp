import asyncio
import json
import httpx
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from fastmcp import FastMCP
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("📄 .env file loaded")

# Load configuration
def load_config():
    domain = os.getenv("PIPEDRIVE_DOMAIN")
    api_key = os.getenv("PIPEDRIVE_API_KEY")
    db_url = os.getenv("DATABASE_URL")
    
    if not all([domain, api_key, db_url]):
        logger.error("⚠️  Missing configuration! Please set PIPEDRIVE_DOMAIN, PIPEDRIVE_API_KEY, and DATABASE_URL environment variables")
        return {
            "domain": "your-company-domain",
            "api_key": "your_api_key_here",
            "db_url": "postgresql://user:pass@host:5432/db"
        }
    
    logger.info("✅ Configuration loaded from environment variables")
    return {
        "domain": domain,
        "api_key": api_key,
        "db_url": db_url
    }

CONFIG = load_config()

# Initialize FastMCP server with custom error handling
class PipedriveMCP(FastMCP):
    async def handle_error(self, error: Exception) -> Dict[str, Any]:
        """Custom error handler for FastMCP"""
        logger.error(f"Error in request: {str(error)}")
        if isinstance(error, json.JSONDecodeError):
            return {
                "code": -32700,
                "message": f"Parse error: {str(error)}"
            }
        elif isinstance(error, ValueError):
            return {
                "code": -32600,
                "message": f"Invalid Request: {str(error)}"
            }
        else:
            return {
                "code": -32603,
                "message": f"Internal error: {str(error)}"
            }

mcp = PipedriveMCP(name="Pipedrive PostgreSQL MCP Server")

# ========================
# DATABASE CONNECTION
# ========================

def get_db_connection():
    """Create a new database connection with retry logic"""
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                CONFIG["db_url"], 
                cursor_factory=RealDictCursor,
                connect_timeout=10
            )
            # Test the connection
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return conn
        except Exception as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                raise

# Test database connection on startup
try:
    with get_db_connection() as conn:
        logger.info("✅ Database connection successful")
except Exception as e:
    logger.error(f"❌ Database connection failed: {str(e)}")
    logger.error("Please check your DATABASE_URL environment variable")

# ========================
# PIPEDRIVE API CLIENT
# ========================

class PipedriveClient:
    def __init__(self):
        self.base_url = f"https://{CONFIG['domain']}.pipedrive.com/api/v1"
        self.api_key = CONFIG['api_key']
        self.client = None
        self._lock = asyncio.Lock()
    
    async def get_client(self):
        async with self._lock:
            if self.client is None:
                self.client = httpx.AsyncClient(
                    timeout=30.0,
                    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
                )
            return self.client
    
    async def close(self):
        async with self._lock:
            if self.client:
                await self.client.aclose()
                self.client = None
    
    async def make_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict] = None,
        json_body: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        if params is None:
            params = {}
        params['api_token'] = self.api_key
        
        url = f"{self.base_url}{endpoint}"
        client = await self.get_client()
        
        try:
            if method == "GET":
                response = await client.get(url, params=params)
            elif method == "POST":
                response = await client.post(url, params=params, json=json_body)
            elif method == "PUT":
                response = await client.put(url, params=params, json=json_body)
            elif method == "DELETE":
                response = await client.delete(url, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            raise

pipedrive_client = PipedriveClient()

# ========================
# NOTE MANAGEMENT (via API)
# ========================

@mcp.tool()
async def add_note_to_deal(deal_id: int, content: str) -> str:
    """
    Adds a new note to a specific deal.
    
    Args:
        deal_id: The ID of the deal to add the note to
        content: The content of the note in HTML or plain text
    
    Returns:
        JSON string containing the details of the created note
    """
    try:
        json_body = {
            "deal_id": deal_id,
            "content": content
        }
        response = await pipedrive_client.make_api_request("/notes", method="POST", json_body=json_body)
        return json.dumps(response, indent=2)
    except Exception as e:
        logger.error(f"Error adding note to deal: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def update_note(note_id: int, content: str) -> str:
    """
    Updates an existing note.
    
    Args:
        note_id: The ID of the note to update
        content: The new content of the note in HTML or plain text
    
    Returns:
        JSON string containing the details of the updated note
    """
    try:
        json_body = {
            "content": content
        }
        response = await pipedrive_client.make_api_request(f"/notes/{note_id}", method="PUT", json_body=json_body)
        return json.dumps(response, indent=2)
    except Exception as e:
        logger.error(f"Error updating note: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def delete_note(note_id: int) -> str:
    """
    Deletes an existing note.
    
    Args:
        note_id: The ID of the note to delete
    
    Returns:
        JSON string containing the response from the API
    """
    try:
        response = await pipedrive_client.make_api_request(f"/notes/{note_id}", method="DELETE")
        return json.dumps(response, indent=2)
    except Exception as e:
        logger.error(f"Error deleting note: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

# ========================
# POSTGRESQL QUERIES
# ========================

@mcp.tool()
async def query_deals(sql: str) -> str:
    """
    Run a custom SQL query on the deals table.
    
    Args:
        sql: SQL query to execute (must be read-only)
    
    Returns:
        JSON string containing the query results
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Ensure query is read-only
                sql_lower = sql.lower().strip()
                if not sql_lower.startswith("select"):
                    logger.warning("Attempted to execute non-SELECT query")
                    return json.dumps({
                        "success": False,
                        "error": "Only SELECT queries are allowed"
                    }, indent=2)
                
                cur.execute(sql)
                results = cur.fetchall()
                return json.dumps({
                    "success": True,
                    "data": results
                }, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def get_todays_deals() -> str:
    """
    Get all deals created or updated today.
    
    Returns:
        JSON string containing today's deals
    """
    try:
        sql = """
        SELECT 
            d.*,
            p.name as person_name,
            o.name as org_name,
            u.name as owner_name
        FROM deals d
        LEFT JOIN persons p ON d.person_id = p.id
        LEFT JOIN organizations o ON d.org_id = o.id
        LEFT JOIN users u ON d.user_id = u.id
        WHERE DATE(d.add_time) = CURRENT_DATE 
           OR DATE(d.update_time) = CURRENT_DATE
        ORDER BY d.update_time DESC
        """
        return await query_deals(sql)
    except Exception as e:
        logger.error(f"Error getting today's deals: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def get_pipeline_summary() -> str:
    """
    Get a summary of all pipelines with deal counts and values.
    
    Returns:
        JSON string containing pipeline summaries
    """
    try:
        sql = """
        SELECT 
            p.name as pipeline_name,
            s.name as stage_name,
            COUNT(d.id) as deal_count,
            SUM(d.value) as total_value,
            AVG(d.value) as avg_value
        FROM pipelines p
        LEFT JOIN stages s ON s.pipeline_id = p.id
        LEFT JOIN deals d ON d.stage_id = s.id
        WHERE d.status = 'open'
        GROUP BY p.name, s.name
        ORDER BY p.name, s.name
        """
        return await query_deals(sql)
    except Exception as e:
        logger.error(f"Error getting pipeline summary: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def get_sales_performance() -> str:
    """
    Get sales performance metrics by owner.
    
    Returns:
        JSON string containing performance metrics
    """
    try:
        sql = """
        SELECT 
            u.name as owner_name,
            COUNT(CASE WHEN d.status = 'won' THEN 1 END) as won_deals,
            COUNT(CASE WHEN d.status = 'lost' THEN 1 END) as lost_deals,
            SUM(CASE WHEN d.status = 'won' THEN d.value ELSE 0 END) as won_value,
            AVG(CASE WHEN d.status = 'won' THEN d.value END) as avg_deal_size,
            COUNT(CASE WHEN d.status = 'open' THEN 1 END) as open_deals
        FROM users u
        LEFT JOIN deals d ON d.user_id = u.id
        WHERE d.add_time >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY u.name
        ORDER BY won_value DESC
        """
        return await query_deals(sql)
    except Exception as e:
        logger.error(f"Error getting sales performance: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

# ========================
# SERVER STARTUP
# ========================

async def run_server():
    """Start the FastMCP server"""
    try:
        host = "0.0.0.0"
        port = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8000")))
        
        logger.info(f"🚀 Starting Pipedrive PostgreSQL MCP Server")
        logger.info(f"📋 Server running on http://{host}:{port}")
        
        try:
            await mcp.run_sse_async(
                host=host, 
                port=port, 
                path="/sse",
                ping_interval=30  # Send ping every 30 seconds to keep connection alive
            )
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            raise
        finally:
            # Cleanup
            await pipedrive_client.close()
            logger.info("Server shutdown complete")
        
    except Exception as e:
        logger.error(f"❌ Server failed to start: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise 