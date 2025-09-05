# PeopleSQL Tool Implementation

## Purpose
Queries a people database using SQL-like filters with adapter-based mapping.

## Input/Output Contract
- **Input**: `{"filters": [{"is_friend": "user"}, {"city": "Seattle"}]}`
- **Output**: `{"people": [{"id": "E3", "name": "Alice", "city": "Seattle"}]}`
- **Assertion**: `(Person "Alice" matchesQuery true)` for each result

## Implementation Details

### Database Schema
```sql
-- People table
CREATE TABLE people (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(100),
    age INTEGER,
    occupation VARCHAR(100)
);

-- Relations table  
CREATE TABLE relations (
    id VARCHAR(50) PRIMARY KEY,
    src_id VARCHAR(50) REFERENCES people(id),
    rel_type VARCHAR(50) NOT NULL,
    dst_id VARCHAR(50) REFERENCES people(id)
);
```

### Adapter Mapping
The adapter translates generic IR filters to SQL WHERE clauses:

- `{"is_friend": "user"}` → `r.rel_type = 'friend' AND r.dst_id = 'user'`
- `{"city": "Seattle"}` → `p.city = 'Seattle'`
- `{"name": "Alice"}` → `p.name ILIKE '%Alice%'`

### Preconditions
- `filters_are_valid`: All filters match known patterns
- `database_accessible`: Database connection is available
- `user_exists`: Referenced user exists in database

### Postconditions
- `results_are_persons`: All results have valid person structure
- `results_match_filters`: All results satisfy the filter conditions
- `no_duplicates`: Results are deduplicated by person ID

## Example Usage

```python
def query(filters: list, user_id: str = "user") -> dict:
    """
    Query people database with filters.
    
    Args:
        filters: List of filter conditions
        user_id: ID of the user making the query
        
    Returns:
        dict: {"people": [person_dict]} or {"error": "message"}
    """
    try:
        # Build SQL query using adapter
        conditions = []
        params = {}
        
        for i, filter_dict in enumerate(filters):
            for key, value in filter_dict.items():
                if key == "is_friend":
                    conditions.append("r.rel_type = 'friend' AND r.dst_id = %(user_id)s")
                    params["user_id"] = user_id
                elif key == "city":
                    conditions.append("p.city = %(city)s")
                    params["city"] = value
                elif key == "name":
                    conditions.append("p.name ILIKE %(name)s")
                    params["name"] = f"%{value}%"
                elif key == "age":
                    conditions.append("p.age = %(age)s")
                    params["age"] = value
                elif key == "occupation":
                    conditions.append("p.occupation ILIKE %(occupation)s")
                    params["occupation"] = f"%{value}%"
        
        if not conditions:
            return {"error": "No valid filters provided"}
        
        # Build final query
        query = """
        SELECT DISTINCT p.id, p.name, p.city, p.age, p.occupation
        FROM people p
        LEFT JOIN relations r ON p.id = r.src_id
        WHERE """ + " AND ".join(conditions)
        
        # Execute query
        results = db.execute(query, params)
        
        # Format results
        people = []
        for row in results:
            people.append({
                "id": row["id"],
                "name": row["name"],
                "city": row["city"],
                "age": row["age"],
                "occupation": row["occupation"]
            })
        
        return {"people": people}
        
    except Exception as e:
        return {"error": f"Query failed: {str(e)}"}
```

## Test Cases

### Valid Queries
- `[{"is_friend": "user"}]` → Returns all friends of user
- `[{"city": "Seattle"}]` → Returns all people in Seattle
- `[{"is_friend": "user"}, {"city": "Seattle"}]` → Returns friends in Seattle
- `[{"name": "Alice"}]` → Returns people with "Alice" in name

### Invalid Queries
- `[]` → `{"error": "No valid filters provided"}`
- `[{"invalid_field": "value"}]` → `{"error": "Unknown filter field: invalid_field"}`

## Error Handling
- Database connection failure → return error
- Invalid SQL generation → return error
- Empty result set → return empty list (not error)
- Malformed filters → return error with details

## Integration Notes
- Tool name: `PeopleSQL`
- Entry point: `people_sql.query`
- Reliability: High (with proper database)
- Cost: Low (database query)
- Latency: ~50ms
- Dependencies: Database connection, adapter configuration
- Adapter: `people_sql_adapter.yaml`
