# gqlmap
This tool creates a graph representation of GraphQL types and allows you to perform queries on those relationships

- Tested using Python 3.8.9 and Neo4j Desktop 4.4.5

## gql_utils

#### Setup
Virtualenv

```bash
python3 -m venv venv
```

```bash
source venv/bin/activate
```

```bash
pip install -r requirements.txt
```

#### gql_tool.py

```
$ python3 -m gql_utils.gql_tool -h
usage: gql_map.gql_utils [-h] {fetch_main_schema,build_sub_schema,update_db,query_operations,expand_request_body} ...

GQL security tool

optional arguments:
  -h, --help            show this help message and exit

Actions:
  Pass in an action below

  {fetch_main_schema,build_sub_schema,update_db,query_operations,expand_request_body}
    fetch_main_schema   Fetch main schema using introspection query
    build_sub_schema    Build sub schema to support a specific set of operations
    update_db           Add types and relationships to db
    query_operations    Query operations that return a GQL type
    expand_request_body
                        Expand request body for an operation
```

Actions:
- `fetch_main_schema`
  - Fetch main schema using introspection query
- `build_sub_schema`
  - Build sub schema to support a specific set of operations
- `update_db`
  - Update neo4j db with schema
  - populates db with types and relationships for queries
- `query_operations`
  - Query operations that return a GQL type
  - requires a running neo4j db instance
  - performance to be tested on large GQL schemas
- `expand_request_body`
  - Expand request body for an operation
