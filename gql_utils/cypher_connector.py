from neo4j import GraphDatabase
from gql_utils.gql_constants import Relationship, RELATIONSHIP_MAP
from utils.common_utils import hash_properties, get_logger

logger = get_logger()


class CypherConnector:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.session = None

    def open_session(self):
        self.session = self.driver.session()
        return self.session

    def close_session(self):
        self.driver.close()
        self.session = None

    def update_db(self, gql_types: list) -> None:
        """
        :param gql_types: 
            GQL schema from Introspection response found in response["__schema"]["types"]

        Translate GQL introspection schema to Cypher and updates the db
        """
        self.open_session()

        for type in gql_types:
            logger.info(f"Creating/updating type {type['name']}")
            hash = hash_properties(properties=type)
            id = self._create_or_update_node(gql_type=type, hash=hash)
            if id < 0:
                logger.debug("Did not update or create new ndoe.")

        self.close_session()

    def _create_or_update_node(self, gql_type: dict, hash: str) -> int:
        """
        :param gql_type: GQL type
        :hash: md5 hash of the GQL type
        :return: False if error

        If node already exists, update node, else, create a new node. Not to be used when linking fields to types.
        """

        # if node exists, update
        nodes = self.query_nodes(
            feature="NAME", hash=hash, name=gql_type["name"], verbose=False)

        if len(nodes) >= 1:
            for node in nodes:
                # type and name must both match since a field may have same name as a data type
                existing_label = list(node.labels)[0]
                existing_name = node._properties["name"]
                if existing_label == gql_type["kind"] and existing_name == gql_type["name"]:
                    logger.info("Node already exists.")
                    return self._update_node_add_entities(old_hash=node._properties["hash"], new_hash=hash, properties=gql_type)
        return self._create_node_add_entities(hash=hash, properties=gql_type)

    def _update_node_add_entities(self, old_hash: str, new_hash: str, properties: dict) -> int:
        """
        :param properties: GQL type properties which may include: "kind", "name", "description", "fields", "inputFields", "interfaces", "enumValues", and "possibleTypes" 
        :hash: md5 hash of the GQL type
        :return: ID of node

        Create a neo4j node with edges to its fields using Cypher
        """
        id = -1
        if old_hash != new_hash:
            id = self._update_node(hash=new_hash, properties=properties)
            if not self._add_relationships(id=id, properties=properties):
                return -1
        return id

    def _create_node_add_entities(self, hash: str, properties: dict) -> int:
        """
        :param properties: GQL type properties which may include: "kind", "name", "description", "fields", "inputFields", "interfaces", "enumValues", and "possibleTypes" 
        :hash: md5 hash of the GQL type
        :return: ID of node

        Create a neo4j node with edges to its fields using Cypher
        """

        id = self._create_node(hash=hash, properties=properties)
        if id < 0:
            logger.warn("Create node failed")
            return id
        return id if self._add_relationships(id=id, properties=properties) else -1

    def _update_node(self, hash: str, properties: dict) -> int:
        """
        :param hash: md5 hash of the GQL type
        :param properties: properties to add
        :param gql_type: GQL type["kind"]
        :return: False if error

        Update a neo4j node from the GQL type using Cypher.
        Requires an open driver session. Assumes that only one node of the "name" exists.
        """

        if not self._basic_properties_check(properties=properties):
            return -1

        if not hash:
            logger.warn("Could not create node: missing 'hash'")
            logger.warn(properties)
            return -1

        cql = f'MATCH (n:{properties["kind"]}'
        cql += f'{{name: "{properties["name"]}"}})'

        if "description" in properties and properties["description"]:
            description = properties["description"].replace('"', r'\"')
            cql += f'SET n.description = "{description}"'
        if "interfaces" in properties and properties["interfaces"]:
            cql += f'SET n.interfaces = "{properties["interfaces"]}"'
        if "enum_values" in properties and properties["enum_values"]:
            cql += f'SET n.enum_values = "{properties["enum_values"]}"'
        if "isDeprecated" in properties and properties["isDeprecated"]:
            cql += f'SET n.isDeprecated = "{properties["isDeprecated"]}"'
        if "deprecationReason" in properties and properties["deprecationReason"]:
            cql += f'SET n.deprecationReason = "{properties["deprecationReason"]}"'
        # property of arg
        if "defaultValue" in properties and properties["defaultValue"]:
            cql += f'SET n.defaultValue = "{properties["defaultValue"]}"'
        cql += f'SET n.hash = "{hash}"'
        cql += "RETURN id(n)"

        res = self.session.run(cql)
        value = res.value()

        return value[0]

    def _create_node(self, hash: str, properties: dict) -> int:
        """
        :param hash: md5 hash of the GQL type
        :param properties: properties to add
        :param gql_type: GQL type["kind"]
        :return: False if error

        Create a neo4j node from the GQL type, field, arg, inputField, or possibleType, using Cypher.
        Requires an open driver session.
        """

        # create temporary hash
        if not hash:
            logger.warn("Could not create node: missing 'hash'")
            logger.warn(properties)
            return -1

        cql = f'CREATE (n:{properties["kind"]}'
        cql += f'{{name: "{properties["name"]}"'

        if "description" in properties and properties["description"]:
            description = properties["description"].replace('"', r'\"')
            cql += f', description: "{description}"'
        if "interfaces" in properties and properties["interfaces"]:
            cql += f', interfaces: "{properties["interfaces"]}"'
        if "enum_values" in properties and properties["enum_values"]:
            cql += f', enum_values: "{properties["enum_values"]}"'
        if "isDeprecated" in properties and properties["isDeprecated"]:
            cql += f', isDeprecated: "{properties["isDeprecated"]}"'
        if "deprecationReason" in properties and properties["deprecationReason"]:
            deprecation_reason = properties["deprecationReason"].replace(
                '"', r'\"')
            cql += f', deprecationReason: "{deprecation_reason}"'
        # property of arg
        if "defaultValue" in properties and properties["defaultValue"]:
            default_value = properties["defaultValue"].replace('"', r'\"')
            cql += f', defaultValue: "{default_value}"'
        cql += f', hash: "{hash}"'
        cql += "}) RETURN id(n)"

        res = self.session.run(cql)
        id = res.value()[0]

        return id

    def query_nodes(self, feature: str, hash: str, name: str, verbose: bool = False) -> list:
        """
        :param feature: feature to query by: "HASH", "NAME"
        :param hash: (Optional) hash to query nodes by
        :param name: name to query nodes by
        :param verbose: print results
        :return: list of neo4j nodes

        Query a neo4j node by name.
        Requires an open driver session.
        """
        if feature == "HASH":
            feat = hash
            cql = f'MATCH (n {{hash: "{feat}"}}) RETURN n'
        elif feature == "NAME":
            feat = name
            cql = f'MATCH (n {{name: "{feat}"}}) RETURN n'
        res = self.session.run(cql)
        nodes = res.value()
        return nodes

    def _query_relationships(self, hash_a: str, hash_b: str, relationship_from_a: str) -> list:
        """
        :param hash_a: md5 hash properties of a
        :param hash_b: md5 hash properties of b
        :param relationship_from_a: reltype from a->b
        :return: list of neo4j relationships

        Query a relationship from a->b of type relationship_from_a using Cypher.
        """
        relationships = []
        entity_b = f'(b {{hash: "{hash_b}"}})' if hash_b else "(b)"
        cql = f'MATCH (a {{hash: "{hash_a}"}})-[r:{relationship_from_a}]->{entity_b} RETURN r'
        res = self.session.run(cql)
        relationships = res.value()
        return relationships

    def _add_relationships(self, id: int, properties: dict, bidirectional: bool = False) -> bool:
        """
        :param hash: node id of GQL object
        :param properties: dict of properties
        :param bidirectional:
            create one-way (child-to-parent) or two-way relationship between nodes
            note: setting bidirectional to true will result in cycles when querying paths
        :return: True if successful

        Properties may include: "kind", "name", "description", "fields", "inputFields", "interfaces", "enumValues", "possibleTypes", "hash"
        """

        # add edges, need to pass in node
        if properties["fields"]:
            for field in properties["fields"]:
                if not self._add_entity(id=id, properties=field, kind="FIELD", bidirectional=bidirectional):
                    return False

        # TODO: add support for interfaces and enums
        # for interface in properties["interfaces"]:
        #     self._add_interfaces(type=input_field)

        # for enumValue in properties["enumValues"]:
        #     self._add_enumValue(type=input_field)

        if properties["possibleTypes"]:
            for possible_type in properties["possibleTypes"]:
                if not self._add_entity(
                        id=id, properties=possible_type, kind="POSSIBLE_TYPE", bidirectional=bidirectional):
                    return False

        return True

    def _add_entity(self, id: int, properties: dict, kind: str, bidirectional: bool = False) -> bool:
        """
        :param id: Neo4j node id
        :param properties: 
            contains "name", "description", "args", "type", "interfaces", "isDeprecated", "deprecationReason", "defaultValue"
        :param kind:
            child entity kind; one of "FIELD", "ARG", "INPUT_FIELD", "SCALAR", "ENUM", "POSSIBLE_TYPE", "INTERFACE", "OBJECT"
        :param bidirectional:
            create one-way or two-way relationship between neighboring nodes
            note: setting bidirectional to true will result in cycles when querying paths
        :return: True if successful

        Add field to GQL type using Cypher
        """

        relationship_from_a = None
        relationship_from_b = None

        if kind in ["FIELD", "ARG", "INPUT_FIELD"]:
            # assign the entity a type and create an entity-to-type relationship
            properties["kind"] = kind
            entity_hash = hash_properties(properties=properties)
            entity_id = self._create_node(
                hash=entity_hash, properties=properties)
            type_properties = self._get_object_type(obj=properties["type"])

            # check if a type relationship already exists for the entity
            relationships = self._query_relationships(
                hash_a=entity_hash, hash_b=None, relationship_from_a=Relationship.OF_TYPE.value)

            # if not, then add type relationship
            if not relationships:
                type_id = -1
                if type_properties["kind"] != "SCALAR":
                    # query for existing type node by name
                    nodes = self.query_nodes(
                        feature="NAME", hash="", name=type_properties["name"])
                    if len(nodes) > 1:
                        logger.debug(
                            f'Query for existing {type_properties["kind"]} returned multiple nodes')
                        for node in nodes:
                            logger.debug(node)
                    elif len(nodes) == 1:
                        type_id = nodes[0].id

                if type_id < 0:
                    # create new nodes for the type object
                    type_hash = hash_properties(
                        properties=type_properties)
                    type_id = self._create_node(
                        hash=type_hash, properties=type_properties)

                # create entity-to-type relationship
                if type_properties["is_list"]:
                    relationship_from_a, relationship_from_b = RELATIONSHIP_MAP["LIST"]
                else:
                    relationship_from_a, relationship_from_b = RELATIONSHIP_MAP["TYPE"]

                relationships = self._create_relationship(
                    id_a=entity_id, id_b=type_id, relationship_from_a=relationship_from_a if bidirectional else None, relationship_from_b=relationship_from_b)

                if len(relationships) != 2:
                    logger.warn(
                        f"Something went wrong with relationships between nodes {entity_hash} and {type_hash}")
                    return False

            # if field has args, add args
            if kind == "FIELD":
                if properties["args"]:
                    for arg in properties["args"]:
                        if not self._add_entity(id=entity_id, properties=arg, kind="ARG"):
                            logger.warn(
                                f"Something went wrong adding arg: {arg} to field with id {entity_id}")
                            return False

        else:
            # query for existing entity node by name
            entity_id = -1
            if properties["kind"] != "SCALAR":
                nodes = self.query_nodes(
                    feature="NAME", hash="", name=properties["name"])
                if len(nodes) > 1:
                    logger.debug(
                        f'Query for {properties["name"]} returned multiple nodes')
                    for node in nodes:
                        logger.debug(node)
                    return False
                elif len(nodes) == 1:
                    entity_id = nodes[0].id
            if entity_id < 0:
                # create temporary node
                entity_hash = hash_properties(properties=properties)
                entity_id = self._create_node(
                    hash=entity_hash, properties=properties)

        relationship_from_a, relationship_from_b = RELATIONSHIP_MAP[kind]

        if entity_id < 0:
            logger.warn(f"No entity_id")
            return False

        # create obj-to-entity relationship
        relationships = self._create_relationship(
            id_a=id, id_b=entity_id, relationship_from_a=relationship_from_a if bidirectional else None, relationship_from_b=relationship_from_b)

        if len(relationships) != 2:
            logger.warn(
                f"Something went wrong with relationships between node ids {id} and {entity_id}")
            return False

        return True

    def _create_relationship(self, id_a: int, id_b: int, relationship_from_a: str, relationship_from_b: str = None) -> tuple:
        """
        :param id_a: neo4j node id of a
        :param id_b: neo4j node id of b
        :param relationship_from_a: reltype from a->b
        :param relationship_from_b: reltype from b->a

        Create a relationship from b->a and a->b of types relationship_from_b and relationship_from_a respectively, using Cypher.
        """

        cql = f'MATCH (a), (b) WHERE id(a) = {id_a} AND id(b) = {id_b} CREATE (b)-[r1:{relationship_from_b}]->(a)'

        if relationship_from_a:
            cql += f"CREATE (a)-[r2:{relationship_from_a}]->(b)"
            cql += "RETURN r1, r2"
        else:
            cql += "RETURN r1"

        res = self.session.run(cql)
        relationship = res.value()[0].nodes
        return relationship

    def _get_object_type(self, obj: dict, is_list=False) -> dict:
        """
        :param type: Type object of a GQL parent object. Has three properties: "kind", "name", "ofType"

        Return field type properties in form of a dict:
          - name: str
          - kind: str 
          - is_list: bool
        """
        if not is_list:
            is_list = obj["ofType"] == "LIST"

        if not obj["ofType"]:
            return {"kind": obj["kind"], "name": obj["name"], "is_list": is_list}

        return self._get_object_type(obj=obj["ofType"], is_list=is_list)

    def _basic_properties_check(self, properties: dict) -> bool:
        """
        :param properties: GQL type properties
        :return: 

        Perform a basic properties check for existence of "name", "kind", and "hash
        """

        if "name" not in properties:
            print("Missing 'name' property")
            print(properties, hash)
            return False
        if "kind" not in properties:
            print("Missing 'kind' property")
            print(properties, hash)
            return False

        return True

    def get_name_from_id(self, id: int) -> str:
        """
        :param id_a: neo4j node id of a
        :return: name of neo4j node
        """
        cql = f'MATCH (n) WHERE ID(n)={id} RETURN n.name'
        res = self.session.run(cql)
        value = res.value()
        return value[0]

    def query_operations(self, type_name: str, limit: int, show_types: bool = False) -> list:
        """
        :param type_name: name of GQL type
        :param limit: limit on number of paths to query for per operation
        :param show_types: if true, show type objects in query

        Query operation paths that return a GQL type.
        """

        if not self.session:
            self.open_session()

        cql = f'MATCH (n {{name:"{type_name}"}})-[r*1..10]->(m {{name: "Mutation"}}) RETURN r LIMIT {limit} UNION MATCH (n {{name:"{type_name}"}})-[r*1..10]->(m {{name: "Query"}}) RETURN r LIMIT {limit}'

        logger.debug(f"Running query: {cql}")
        res = self.session.run(cql)

        paths = []
        relationship_paths = res.value()
        for relationship_path in relationship_paths:
            new_path = []
            for edge in relationship_path:
                if show_types or (edge.type != Relationship.IS_TYPE_FOR.value):
                    id = edge.nodes[0].id
                    name = self.get_name_from_id(id)
                    new_path.append(name)
            paths.append(" -> ".join(reversed(new_path)))
        return paths
