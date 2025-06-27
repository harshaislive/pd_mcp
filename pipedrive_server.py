import asyncio
import json
import httpx
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastmcp import FastMCP

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("📄 .env file loaded")
except ImportError:
    print("📄 python-dotenv not installed, skipping .env file loading")

# Load configuration from environment variables
def load_config():
    domain = os.getenv("PIPEDRIVE_DOMAIN")
    api_key = os.getenv("PIPEDRIVE_API_KEY")
    
    if not domain or not api_key:
        print("⚠️  No configuration found! Please set PIPEDRIVE_DOMAIN and PIPEDRIVE_API_KEY environment variables")
        return {
            "domain": "your-company-domain",
            "api_key": "your_api_key_here"
        }
    
    print("✅ Configuration loaded from environment variables")
    return {
        "domain": domain,
        "api_key": api_key
    }

PIPEDRIVE_CONFIG = load_config()

class PipedriveClient:
    def __init__(self):
        self.base_url = f"https://{PIPEDRIVE_CONFIG['domain']}.pipedrive.com/api/v1"
        self.api_key = PIPEDRIVE_CONFIG['api_key']
        self.client = httpx.AsyncClient()
    
    async def make_api_request(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make an authenticated request to Pipedrive API"""
        
        # Add API key to parameters
        if params is None:
            params = {}
        params['api_token'] = self.api_key
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = await self.client.get(url, params=params)
            elif method == "POST":
                response = await self.client.post(url, params=params)
            elif method == "PUT":
                response = await self.client.put(url, params=params)
            elif method == "DELETE":
                response = await self.client.delete(url, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            raise Exception(f"API request failed: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")

# Initialize Pipedrive client
pipedrive_client = PipedriveClient()

# Initialize FastMCP server
mcp = FastMCP(name="Pipedrive MCP Server")

# PHASE 1: BASIC DATA RETRIEVAL TOOLS

@mcp.tool()
async def get_pipelines() -> str:
    """
    Get all pipelines from Pipedrive.
    
    Returns:
        JSON string containing list of all pipelines with their details
    """
    try:
        response = await pipedrive_client.make_api_request("/pipelines")
        return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error fetching pipelines: {str(e)}"

@mcp.tool()
async def get_deals(status: str = "all_not_deleted", limit: int = 100) -> str:
    """
    Get deals from Pipedrive with optional status filtering.
    
    Args:
        status: Deal status (open, won, lost, deleted, all_not_deleted) - default is 'all_not_deleted'
        limit: Number of deals to return (max 500) - default is 100
    
    Returns:
        JSON string containing list of deals with their details
    """
    try:
        params = {
            "limit": min(limit, 500),
            "status": status
        }
        response = await pipedrive_client.make_api_request("/deals", params=params)
        return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error fetching deals: {str(e)}"

@mcp.tool()
async def get_deal_details(deal_id: int) -> str:
    """
    Get detailed information about a specific deal.
    
    Args:
        deal_id: The ID of the deal to fetch details for
    
    Returns:
        JSON string containing detailed deal information
    """
    try:
        response = await pipedrive_client.make_api_request(f"/deals/{deal_id}")
        return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error fetching deal details: {str(e)}"

@mcp.tool()
async def get_deal_flow(deal_id: int) -> str:
    """
    Get the flow/timeline of a deal including stage changes and history.
    
    Args:
        deal_id: The ID of the deal to get flow for
    
    Returns:
        JSON string containing deal flow with stage change history
    """
    try:
        response = await pipedrive_client.make_api_request(f"/deals/{deal_id}/flow")
        return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error fetching deal flow: {str(e)}"

@mcp.tool()
async def get_deal_activities(deal_id: int) -> str:
    """
    Get all activities associated with a specific deal.
    
    Args:
        deal_id: The ID of the deal to get activities for
    
    Returns:
        JSON string containing all activities linked to the deal
    """
    try:
        response = await pipedrive_client.make_api_request(f"/deals/{deal_id}/activities")
        return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error fetching deal activities: {str(e)}"

@mcp.tool()
async def get_users() -> str:
    """
    Get all users from your Pipedrive account.
    
    Returns:
        JSON string containing list of all users with their details
    """
    try:
        response = await pipedrive_client.make_api_request("/users")
        return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error fetching users: {str(e)}"

@mcp.tool()
async def get_stages(pipeline_id: Optional[int] = None) -> str:
    """
    Get all stages, optionally filtered by pipeline.
    
    Args:
        pipeline_id: Optional pipeline ID to filter stages for specific pipeline
    
    Returns:
        JSON string containing list of stages
    """
    try:
        params = {}
        if pipeline_id:
            params["pipeline_id"] = pipeline_id
        response = await pipedrive_client.make_api_request("/stages", params=params)
        return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error fetching stages: {str(e)}"

# OVERDUE ACTIVITIES & RESPONSIBLE USERS

@mcp.tool()
async def get_overdue_activities() -> str:
    """
    Get all overdue activities and the users responsible for them.
    Only includes activities from open deals or activities not linked to any deal.
    
    Returns:
        JSON string containing overdue activities with user details
    """
    try:
        # Get current date in YYYY-MM-DD format
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get all activities that are due before today and not done
        params = {
            "done": 0,  # Not completed
            "limit": 500
        }
        response = await pipedrive_client.make_api_request("/activities", params=params)
        
        if response.get("success") and response.get("data"):
            # Filter for overdue activities (due_date < today)
            overdue_activities = []
            activities_from_lost_deals = 0
            
            for activity in response["data"]:
                due_date = activity.get("due_date")
                if due_date and due_date < today:
                    deal_id = activity.get("deal_id")
                    
                    # If activity has no deal_id, include it
                    if not deal_id:
                        overdue_activities.append(activity)
                    else:
                        # Check if the deal is open
                        try:
                            deal_response = await pipedrive_client.make_api_request(f"/deals/{deal_id}")
                            if deal_response.get("success") and deal_response.get("data"):
                                deal_status = deal_response["data"].get("status")
                                # Only include activities from open deals
                                if deal_status == "open":
                                    overdue_activities.append(activity)
                                else:
                                    activities_from_lost_deals += 1
                        except:
                            # If we can't fetch deal info, include the activity to be safe
                            overdue_activities.append(activity)
            
            # Add count summary
            result = {
                "success": True,
                "overdue_count": len(overdue_activities),
                "total_activities_checked": len(response["data"]),
                "activities_from_lost_deals_excluded": activities_from_lost_deals,
                "note": "Only includes overdue activities from open deals or activities not linked to deals",
                "data": overdue_activities
            }
            
            return json.dumps(result, indent=2)
        else:
            return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error fetching overdue activities: {str(e)}"

@mcp.tool()
async def get_overdue_summary_by_user() -> str:
    """
    Get summary of overdue activities grouped by user.
    Only includes activities from open deals or activities not linked to any deal.
    
    Returns:
        JSON string containing overdue activity counts per user
    """
    try:
        # Get current date in YYYY-MM-DD format
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get all activities that are not done
        params = {
            "done": 0,  # Not completed
            "limit": 500
        }
        response = await pipedrive_client.make_api_request("/activities", params=params)
        
        if response.get("success") and response.get("data"):
            # Group overdue activities by user
            user_overdue_count = {}
            total_overdue = 0
            activities_from_lost_deals_excluded = 0
            
            for activity in response["data"]:
                due_date = activity.get("due_date")
                if due_date and due_date < today:
                    deal_id = activity.get("deal_id")
                    include_activity = False
                    
                    # If activity has no deal_id, include it
                    if not deal_id:
                        include_activity = True
                    else:
                        # Check if the deal is open
                        try:
                            deal_response = await pipedrive_client.make_api_request(f"/deals/{deal_id}")
                            if deal_response.get("success") and deal_response.get("data"):
                                deal_status = deal_response["data"].get("status")
                                # Only include activities from open deals
                                if deal_status == "open":
                                    include_activity = True
                                else:
                                    activities_from_lost_deals_excluded += 1
                        except:
                            # If we can't fetch deal info, include the activity to be safe
                            include_activity = True
                    
                    if include_activity:
                        total_overdue += 1
                        user_id = activity.get("user_id")
                        user_name = activity.get("assignee_name", f"User {user_id}")
                        
                        if user_id not in user_overdue_count:
                            user_overdue_count[user_id] = {
                                "user_name": user_name,
                                "user_id": user_id,
                                "overdue_count": 0,
                                "activities": []
                            }
                        
                        user_overdue_count[user_id]["overdue_count"] += 1
                        user_overdue_count[user_id]["activities"].append({
                            "id": activity.get("id"),
                            "subject": activity.get("subject"),
                            "due_date": activity.get("due_date"),
                            "type": activity.get("type"),
                            "deal_id": deal_id,
                            "deal_title": activity.get("deal_title")
                        })
            
            result = {
                "success": True,
                "total_overdue_activities": total_overdue,
                "users_with_overdue": len(user_overdue_count),
                "activities_from_lost_deals_excluded": activities_from_lost_deals_excluded,
                "note": "Only includes overdue activities from open deals or activities not linked to deals",
                "user_summary": list(user_overdue_count.values())
            }
            
            return json.dumps(result, indent=2)
        else:
            return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error fetching overdue summary: {str(e)}"

# DEALS WITH NO ACTIVITIES

@mcp.tool()
async def get_deals_with_no_activities(status: str = "open", limit: int = 100) -> str:
    """
    Find deals that have no activities associated with them.
    
    Args:
        status: Deal status to check (open, won, lost, all_not_deleted) - default is 'open'
        limit: Number of deals to check (max 500) - default is 100
    
    Returns:
        JSON string containing deals with no activities
    """
    try:
        # First get deals
        params = {
            "limit": min(limit, 500),
            "status": status
        }
        deals_response = await pipedrive_client.make_api_request("/deals", params=params)
        
        if not deals_response.get("success") or not deals_response.get("data"):
            return json.dumps(deals_response, indent=2)
        
        deals_with_no_activities = []
        total_deals_checked = len(deals_response["data"])
        
        # Check each deal for activities
        for deal in deals_response["data"]:
            deal_id = deal.get("id")
            if not deal_id:
                continue
                
            try:
                activities_response = await pipedrive_client.make_api_request(f"/deals/{deal_id}/activities")
                
                # If no activities or empty activities list
                has_activities = (
                    activities_response.get("success") and 
                    activities_response.get("data") and 
                    len(activities_response["data"]) > 0
                )
                
                if not has_activities:
                    deals_with_no_activities.append({
                        "id": deal.get("id"),
                        "title": deal.get("title"),
                        "status": deal.get("status"),
                        "stage_name": deal.get("stage", {}).get("name") if deal.get("stage") else "Unknown",
                        "value": deal.get("value"),
                        "currency": deal.get("currency"),
                        "add_time": deal.get("add_time"),
                        "owner_name": deal.get("owner_name"),
                        "person_name": deal.get("person_name"),
                        "org_name": deal.get("org_name")
                    })
                    
            except Exception as activity_error:
                # If we can't fetch activities, assume no activities
                deals_with_no_activities.append({
                    "id": deal.get("id"),
                    "title": deal.get("title"),
                    "status": deal.get("status"),
                    "error": f"Could not fetch activities: {str(activity_error)}"
                })
        
        result = {
            "success": True,
            "total_deals_checked": total_deals_checked,
            "deals_with_no_activities_count": len(deals_with_no_activities),
            "percentage_without_activities": round((len(deals_with_no_activities) / total_deals_checked * 100), 2) if total_deals_checked > 0 else 0,
            "data": deals_with_no_activities
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error finding deals with no activities: {str(e)}"

# SMART TIME-RANGE FILTERING WITH CUSTOM DATES & SUMMARIZATION

@mcp.tool()
async def get_deals_summary_by_date(start_date: str = "", end_date: str = "", status: str = "open", date_filter: str = "update") -> str:
    """
    Get a SUMMARY of deals within specific date range. Returns key metrics + top 10 deals only.
    Uses Pipedrive API's native date filtering for accurate results!
    
    Args:
        start_date: Start date in YYYY-MM-DD format (default: today)
        end_date: End date in YYYY-MM-DD format (default: today)  
        status: Deal status (open, won, lost, all_not_deleted) - default is 'open'
        date_filter: Date field to filter by ('update' = last modified, 'add' = created date) - default is 'update'
    
    Returns:
        JSON string with summary metrics + top 10 deals by value
    """
    try:
        # Default to today if no dates provided
        now = datetime.now()
        if not start_date:
            start_date = now.strftime("%Y-%m-%d")
        if not end_date:
            end_date = now.strftime("%Y-%m-%d")
        
        # Validate date format
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return f"Error: Please use YYYY-MM-DD format for dates. Example: 2025-01-15"
        
        # Convert dates to RFC3339 format for API (add time component)
        start_datetime = f"{start_date}T00:00:00Z"
        end_datetime = f"{end_date}T23:59:59Z"
        
        # Get deals using API's native date filtering
        all_deals = []
        total_value = 0
        stage_counts = {}
        owner_counts = {}
        
        cursor = None
        requests_made = 0
        
        while requests_made < 10:  # Limit API calls
            requests_made += 1
            
            # Use API v2 with native date filtering
            params = {
                "limit": 500, 
                "status": status,
                "sort_by": "update_time",
                "sort_direction": "desc"
            }
            
            # Add native API date filtering based on date_filter type
            if date_filter == "update":
                params["updated_since"] = start_datetime
                params["updated_until"] = end_datetime
            # For other filters, we'll still need client-side filtering since API only supports update_time natively
            
            if cursor:
                params["cursor"] = cursor
                
            try:
                # Use API v2 deals endpoint with native filtering
                response = await pipedrive_client.make_api_request("/api/v2/deals", params=params)
            except:
                # Fallback to v1 if v2 fails
                response = await pipedrive_client.make_api_request("/deals", params=params)
            
            if not response.get("success") or not response.get("data"):
                break
            
            # Process deals and calculate metrics
            for deal in response["data"]:
                # For update filter, API already filtered for us
                if date_filter == "update":
                    include_deal = True
                    deal_date = deal.get("update_time", "").split("T")[0] if deal.get("update_time") else ""
                else:
                    # For other filters, do client-side filtering
                    if date_filter == "add":
                        date_field = deal.get("add_time", "")
                    elif date_filter == "close":
                        date_field = deal.get("close_time", "")
                    elif date_filter == "activity":
                        date_field = deal.get("last_activity_date", "")
                    else:
                        date_field = deal.get("update_time", "")
                    
                    if date_field:
                        deal_date = date_field.split("T")[0] if "T" in date_field else date_field.split(" ")[0]
                        include_deal = start_date <= deal_date <= end_date
                    else:
                        include_deal = False
                
                if include_deal:
                    # Add to summary metrics
                    value = deal.get("value", 0) or 0
                    total_value += value
                    
                    stage_name = deal.get("stage", {}).get("name", "Unknown") if deal.get("stage") else "Unknown"
                    stage_counts[stage_name] = stage_counts.get(stage_name, 0) + 1
                    
                    owner_name = deal.get("owner_name", "Unknown")
                    owner_counts[owner_name] = owner_counts.get(owner_name, 0) + 1
                    
                    # Keep deal for top 10 list
                    all_deals.append({
                        "id": deal.get("id"),
                        "title": deal.get("title"),
                        "value": value,
                        "currency": deal.get("currency"),
                        "stage": stage_name,
                        "owner": owner_name,
                        "person": deal.get("person_name"),
                        "org": deal.get("org_name"),
                        "filter_date": deal_date,
                        "date_type": date_filter
                    })
            
            # For native API filtering (update_time), we can trust pagination
            # For client-side filtering, we need to be more careful about pagination
            if date_filter == "update":
                # Check pagination normally
                if response.get("additional_data", {}).get("next_cursor"):
                    cursor = response["additional_data"]["next_cursor"]
                else:
                    break
            else:
                # For client-side filtering, continue until we have enough data or hit limits
                if response.get("additional_data", {}).get("next_cursor") and len(all_deals) < 200:
                    cursor = response["additional_data"]["next_cursor"]
                else:
                    break
        
        # Sort deals by value and take top 10
        top_deals = sorted(all_deals, key=lambda x: x["value"] or 0, reverse=True)[:10]
        
        # Calculate averages
        total_deals = len(all_deals)
        avg_value = total_value / total_deals if total_deals > 0 else 0
        
        result = {
            "success": True,
            "date_range": f"{start_date} to {end_date}",
            "date_filter_type": f"{date_filter} date ({date_filter}_time field)",
            "status_filter": status,
            "summary": {
                "total_deals": total_deals,
                "total_value": total_value,
                "average_value": round(avg_value, 2),
                "currency": top_deals[0]["currency"] if top_deals else "USD"
            },
            "breakdown_by_stage": dict(sorted(stage_counts.items(), key=lambda x: x[1], reverse=True)),
            "breakdown_by_owner": dict(sorted(owner_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
            "top_10_deals_by_value": top_deals,
            "note": f"Showing summary + top 10 deals out of {total_deals} total filtered by {date_filter} date. Use get_deals_list() to see specific deals."
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error fetching deals summary: {str(e)}"

@mcp.tool()
async def get_deals_list(start_date: str = "", end_date: str = "", status: str = "open", limit: int = 20, date_filter: str = "update") -> str:
    """
    Get a focused LIST of deals (just key fields) within date range.
    Returns only essential fields to minimize context usage.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (default: today)
        end_date: End date in YYYY-MM-DD format (default: today)
        status: Deal status (open, won, lost, all_not_deleted) - default is 'open'
        limit: Max number of deals to return (default: 20, max: 50)
        date_filter: Date field to filter by ('add' = created date, 'update' = last modified, 'close' = close date, 'activity' = last activity) - default is 'update'
    
    Returns:
        JSON string with focused deal list (ID, title, value, stage, owner only)
    """
    try:
        # Default to today if no dates provided
        now = datetime.now()
        if not start_date:
            start_date = now.strftime("%Y-%m-%d")
        if not end_date:
            end_date = now.strftime("%Y-%m-%d")
        
        # Limit to prevent context overload
        limit = min(limit, 50)
        
        matching_deals = []
        cursor = None
        requests_made = 0
        
        # Convert dates to RFC3339 format for API
        start_datetime = f"{start_date}T00:00:00Z"
        end_datetime = f"{end_date}T23:59:59Z"
        
        while len(matching_deals) < limit and requests_made < 5:  # Limit API calls
            requests_made += 1
            
            # Use API v2 with native date filtering when possible
            params = {
                "limit": 500, 
                "status": status,
                "sort_by": "update_time",
                "sort_direction": "desc"
            }
            
            # Add native API date filtering for update_time
            if date_filter == "update":
                params["updated_since"] = start_datetime
                params["updated_until"] = end_datetime
            
            if cursor:
                params["cursor"] = cursor
                
            try:
                # Use API v2 for better date filtering
                response = await pipedrive_client.make_api_request("/api/v2/deals", params=params)
            except:
                # Fallback to v1
                response = await pipedrive_client.make_api_request("/deals", params=params)
            
            if not response.get("success") or not response.get("data"):
                break
            
            # Filter deals by date range
            for deal in response["data"]:
                if len(matching_deals) >= limit:
                    break
                
                # For update filter, API already filtered for us
                if date_filter == "update":
                    include_deal = True
                    deal_date = deal.get("update_time", "").split("T")[0] if deal.get("update_time") else ""
                else:
                    # For other filters, do client-side filtering
                    if date_filter == "add":
                        date_field = deal.get("add_time", "")
                    elif date_filter == "close":
                        date_field = deal.get("close_time", "")
                    elif date_filter == "activity":
                        date_field = deal.get("last_activity_date", "")
                    else:
                        date_field = deal.get("update_time", "")
                    
                    if date_field:
                        deal_date = date_field.split("T")[0] if "T" in date_field else date_field.split(" ")[0]
                        include_deal = start_date <= deal_date <= end_date
                    else:
                        include_deal = False
                
                if include_deal:
                    matching_deals.append({
                        "id": deal.get("id"),
                        "title": deal.get("title"),
                        "value": deal.get("value"),
                        "currency": deal.get("currency"),
                        "stage": deal.get("stage", {}).get("name", "Unknown") if deal.get("stage") else "Unknown",
                        "owner": deal.get("owner_name"),
                        "filter_date": deal_date,
                        "date_type": date_filter
                    })
            
            # Check pagination based on filter type
            if date_filter == "update":
                # For native filtering, trust normal pagination
                if response.get("additional_data", {}).get("next_cursor"):
                    cursor = response["additional_data"]["next_cursor"]
                else:
                    break
            else:
                # For client-side filtering, be more careful
                if response.get("additional_data", {}).get("next_cursor") and len(matching_deals) < limit:
                    cursor = response["additional_data"]["next_cursor"]
                else:
                    break
        
        result = {
            "success": True,
            "date_range": f"{start_date} to {end_date}",
            "date_filter_type": f"{date_filter} date ({date_filter}_time field)",
            "status_filter": status,
            "total_returned": len(matching_deals),
            "limit_applied": limit,
            "deals": matching_deals,
            "note": f"Focused list filtered by {date_filter} date with key fields only. Use get_deal_details(id) for full information."
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error fetching deals list: {str(e)}"

@mcp.tool()
async def get_activities_summary_by_date(date: str = "", done: int = 0, limit: int = 15) -> str:
    """
    Get a focused summary of activities for a specific date.
    Returns essential info only to minimize LLM context usage.
    
    Args:
        date: Date in YYYY-MM-DD format (default: today)
        done: Activity completion status (0 = not done, 1 = done, -1 = all) - default is 0
        limit: Max number of activities to return (default: 15, max: 30)
    
    Returns:
        JSON string with activity summary + focused activity list
    """
    try:
        # Default to today if no date provided
        now = datetime.now()
        if not date:
            date = now.strftime("%Y-%m-%d")
        
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return f"Error: Please use YYYY-MM-DD format. Example: 2025-01-15"
        
        # Limit to prevent context overload
        limit = min(limit, 30)
        
        matching_activities = []
        type_counts = {}
        user_counts = {}
        cursor = None
        requests_made = 0
        
        while len(matching_activities) < limit and requests_made < 3:  # Limit API calls
            requests_made += 1
            params = {"limit": 500}
            
            if done != -1:
                params["done"] = done
                
            if cursor:
                params["cursor"] = cursor
            
            try:
                response = await pipedrive_client.make_api_request("/activities/collection", params=params)
            except:
                response = await pipedrive_client.make_api_request("/activities", params=params)
            
            if not response.get("success") or not response.get("data"):
                break
            
            # Filter activities by date
            for activity in response["data"]:
                if len(matching_activities) >= limit:
                    break
                    
                due_date = activity.get("due_date", "")
                if due_date == date:
                    # Count by type and user for summary
                    activity_type = activity.get("type", "Unknown")
                    type_counts[activity_type] = type_counts.get(activity_type, 0) + 1
                    
                    user_name = activity.get("assignee_name", "Unknown")
                    user_counts[user_name] = user_counts.get(user_name, 0) + 1
                    
                    # Add focused activity info
                    matching_activities.append({
                        "id": activity.get("id"),
                        "subject": activity.get("subject"),
                        "type": activity_type,
                        "due_time": activity.get("due_time"),
                        "done": activity.get("done"),
                        "assignee": user_name,
                        "deal_title": activity.get("deal_title"),
                        "person_name": activity.get("person_name")
                    })
            
            # Check pagination
            if response.get("additional_data", {}).get("next_cursor"):
                cursor = response["additional_data"]["next_cursor"]
            else:
                break
        
        result = {
            "success": True,
            "date": date,
            "completion_filter": "not done" if done == 0 else "done" if done == 1 else "all",
            "summary": {
                "total_activities": len(matching_activities),
                "breakdown_by_type": dict(sorted(type_counts.items(), key=lambda x: x[1], reverse=True)),
                "breakdown_by_user": dict(sorted(user_counts.items(), key=lambda x: x[1], reverse=True))
            },
            "activities": matching_activities,
            "note": f"Showing {len(matching_activities)} activities. Use get_deal_activities(id) for deal-specific activities."
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error fetching activities summary: {str(e)}"

# SEARCH FUNCTIONALITY

@mcp.tool()
async def search_deals(search_term: str, limit: int = 100) -> str:
    """
    Search for deals by title, person name, organization name, or notes.
    
    Args:
        search_term: The search query (deal title, person name, org name, etc.)
        limit: Maximum number of results to return - default is 100
    
    Returns:
        JSON string containing search results for deals
    """
    try:
        params = {
            "term": search_term,
            "item_type": "deal",
            "limit": min(limit, 500)
        }
        response = await pipedrive_client.make_api_request("/itemSearch", params=params)
        return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error searching deals: {str(e)}"

@mcp.tool()
async def search_persons(search_term: str, limit: int = 100) -> str:
    """
    Search for persons/contacts by name, email, phone, or organization.
    
    Args:
        search_term: The search query (person name, email, phone, etc.)
        limit: Maximum number of results to return - default is 100
    
    Returns:
        JSON string containing search results for persons
    """
    try:
        params = {
            "term": search_term,
            "item_type": "person",
            "limit": min(limit, 500)
        }
        response = await pipedrive_client.make_api_request("/itemSearch", params=params)
        return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error searching persons: {str(e)}"

@mcp.tool()
async def search_organizations(search_term: str, limit: int = 100) -> str:
    """
    Search for organizations/companies by name, address, or other details.
    
    Args:
        search_term: The search query (organization name, address, etc.)
        limit: Maximum number of results to return - default is 100
    
    Returns:
        JSON string containing search results for organizations
    """
    try:
        params = {
            "term": search_term,
            "item_type": "organization",
            "limit": min(limit, 500)
        }
        response = await pipedrive_client.make_api_request("/itemSearch", params=params)
        return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error searching organizations: {str(e)}"

@mcp.tool()
async def search_activities(search_term: str, limit: int = 100) -> str:
    """
    Search for activities by subject, note, or type.
    
    Args:
        search_term: The search query (activity subject, note content, etc.)
        limit: Maximum number of results to return - default is 100
    
    Returns:
        JSON string containing search results for activities
    """
    try:
        params = {
            "term": search_term,
            "item_type": "activity",
            "limit": min(limit, 500)
        }
        response = await pipedrive_client.make_api_request("/itemSearch", params=params)
        return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error searching activities: {str(e)}"

@mcp.tool()
async def search_all(search_term: str, limit: int = 100) -> str:
    """
    Search across all entity types (deals, persons, organizations, activities) simultaneously.
    
    Args:
        search_term: The search query
        limit: Maximum number of results per entity type - default is 100
    
    Returns:
        JSON string containing search results across all entity types
    """
    try:
        all_results = {
            "success": True,
            "search_term": search_term,
            "results": {}
        }
        
        # Search each entity type
        entity_types = ["deal", "person", "organization", "activity"]
        
        for entity_type in entity_types:
            try:
                params = {
                    "term": search_term,
                    "item_type": entity_type,
                    "limit": min(limit, 500)
                }
                response = await pipedrive_client.make_api_request("/itemSearch", params=params)
                
                if response.get("success"):
                    all_results["results"][entity_type] = {
                        "count": len(response.get("data", [])),
                        "data": response.get("data", [])
                    }
                else:
                    all_results["results"][entity_type] = {
                        "count": 0,
                        "data": [],
                        "error": response.get("error", "Unknown error")
                    }
            except Exception as e:
                all_results["results"][entity_type] = {
                    "count": 0,
                    "data": [],
                    "error": str(e)
                }
        
        # Add summary
        total_results = sum(result["count"] for result in all_results["results"].values())
        all_results["summary"] = {
            "total_results": total_results,
            "deals_found": all_results["results"].get("deal", {}).get("count", 0),
            "persons_found": all_results["results"].get("person", {}).get("count", 0),
            "organizations_found": all_results["results"].get("organization", {}).get("count", 0),
            "activities_found": all_results["results"].get("activity", {}).get("count", 0)
        }
        
        return json.dumps(all_results, indent=2)
    except Exception as e:
        return f"Error performing comprehensive search: {str(e)}"

# UTILITY TOOLS

@mcp.tool()
async def get_current_datetime() -> str:
    """
    Get current date and time in various formats useful for Pipedrive operations.
    
    Returns:
        JSON string containing current date/time information
    """
    try:
        now = datetime.now()
        
        result = {
            "current_datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "current_date": now.strftime("%Y-%m-%d"),
            "current_time": now.strftime("%H:%M:%S"),
            "today": now.strftime("%Y-%m-%d"),
            "yesterday": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "week_start": (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d"),
            "month_start": now.replace(day=1).strftime("%Y-%m-%d"),
            "iso_format": now.isoformat(),
            "timestamp": int(now.timestamp()),
            "day_of_week": now.strftime("%A"),
            "month_name": now.strftime("%B")
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error getting current datetime: {str(e)}"

@mcp.resource("pipedrive://info")
def pipedrive_info() -> str:
    """
    Get information about available Pipedrive functionality.
    """
    return """# Pipedrive MCP Server

## Available Tools (22 Total):

### Phase 1 - Basic Data Retrieval:
1. **get_pipelines()** - Get all pipelines from your Pipedrive account
2. **get_deals(status, limit)** - Get deals with optional status filtering
3. **get_deal_details(deal_id)** - Get detailed information about a specific deal
4. **get_deal_flow(deal_id)** - Get deal timeline with stage changes
5. **get_deal_activities(deal_id)** - Get all activities for a specific deal
6. **get_users()** - Get all users from your account
7. **get_stages(pipeline_id)** - Get all stages, optionally for specific pipeline

### Smart Date Filtering (LLM-Optimized):
8. **get_deals_summary_by_date(start_date, end_date, status, date_filter)** - Summary + top 10 deals by specific date field
9. **get_deals_list(start_date, end_date, status, limit, date_filter)** - Focused list with key fields only (max 50)
10. **get_activities_summary_by_date(date, done, limit)** - Daily activity summary (max 30)

### Search Functionality:
11. **search_deals(search_term, limit)** - Search deals by title, person, org, notes
12. **search_persons(search_term, limit)** - Search contacts by name, email, phone
13. **search_organizations(search_term, limit)** - Search companies by name, address
14. **search_activities(search_term, limit)** - Search activities by subject, notes
15. **search_all(search_term, limit)** - Search across all entity types simultaneously

### Overdue Activity Management:
16. **get_overdue_activities()** - Get overdue activities from open deals only
17. **get_overdue_summary_by_user()** - Overdue activity summary by user (open deals only)

### Deal Quality Analysis:
18. **get_deals_with_no_activities(status, limit)** - Find deals with zero activities

### Today's Work Focus (NEW!):
20. **get_todays_deals()** - Deals relevant for TODAY (closing today, activities due, recently active)
21. **get_todays_activities()** - Activities scheduled for today organized by urgency  
22. **get_my_pipeline_focus()** - Pipeline review with actionable insights

### Utility Tools:
19. **get_current_datetime()** - Get current date/time in various formats

## Key Improvements:
✅ **LLM-Optimized**: Small, focused responses instead of 500+ item dumps
✅ **Custom Date Ranges**: Use specific dates (YYYY-MM-DD) not just predefined periods
✅ **Summary-First Approach**: Get metrics + top items, drill down for details
✅ **Smart Limits**: Default 15-50 items instead of 1000+ for better context usage
✅ **Comprehensive Search**: Search across deals, persons, organizations, activities
✅ **Overdue Focus**: Only shows overdue activities from open deals (not lost/won)

## Setup Instructions:
1. Create a .env file in your project root
2. Add your Pipedrive domain and API key:
   ```
   PIPEDRIVE_DOMAIN=your-company-domain
   PIPEDRIVE_API_KEY=your_api_key_here
   ```
3. Get your API key from Pipedrive Settings > Personal preferences > API

## Usage Examples:

### For "Today's Deals" Requests (RECOMMENDED):
- **Today's Actionable Deals**: get_todays_deals() - Shows deals that need attention TODAY
- **Today's Schedule**: get_todays_activities() - Activities due today organized by urgency
- **Pipeline Review**: get_my_pipeline_focus() - Daily pipeline review with insights

### Traditional Date Filtering:
- **Daily Updated Deals**: get_deals_summary_by_date("2025-06-27", "2025-06-27", "open", "update") 
- **Deals Created Today**: get_deals_summary_by_date("2025-01-15", "2025-01-15", "open", "add")
- **Recent Activity**: get_deals_summary_by_date("2025-01-13", "2025-01-19", "open", "activity")
- **Focused List**: get_deals_list("2025-01-15", "2025-01-15", "open", 20, "update") - key fields only
- **Activity Schedule**: get_activities_summary_by_date("2025-01-15", 0, 15) - today's tasks

### Search & Analysis:
- **Search Everything**: search_all("Microsoft") - comprehensive search
- **Quality Check**: get_deals_with_no_activities("open") - neglected opportunities
- **Overdue Management**: get_overdue_activities() - only from active deals

## Date Filter Options:
- **"update"** (default) ✅ - Deals modified on this date (uses API native filtering!)
- **"add"** - Deals created on this date (client-side filtering)
- **"close"** - Deals closed on this date (client-side filtering) 
- **"activity"** - Deals with last activity on this date (client-side filtering)

**Note**: "update" filter is most accurate as it uses Pipedrive's native API filtering!

## Smart Approach:
1. **Start with summaries** to get the big picture
2. **Use focused lists** for specific analysis
3. **Drill down with details** only when needed
4. **Set appropriate limits** to stay within context windows

## Pipedrive Domain:
- Your domain is the part before .pipedrive.com in your account URL
- For example, if your URL is https://mycompany.pipedrive.com, your domain is "mycompany"
"""

# PHASE 4: TODAY'S WORK FOCUS TOOLS

@mcp.tool()
async def get_todays_deals() -> str:
    """
    Get deals that are relevant for TODAY'S work - not just updated today.
    This includes deals with activities due today, expected to close today, or recently active.
    
    Returns:
        JSON string with deals organized by why they're relevant today
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get deals with different relevance criteria
        relevant_deals = {
            "deals_closing_today": [],
            "deals_with_activities_today": [],
            "recently_active_deals": [],
            "overdue_deals": []
        }
        
        # 1. Get deals expected to close today
        try:
            params = {
                "status": "open",
                "limit": 100
            }
            response = await pipedrive_client.make_api_request("/deals", params=params)
            
            if response.get("success") and response.get("data"):
                for deal in response["data"]:
                    expected_close = deal.get("expected_close_date")
                    if expected_close == today:
                        relevant_deals["deals_closing_today"].append({
                            "id": deal.get("id"),
                            "title": deal.get("title"),
                            "value": deal.get("value"),
                            "currency": deal.get("currency"),
                            "stage": deal.get("stage", {}).get("name", "Unknown"),
                            "owner": deal.get("owner_name"),
                            "person": deal.get("person_name"),
                            "org": deal.get("org_name"),
                            "expected_close_date": expected_close
                        })
        except Exception as e:
            print(f"Error fetching closing deals: {e}")
        
        # 2. Get activities due today and their associated deals
        try:
            today_start = f"{today}T00:00:00Z"
            today_end = f"{today}T23:59:59Z"
            
            params = {
                "done": 0,  # Only undone activities
                "limit": 200
            }
            
            # Try API v2 first
            try:
                response = await pipedrive_client.make_api_request("/api/v2/activities", params=params)
            except:
                response = await pipedrive_client.make_api_request("/activities", params=params)
            
            if response.get("success") and response.get("data"):
                deal_ids_with_activities = set()
                
                for activity in response["data"]:
                    due_date = activity.get("due_date")
                    if due_date == today:
                        deal_id = activity.get("deal_id")
                        if deal_id:
                            deal_ids_with_activities.add(deal_id)
                
                # Get deal details for these deals
                for deal_id in list(deal_ids_with_activities)[:20]:  # Limit to prevent too many calls
                    try:
                        deal_response = await pipedrive_client.make_api_request(f"/deals/{deal_id}")
                        if deal_response.get("success") and deal_response.get("data"):
                            deal = deal_response["data"]
                            relevant_deals["deals_with_activities_today"].append({
                                "id": deal.get("id"),
                                "title": deal.get("title"),
                                "value": deal.get("value"),
                                "currency": deal.get("currency"),
                                "stage": deal.get("stage", {}).get("name", "Unknown"),
                                "owner": deal.get("owner_name"),
                                "person": deal.get("person_name"),
                                "org": deal.get("org_name"),
                                "status": deal.get("status")
                            })
                    except:
                        continue
        except Exception as e:
            print(f"Error fetching today's activities: {e}")
        
        # 3. Get recently active deals (updated in last 3 days)
        try:
            three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
            recent_datetime = f"{three_days_ago}T00:00:00Z"
            
            params = {
                "status": "open",
                "updated_since": recent_datetime,
                "limit": 50,
                "sort_by": "update_time",
                "sort_direction": "desc"
            }
            
            try:
                response = await pipedrive_client.make_api_request("/api/v2/deals", params=params)
            except:
                response = await pipedrive_client.make_api_request("/deals", params=params)
            
            if response.get("success") and response.get("data"):
                for deal in response["data"][:15]:  # Top 15 most recently updated
                    relevant_deals["recently_active_deals"].append({
                        "id": deal.get("id"),
                        "title": deal.get("title"),
                        "value": deal.get("value"),
                        "currency": deal.get("currency"),
                        "stage": deal.get("stage", {}).get("name", "Unknown"),
                        "owner": deal.get("owner_name"),
                        "person": deal.get("person_name"),
                        "org": deal.get("org_name"),
                        "last_updated": deal.get("update_time", "").split("T")[0]
                    })
        except Exception as e:
            print(f"Error fetching recently active deals: {e}")
        
        # 4. Get deals with overdue activities
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            params = {
                "done": 0,
                "limit": 100
            }
            
            try:
                response = await pipedrive_client.make_api_request("/api/v2/activities", params=params)
            except:
                response = await pipedrive_client.make_api_request("/activities", params=params)
            
            if response.get("success") and response.get("data"):
                overdue_deal_ids = set()
                
                for activity in response["data"]:
                    due_date = activity.get("due_date")
                    if due_date and due_date < today:  # Overdue
                        deal_id = activity.get("deal_id")
                        if deal_id:
                            overdue_deal_ids.add(deal_id)
                
                # Get deal details for overdue deals
                for deal_id in list(overdue_deal_ids)[:10]:  # Limit to top 10
                    try:
                        deal_response = await pipedrive_client.make_api_request(f"/deals/{deal_id}")
                        if deal_response.get("success") and deal_response.get("data"):
                            deal = deal_response["data"]
                            if deal.get("status") == "open":  # Only open deals
                                relevant_deals["overdue_deals"].append({
                                    "id": deal.get("id"),
                                    "title": deal.get("title"),
                                    "value": deal.get("value"),
                                    "currency": deal.get("currency"),
                                    "stage": deal.get("stage", {}).get("name", "Unknown"),
                                    "owner": deal.get("owner_name"),
                                    "person": deal.get("person_name"),
                                    "org": deal.get("org_name")
                                })
                    except:
                        continue
        except Exception as e:
            print(f"Error fetching overdue deals: {e}")
        
        # Calculate totals
        total_relevant = sum(len(deals) for deals in relevant_deals.values())
        
        result = {
            "success": True,
            "date": today,
            "summary": {
                "total_relevant_deals": total_relevant,
                "deals_closing_today": len(relevant_deals["deals_closing_today"]),
                "deals_with_activities_today": len(relevant_deals["deals_with_activities_today"]),
                "recently_active_deals": len(relevant_deals["recently_active_deals"]),
                "overdue_deals": len(relevant_deals["overdue_deals"])
            },
            "deals_by_priority": relevant_deals,
            "note": "These are deals that need attention TODAY - not just deals updated today"
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error fetching today's deals: {str(e)}"

@mcp.tool()
async def get_todays_activities() -> str:
    """
    Get activities scheduled for TODAY with their associated deals.
    
    Returns:
        JSON string with today's activities organized by type and urgency
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        activities_today = {
            "overdue": [],
            "due_today": [],
            "by_type": {},
            "by_deal": {}
        }
        
        # Get all activities
        params = {
            "done": 0,  # Only undone activities
            "limit": 300
        }
        
        try:
            response = await pipedrive_client.make_api_request("/api/v2/activities", params=params)
        except:
            response = await pipedrive_client.make_api_request("/activities", params=params)
        
        if response.get("success") and response.get("data"):
            for activity in response["data"]:
                due_date = activity.get("due_date")
                
                # Check if activity is for today or overdue
                is_today = due_date == today
                is_overdue = due_date and due_date < today
                
                if is_today or is_overdue:
                    activity_data = {
                        "id": activity.get("id"),
                        "subject": activity.get("subject"),
                        "type": activity.get("type"),
                        "due_date": due_date,
                        "due_time": activity.get("due_time"),
                        "deal_id": activity.get("deal_id"),
                        "deal_title": activity.get("deal_title"),
                        "person_name": activity.get("person_name"),
                        "org_name": activity.get("org_name"),
                        "owner_name": activity.get("owner_name"),
                        "note": activity.get("note", "")[:100] + "..." if activity.get("note", "") else ""
                    }
                    
                    # Categorize by urgency
                    if is_overdue:
                        activities_today["overdue"].append(activity_data)
                    else:
                        activities_today["due_today"].append(activity_data)
                    
                    # Group by type
                    activity_type = activity.get("type", "Unknown")
                    if activity_type not in activities_today["by_type"]:
                        activities_today["by_type"][activity_type] = []
                    activities_today["by_type"][activity_type].append(activity_data)
                    
                    # Group by deal
                    deal_id = activity.get("deal_id")
                    if deal_id:
                        deal_title = activity.get("deal_title", f"Deal {deal_id}")
                        if deal_title not in activities_today["by_deal"]:
                            activities_today["by_deal"][deal_title] = []
                        activities_today["by_deal"][deal_title].append(activity_data)
        
        # Sort activities by time
        activities_today["due_today"].sort(key=lambda x: x.get("due_time", "23:59"))
        activities_today["overdue"].sort(key=lambda x: x.get("due_date", ""))
        
        total_activities = len(activities_today["overdue"]) + len(activities_today["due_today"])
        
        result = {
            "success": True,
            "date": today,
            "summary": {
                "total_activities_today": total_activities,
                "overdue_count": len(activities_today["overdue"]),
                "due_today_count": len(activities_today["due_today"]),
                "activity_types": list(activities_today["by_type"].keys()),
                "deals_with_activities": len(activities_today["by_deal"])
            },
            "activities": activities_today,
            "note": "Activities that need attention today, sorted by urgency and time"
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error fetching today's activities: {str(e)}"

@mcp.tool()
async def get_my_pipeline_focus() -> str:
    """
    Get a focused view of your pipeline - deals that need attention organized by stage.
    Perfect for daily pipeline review and planning next actions.
    
    Returns:
        JSON string with pipeline organized by stage with actionable insights
    """
    try:
        # Get all open deals
        params = {
            "status": "open",
            "limit": 200
        }
        
        try:
            response = await pipedrive_client.make_api_request("/api/v2/deals", params=params)
        except:
            response = await pipedrive_client.make_api_request("/deals", params=params)
        
        if not response.get("success") or not response.get("data"):
            return json.dumps({"error": "No deals found"}, indent=2)
        
        # Organize deals by stage
        pipeline_view = {
            "by_stage": {},
            "needs_attention": [],
            "closing_soon": [],
            "stalled_deals": []
        }
        
        today = datetime.now().strftime("%Y-%m-%d")
        week_from_now = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        two_weeks_ago = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        
        for deal in response["data"]:
            stage_name = deal.get("stage", {}).get("name", "Unknown Stage")
            
            deal_data = {
                "id": deal.get("id"),
                "title": deal.get("title"),
                "value": deal.get("value"),
                "currency": deal.get("currency"),
                "owner": deal.get("owner_name"),
                "person": deal.get("person_name"),
                "org": deal.get("org_name"),
                "expected_close_date": deal.get("expected_close_date"),
                "last_activity_date": deal.get("last_activity_date"),
                "activities_count": deal.get("activities_count", 0),
                "last_updated": deal.get("update_time", "").split("T")[0]
            }
            
            # Group by stage
            if stage_name not in pipeline_view["by_stage"]:
                pipeline_view["by_stage"][stage_name] = []
            pipeline_view["by_stage"][stage_name].append(deal_data)
            
            # Identify deals that need attention
            expected_close = deal.get("expected_close_date")
            last_activity = deal.get("last_activity_date")
            last_update = deal.get("update_time", "").split("T")[0]
            
            # Closing soon (within 7 days)
            if expected_close and expected_close <= week_from_now:
                pipeline_view["closing_soon"].append(deal_data)
            
            # Stalled deals (no activity in 2+ weeks)
            if last_activity and last_activity < two_weeks_ago:
                pipeline_view["stalled_deals"].append(deal_data)
            elif not last_activity and last_update < two_weeks_ago:
                pipeline_view["stalled_deals"].append(deal_data)
            
            # Needs attention (various criteria)
            needs_attention = False
            reasons = []
            
            if expected_close and expected_close <= today:
                needs_attention = True
                reasons.append("Expected to close today or overdue")
            
            if deal.get("activities_count", 0) == 0:
                needs_attention = True
                reasons.append("No activities scheduled")
            
            if last_activity and last_activity < (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"):
                needs_attention = True
                reasons.append("No recent activity")
            
            if needs_attention:
                deal_data["attention_reasons"] = reasons
                pipeline_view["needs_attention"].append(deal_data)
        
        # Sort deals within each category
        for stage in pipeline_view["by_stage"]:
            pipeline_view["by_stage"][stage].sort(key=lambda x: x.get("value", 0), reverse=True)
        
        pipeline_view["closing_soon"].sort(key=lambda x: x.get("expected_close_date", "9999-12-31"))
        pipeline_view["stalled_deals"].sort(key=lambda x: x.get("last_activity_date", "1900-01-01"))
        pipeline_view["needs_attention"].sort(key=lambda x: x.get("value", 0), reverse=True)
        
        # Calculate summary metrics
        total_deals = len(response["data"])
        total_value = sum(deal.get("value", 0) or 0 for deal in response["data"])
        
        result = {
            "success": True,
            "summary": {
                "total_open_deals": total_deals,
                "total_pipeline_value": total_value,
                "deals_closing_soon": len(pipeline_view["closing_soon"]),
                "stalled_deals": len(pipeline_view["stalled_deals"]),
                "deals_needing_attention": len(pipeline_view["needs_attention"]),
                "stages_with_deals": len(pipeline_view["by_stage"])
            },
            "pipeline": pipeline_view,
            "note": "Your pipeline organized for daily review - focus on 'needs_attention' and 'closing_soon' first"
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error fetching pipeline focus: {str(e)}"

async def run_server():
    """Run the MCP server"""
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8000")))
    
    print("🚀 Starting Enhanced Pipedrive MCP Server")
    print(f"📋 Server running on http://{host}:{port}")
    print(f"🔧 22 tools available (Basic + Today's Focus + Time-Range + Search + Quality Analysis)")
    print(f"📚 1 resource available")
    print("✨ New Features: Today's work focus, smart pagination, time-range filtering, comprehensive search")
    
    # Check if credentials are properly configured
    if PIPEDRIVE_CONFIG["domain"] == "your-company-domain":
        print("\n⚠️  WARNING: Default credentials detected!")
        print("   Please set PIPEDRIVE_DOMAIN and PIPEDRIVE_API_KEY environment variables")
    else:
        print(f"\n✅ Configured for domain: {PIPEDRIVE_CONFIG['domain']}.pipedrive.com")
    
    # Run the server
    await mcp.run_sse_async(host=host, port=port, path="/sse")

if __name__ == "__main__":
    asyncio.run(run_server()) 