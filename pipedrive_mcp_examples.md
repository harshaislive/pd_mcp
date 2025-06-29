# Pipedrive MCP: Filtering Examples & Recipes

This guide provides practical examples for using the advanced filtering tools in your Pipedrive MCP.

## The Core Filtering Workflow

Most data retrieval tasks follow a simple, three-step pattern:

1.  **Discover Field IDs**: Use `get_field_ids_for_entity` to find the internal ID for the field you want to filter on (e.g., `add_time`, `status`, `owner_id`). This is a crucial first step.
2.  **Create a Filter**: Use a filter creation tool (`create_advanced_filter`, `create_date_range_filter`, etc.) with the `field_id` from step 1 to get a `filter_id`.
3.  **Get Data**: Use the `filter_id` with a data retrieval tool (e.g., `get_deals_with_filter`, `get_activities_with_filter`) to get your items.

---

## Tool Examples

### 1. `get_field_ids_for_entity`

**Purpose**: To get the all-important `field_id` needed for creating filters.

**Example Request**:
```json
{
  "tool": "get_field_ids_for_entity",
  "args": {
    "entity_type": "deals"
  }
}
```
*Look through the output to find the field you need. For example, the deal creation time is `add_time`.*

### 2. `create_advanced_filter`

**Purpose**: The most powerful tool for building complex queries with `ALL` (and) and `ANY` (or) conditions.

**Example Request (Get deals over $500 that are either in Pipeline 1 or Pipeline 2):**
```json
{
  "tool": "create_advanced_filter",
  "args": {
    "filter_type": "deals",
    "conditions_all": [{
      "object": "deal",
      "field_id": "value",
      "operator": ">",
      "value": "500"
    }],
    "conditions_any": [{
      "object": "deal",
      "field_id": "pipeline_id",
      "operator": "=",
      "value": "1"
    }, {
      "object": "deal",
      "field_id": "pipeline_id",
      "operator": "=",
      "value": "2"
    }]
  }
}
```

### 3. `create_date_range_filter`

**Purpose**: A helper for creating simple date-based filters.

**Example Request (Get activities due next week):**
*(You would need to calculate the dates for next week first)*
```json
{
  "tool": "create_date_range_filter",
  "args": {
    "filter_type": "activities",
    "field_id": "due_date",
    "start_date": "2025-07-01",
    "end_date": "2025-07-07"
  }
}
```

---

## Practical Recipes

### How to Get Activities Due By a Specific Owner

1.  **Find Field IDs**: Call `get_field_ids_for_entity` for `"activities"`. Find the `field_id` for `due_date` and `user_id`.
2.  **Create Filter**: Use `create_advanced_filter`.
    ```json
    {
      "tool": "create_advanced_filter",
      "args": {
        "filter_type": "activities",
        "conditions_all": [{
          "object": "activity",
          "field_id": "due_date",
          "operator": "<=",
          "value": "2025-06-30"
        },{
          "object": "activity",
          "field_id": "user_id",
          "operator": "=",
          "value": "12345"
        }]
      }
    }
    ```
3.  **Get Data**: Use `get_activities_with_filter` with the `filter_id` returned from step 2.

### How to Get Deals Created Yesterday

*Your client application will first need to calculate yesterday's date string (e.g., "2025-06-26").*

1.  **Find Field ID**: Call `get_field_ids_for_entity` for `"deals"` to get the `field_id` for `add_time`.
2.  **Create Filter**: Use `create_date_range_filter` for a single day.
    ```json
    {
      "tool": "create_date_range_filter",
      "args": {
        "filter_type": "deals",
        "field_id": "add_time",
        "start_date": "2025-06-26",
        "end_date": "2025-06-26"
      }
    }
    ```
3.  **Get Data**: Use `get_deals_with_filter` with the returned `filter_id`.

### How to Get Deals Created Last Month

*Your client application will first need to calculate the start and end dates for the previous month (e.g., "2025-05-01" to "2025-05-31").*

1.  **Find Field ID**: Same as above, you need the `field_id` for `add_time` from `get_field_ids_for_entity`.
2.  **Create Filter**: Use `create_date_range_filter` with the calculated month range.
    ```json
    {
      "tool": "create_date_range_filter",
      "args": {
        "filter_type": "deals",
        "field_id": "add_time",
        "start_date": "2025-05-01",
        "end_date": "2025-05-31"
      }
    }
    ```
3.  **Get Data**: Use `get_deals_with_filter` with the returned `filter_id`. 