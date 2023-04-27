import argparse

from gql_utils.cypher_connector import CypherConnector
from gql_utils.gql_schema import GQLSchema


def main():
    default_main_schema_url = "https://main_url/graphql" # REPLACE
    default_main_schema_file = "./gql_utils/schema.json"
    default_sub_schema_file = "./gql_utils/sub_schema.json"
    default_expanded_request_body_file = "./gql_utils/expanded_body.req"

    # create top-level parser
    parser = argparse.ArgumentParser(
        prog="gql_map.gql_utils",
        description="GQL security tool",
        add_help=True
    )

    # create sub-parser
    sub_parsers = parser.add_subparsers(
        title="Actions",
        description="Pass in an action below",
        dest="action",
        required=True
    )

    # create parser for the "fetch_main_schema" sub-command
    parser_fetch_main_schema = sub_parsers.add_parser(
        "fetch_main_schema", help="Fetch main schema using introspection query")
    parser_fetch_main_schema.add_argument(
        "-t", "--target", type=str, help="url to send introspection query to", default=default_main_schema_url
    )
    parser_fetch_main_schema.add_argument(
        "-o", "--output", type=str, help="file to save schema to", default=default_main_schema_file
    )

    # create parser for the "build_sub_schema" sub-command
    parser_build_sub_schema = sub_parsers.add_parser(
        "build_sub_schema", help="Build sub schema to support a specific set of operations")
    parser_build_sub_schema.add_argument(
        "-s", "--schema", type=str, help="main schema file location", default=default_main_schema_file
    )
    parser_build_sub_schema.add_argument(
        "-o", "--output", type=str, help="file to save sub schema to", default=default_sub_schema_file
    )
    parser_build_sub_schema.add_argument(
        "-q", "--queries", type=lambda arg: arg.split(','), help="comma-delimited list of top-level queries to support without spaces (eg. 'shiota,vortex')", default=""
    )
    parser_build_sub_schema.add_argument(
        "-m", "--mutations", type=lambda arg: arg.split(','), help="comma-delimited list of top-level mutations to support without spaces (eg. 'toran,updateExperienceCheckoutFlow')", default=""
    )

    # create parser for the "update_db" sub-command
    parser_update_db = sub_parsers.add_parser(
        "update_db", help="Add types and relationships to db")
    parser_update_db.add_argument(
        "-s", "--schema", type=str, help="schema file location", required=True
    )
    parser_update_db.add_argument(
        "-c", "--credentials", type=str, help="neo4j auth credentials in format <user>:<password> (eg. --credentials neo4j:password123)", default="neo4j:password123"
    )
    parser_update_db.add_argument(
        "-u", "--uri", type=str, help="database uri in format <schema>://<ip>:<host>, (eg. --uri bolt://localhost:7687)", default="bolt://localhost:7687"
    )

    # create parser for the "query_operations" sub-command
    parser_query_operations = sub_parsers.add_parser(
        "query_operations", help="Query operations that return a GQL type")
    parser_query_operations.add_argument(
        "-t", "--type", type=str, help="name of GQL type returned in an operation", required=True
    )
    parser_query_operations.add_argument(
        "-l", "--limit", type=int, help="limit on number of operation paths to return per operation type (eg. '--limit 5' will set a limit of 5 queries AND 5 mutations for a total of 10 operations)", default=5
    )
    parser_query_operations.add_argument(
        "-c", "--credentials", type=str, help="neo4j auth credentials in format <user>:<password> (eg. --credentials neo4j:password123)", default="neo4j:password123"
    )
    parser_query_operations.add_argument(
        "-u", "--uri", type=str, help="database uri in format <schema>://<ip>:<host>, (eg. --uri bolt://localhost:7687)", default="bolt://localhost:7687"
    )
    parser_query_operations.add_argument(
        "--show-types", help="switch to show type objects in query result", default=False, action="store_true"
    )

    # create parser for the "expand_request_body" sub-command
    parser_expand_request_body = sub_parsers.add_parser(
        "expand_request_body", help="Expand request body for an operation")
    parser_expand_request_body.add_argument(
        "-s", "--schema", type=str, help="schema file location", default=default_main_schema_file
    )
    parser_expand_request_body.add_argument(
        "-o", "--output", type=str, help="file to save request body to", default=default_expanded_request_body_file
    )
    parser_expand_request_body.add_argument(
        "-q", "--query", type=str, help="top-level query to expand (eg. vortex)", default=""
    )
    parser_expand_request_body.add_argument(
        "-m", "--mutation", type=str, help="top-level mutation to expand (eg. updateExperienceCheckoutFlow)", default=""
    )

    args = parser.parse_args()

    print(args)

    if args.action == "fetch_main_schema":
        print(
            f"[-] Running introspection query on {args.target} and saving output to {args.output}")

        schema = GQLSchema(
            url=args.target, path=args.output)
        if schema.get_schema(refetch=True):
            schema.save_schema()
            print(
                f"[*] Introspection query complete! Check {args.output} for output.")
        else:
            print(
                f"[!] Something went wrong. Please try again.")

    elif args.action == "build_sub_schema":
        if not args.mutations and not args.queries:
            print(
                f"[!] Must pass in a list of queries (-q), mutations (-m), or both.")
        operations = []
        for mutation in args.mutations:
            # handle empty string
            if mutation:
                operations.append(("Mutation", mutation))
        for query in args.queries:
            # handle empty string
            if query:
                operations.append(("Query", query))

        schema = GQLSchema(
            url=default_main_schema_url, path=args.schema)

        print(
            f"[-] Building a sub schema to support mutations: {args.mutations} and queries: {args.queries}")

        if schema.get_schema(refetch=False):
            schema.build_test_schema_with_operations(
                operation_tuples=operations, test_schema_path=default_sub_schema_file)

        print(
            f"[*] Schema successfully created! Check {args.output} for results.")

    elif args.action == "update_db":
        print(f"[-] Making connection to neo4j on localhost, port 7687")

        user = args.credentials.split(":", 1)[0]
        pwd = args.credentials.split(":", 1)[1]

        cc = CypherConnector(args.uri, user, pwd)

        print(f"[-] Updating neo4j db using schema at {args.schema}")

        schema = GQLSchema(path=args.schema)
        if schema.get_schema(refetch=False):
            cc.update_db(gql_types=schema.data["types"])
        cc.close_session()

        print(
            "[*] Database update complete! Use the Neo4j browser to view the database.")
        print("[*] For starters, try the query 'MATCH (n) RETURN n LIMIT 500'")

    elif args.action == "query_operations":
        print(f"[-] Making connection to neo4j on localhost, port 7687")

        user = args.credentials.split(":", 1)[0]
        pwd = args.credentials.split(":", 1)[1]

        cc = CypherConnector(args.uri, user, pwd)

        print(f"[-] Querying operation paths for {args.type}")
        res = cc.query_operations(
            type_name=args.type, limit=args.limit, show_types=args.show_types)
        print(f"[!] Query complete!")
        for i, path in enumerate(res):
            print(f"Path {i+1}: {path}")

    elif args.action == "expand_request_body":
        if args.mutation and args.query:
            print(f"[!] Only one operation allowed.")
        if not args.mutation and not args.query:
            print(
                f"[!] Must pass an operation.")

        if args.mutation:
            operation = ("Mutation", args.mutation)
        if args.query:
            operation = ("Query", args.query)

        schema = GQLSchema(
            url=default_main_schema_url, path=args.schema)
        if schema.get_schema(refetch=False):
            schema.get_filled_operation_body(
                operation_tuple=operation, out_file=args.output)

        print("[*] Query dumped! Request fields will need to be input manually.")


if __name__ == "__main__":
    main()
