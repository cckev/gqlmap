import requests
import json
import copy

from gql_utils.gql_constants import INTROSPECTION_QUERY_STRING
from utils.common_utils import hash_properties, get_logger

logger = get_logger()


class GQLSchema:
    def __init__(self, url: str = "", path: str = ""):
        self.url = url
        self.path = path
        self.type_map = {}
        self.operation_map = {}
        self.raw_data = {}
        self.data = {}

    def get_schema(self, refetch=False) -> bool:
        """
        :param refetch: If True, refresh the schema from self.url
        :return: False if error

        Retrieve schema from self.url via introsepction query
        """

        if refetch:
            if self.url:
                url = self.url
                req = {}
                req["operationName"] = "IntrospectionQuery"
                req["query"] = INTROSPECTION_QUERY_STRING
                res = requests.post(url, json=req)

                data = {}
                try:
                    data = res.json()
                except requests.models.HTTPError as http_error:
                    logger.exception(
                        f"HTTP error when decoding json: {http_error}")
                    return False
                except Exception as e:
                    logger.exception(f"Exception when decoding json: {e}")
                    return False
        else:
            if self.path:
                data = self.load_schema(self.path)
            else:
                return False

        if "data" in data and "__schema" in data["data"]:
            self.raw_data = data
            self.data = data["data"]["__schema"]
            if "extensions" in data and "traceId" in data["extensions"]:
                self.trace_id = data["extensions"]["traceId"]
        else:
            logger.debug("No schema found.")
            return False

        return True

    def save_schema(self) -> bool:
        with open(self.path, "w") as f:
            json.dump(self.raw_data, f)
        return True

    def load_schema(self, path: str) -> dict:
        """
        :path: path to GQL schema
        :return: schema which can be parsed as JSON
        """
        data = {}

        with open(path) as f:
            # TODO: handle parsing error
            data = json.load(f)

        return data

    def print_keys(self) -> None:
        """
        Print schema keys
        """
        if not self.data:
            self.get_schema(refresh=True)

        print(self.data.keys())

    def print_kinds(self) -> None:
        """
        Print unique kinds
        """
        if not self.data:
            self.get_schema(refresh=True)

        kinds = set()
        for type in self.data["types"]:
            if type["kind"] not in kinds:
                kinds.add(type["kind"])

        print(sorted(list(kinds)))

    def print_types(self) -> None:
        """
        Print unique types
        """
        if not self.data:
            self.get_schema(refresh=True)

        types = set()
        for type in self.data["types"]:
            if type["fields"]:
                for field in type["fields"]:
                    self.get_types_of_field_or_arg(types, field["type"])

        print(sorted(list(types)))

    def get_types_of_field_or_arg(self, types: set, object: dict, stack: list) -> None:
        """
        :param types: Current set of types related to a field
        :param object: Current type object to recurse on
        :param stack: Stack of types to process

        Helper function to recurse on an object["type"] to get all nested types
        """

        if object["name"] not in types and object["kind"] not in ["LIST", "NON_NULL", "SCALAR"]:
            types.add(object["name"])
            stack.append(object["name"])

        if not object["ofType"]:
            return

        self.get_types_of_field_or_arg(types, object["ofType"], stack)

    def get_type_object_of_field_or_arg(self, object: dict) -> dict:
        """
        :param object: Current type object to recurse on
        :return: deepest type object of a field or arg

        Helper function to recurse on an object["type"] to the deepest type object
        """

        if not object["ofType"]:
            return object
        else:
            return self.get_type_object_of_field_or_arg(object["ofType"])

    def get_names_of_field_or_arg(self, types: set, object: dict, stack: list) -> None:
        """
        :param types: Current set of types related to a field
        :param object: Current type object to recurse on
        :param stack: Stack of types to process

        Helper function to recurse on a field to get all nested field names
        """

        if object["name"] not in types and object["type"]["kind"] not in ["LIST", "NON_NULL", "SCALAR"]:
            types.add(object["type"]["name"])
            stack.append(object["type"]["name"])

        if not object["type"]["ofType"]:
            return

        self.get_types_of_field_or_arg(types, object["type"]["ofType"], stack)

    def build_type_map(self) -> None:
        """
        Helper function to build a map of GQL types and their indices in self.data
        """
        for i, type in enumerate(self.data["types"]):
            self.type_map[type["name"]] = i

    def build_operation_map(self) -> None:
        """
        Helper function to build a map of GQL operations and their indices as found in the parent operation's ("Query", "Mutation", "Subscription") field list
        """
        if not self.type_map:
            self.build_type_map()

        for operation_type in ["Query", "Mutation", "Subscription"]:
            self.operation_map[operation_type] = {}
            for i, operation_obj in enumerate(self.data["types"][self.type_map[operation_type]]["fields"]):
                self.operation_map[operation_type][operation_obj["name"]] = i

    def get_connected_types(self, stack: list, types=set()) -> set:
        """
        :param stack: stack of types to explore
        :param types: current set of connected types
        :return: set of types related to types in the stack param

        Function to get all types related to a field["type"]
        """

        if not self.type_map:
            self.build_type_map()

        while stack:
            type_name = stack.pop()
            i = self.type_map[type_name]
            if self.data["types"][i]["fields"]:
                for field in self.data["types"][i]["fields"]:
                    self.get_names_of_field_or_arg(types, field, stack)

        return types

    def build_test_schema_with_operations(self, operation_tuples: list, test_schema_path: str) -> None:
        """
        :param operation_tuples: list of tuples of (GQL operation type, GQL operation field)
          - eg. [("Mutation", "UniqueMutationName"),("Query", "UniqueQueryName")]
        :param test_schema_path: path to test schema dump

        Function to build test schema from operation names
        """

        if not self.type_map:
            self.build_type_map()

        if not self.operation_map:
            self.build_operation_map()

        # template for "Query", "Mutation", or "Subscription" objects
        # "field" parameter to be filled from operation_tuples
        operation_type_object_template = {
            "kind": "OBJECT", "name": "", "description": None, "fields": [], "inputFields": None, "interfaces": [], "enumValues": None, "possibleTypes": None
        }

        operation_type_object_map = {}
        for operation_type in ["Query", "Mutation", "Subscription"]:
            operation_type_object_map[operation_type] = copy.deepcopy(
                operation_type_object_template)
            operation_type_object_map[operation_type]["name"] = operation_type

        types = set()
        for operation_type, operation_name in operation_tuples:
            logger.debug(f"Processing {operation_type}: {operation_name}")
            # add operation object to operation type object fields
            operation_object = self.data["types"][self.type_map[operation_type]
                                                  ]["fields"][self.operation_map[operation_type][operation_name]]

            operation_type_object_map[operation_type]["fields"].append(
                operation_object)

            # find all associated types
            new_types = set()
            self.get_names_of_field_or_arg(
                types=new_types, object=operation_object, stack=[])
            for arg in operation_object["args"]:
                self.get_names_of_field_or_arg(
                    types=new_types, object=arg, stack=[])

            types = types.union(new_types)

        test_schema_types = self.get_connected_types(
            stack=list(types), types=types)

        test_schema = {}
        test_schema["data"] = {}
        test_schema["data"]["__schema"] = copy.deepcopy(self.data)
        del test_schema["data"]["__schema"]["types"]
        test_schema["data"]["__schema"]["types"] = []

        for type in self.data["types"]:
            if type["name"] in list(test_schema_types):
                test_schema["data"]["__schema"]["types"].append(type)

        # add non-empty operation type objects
        for operation_type, operation_type_object in operation_type_object_map.items():
            if operation_type_object["fields"] != []:
                test_schema["data"]["__schema"]["types"].append(
                    operation_type_object)

        with open(test_schema_path, "w") as f:
            json.dump(test_schema, f)

    def get_filled_operation_body(self, operation_tuple: tuple, out_file: str, deep_copy_hashes: bool = False) -> None:
        """
        :param operation_tuple: (GQL operation type, GQL operation field)
        - e.g. ("Mutation", "UniqueMutationName")
        :param out_file: Output file for GraphQL query
        :param deep_copy_hashes: Whether to deep copy type_hashes or not when nesting occurs. While both values, True or False, will disallow hashes, setting this value to True will allow objects to be repeated across sibling nodes since sibling objects won't be saved in the type_hashes set. True should allow for more complete requests as repeat types will be allowed across sibling nodes.
        :return: Filled data types for a GQL operation request body.

        Function that attempts to create a fully expanded GraphQL request based on the operation as passed in the operation_tuple parameter.

        Note: Not yet complete. Needs refactoring to handle Unions and a cleaner way to handle cycles. Currently uses hashing to avoid repeating types while exploring down a path.
        """

        if not self.type_map:
            self.build_type_map()

        if not self.operation_map:
            self.build_operation_map()

        request_body = []

        operation_type, operation_name = operation_tuple
        operation_object = self.data["types"][self.type_map[operation_type]
                                              ]["fields"][self.operation_map[operation_type][operation_name]]

        request_body.append(f"{operation_type}".lower())
        request_body.append("TestOperation")
        request_body.append("{")

        type_hashes = set()
        request_body.extend(self.get_names_of_field(
            object=operation_object, type_hashes=type_hashes, deep_copy_hashes=deep_copy_hashes))

        request_body.append("}")

        with open(out_file, 'w') as f:
            f.write(" ".join(request_body))

        return

    def get_filled_object_body(self, object: dict, type_hashes: set, deep_copy_hashes: bool = False) -> list:
        """
        :param object: GQL object
        :param type_hashes: Hashes of objects that have been seen. Used to avoid cycles.
        :param deep_copy_hashes: See `get_filled_operation_body`
        :return: List of strings that, when concatenated, represents a fully expanded GQL object for a GraphQL request

        Helper function for `get_filled_operation_body`. Returns nested fields for a GQL object as part of a GQL operation request body.
        """
        hash = hash_properties(properties=object)
        request_body = []
        if hash in type_hashes:
            return request_body

        type_hashes.add(hash)

        request_body.append("{")
        fields_request_body = []

        if object["kind"] == "UNION":
            for possible_type in object["possibleTypes"]:
                possible_type_object = self.data["types"][self.type_map[possible_type["name"]]]
                type_hashes = copy.deepcopy(
                    type_hashes) if deep_copy_hashes else type_hashes
                filled_object_body = self.get_filled_object_body(
                    object=possible_type_object, type_hashes=type_hashes)
                if filled_object_body:
                    fields_request_body.append(
                        f'... on {possible_type["name"]}')
                    fields_request_body.extend(filled_object_body)
        else:
            for field in object["fields"]:
                if not field["isDeprecated"]:
                    type_hashes = copy.deepcopy(
                        type_hashes) if deep_copy_hashes else type_hashes
                    fields_request_body.extend(self.get_names_of_field(
                        object=field, type_hashes=type_hashes))

        if fields_request_body == []:
            logger.debug(f'Request body was empty for {object["name"]}')
            return fields_request_body
        request_body.extend(fields_request_body)
        if fields_request_body:
            request_body.append("}")
        return request_body

    def get_names_of_field(self, object: dict, type_hashes: set, deep_copy_hashes: bool = False) -> list:
        """
        :param object: GQL object
        :param type_hashes: Hashes of objects that have been seen. Used to avoid cycles.
        :param deep_copy_hashes: See `get_filled_operation_body`
        :return: List of strings that, when concatenated, represents the fields of fully expanded GQL object for a GraphQL request

        Helper function for `get_filled_object_body`. Returns names of all nested fields in list form.
        """

        request_body = []

        type_object = self.get_type_object_of_field_or_arg(object["type"])
        if type_object["kind"] in ["INTERFACE", "INPUT_OBJECT"]:
            return request_body

        if type_object["kind"] not in ["SCALAR", "ENUM"]:
            type_properties = self.data["types"][self.type_map[type_object["name"]]]
            filled_object_body = self.get_filled_object_body(
                object=type_properties, type_hashes=type_hashes, deep_copy_hashes=deep_copy_hashes)
            if filled_object_body:
                request_body.append(object["name"])
                request_body.extend(filled_object_body)
        else:
            request_body.append(object["name"])

        return request_body

    def get_name_of_field_or_arg(self, object: dict) -> None:
        """
        :param types: Current set of types related to a field
        :param type: Current type object to recurse on
        :param stack: Stack of types to process

        Helper function to recurse on an object["type"] to get all nested types
        """
        if not object["type"]["ofType"]:
            return object["type"]["name"]

        self.get_types_of_field_or_arg(object["type"]["ofType"])
