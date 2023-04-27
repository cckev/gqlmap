from enum import Enum


class OperationType(Enum):
    QUERY = "Query"
    MUTATION = "Mutation"
    SUBSCRIPTION = "Subscription"


class Relationship(Enum):
    """
    if (a)-[:OF_TYPE]->(b) ==> (b)-[:IS_TYPE_FOR]->(a)
    """
    HAS_FIELD = "HAS_FIELD"
    IS_FIELD_OF = "IS_FIELD_OF"
    HAS_ARG = "HAS_ARG"
    IS_ARG_OF = "IS_ARG_OF"
    HAS_POSSIBLE_TYPE = "HAS_POSSIBLE_TYPE"
    IS_POSSIBLE_TYPE_OF = "IS_POSSIBLE_TYPE_OF"
    HAS_INPUT_FIELD = "HAS_INPUT_FIELD"
    IS_INPUT_FIELD_OF = "IS_INPUT_FIELD_OF"
    OF_TYPE = "OF_TYPE"
    IS_TYPE_FOR = "IS_TYPE_FOR"
    IS_LIST_OF = "IS_LIST_OF"
    IS_ITEM_FROM_LIST = "IS_ITEM_FROM_LIST"
    HAS_INTERFACE = "HAS_INTERFACE"
    IS_INTERFACE_FOR = "IS_INTERFACE_FOR"


RELATIONSHIP_MAP = {
    "FIELD": (Relationship.HAS_FIELD.value, Relationship.IS_FIELD_OF.value),
    "ARG": (Relationship.HAS_ARG.value, Relationship.IS_ARG_OF.value),
    "TYPE": (Relationship.OF_TYPE.value, Relationship.IS_TYPE_FOR.value),
    "POSSIBLE_TYPE": (Relationship.HAS_POSSIBLE_TYPE.value, Relationship.IS_POSSIBLE_TYPE_OF.value),
    "INPUT_FIELD": (Relationship.HAS_INPUT_FIELD.value, Relationship.IS_INPUT_FIELD_OF.value),
    "INTERFACE": (Relationship.HAS_INTERFACE.value, Relationship.IS_INTERFACE_FOR.value),
    "LIST": (Relationship.IS_LIST_OF.value, Relationship.IS_ITEM_FROM_LIST.value)
}

GQL_KINDS = [
    "ENUM",
    "INPUT_OBJECT",
    "INTERFACE",
    "OBJECT",
    "SCALAR",
    "UNION"
]

GQL_TYPES = [
    "ENUM",
    "INTERFACE",
    "LIST",
    "NON_NULL",
    "OBJECT",
    "SCALAR",
    "UNION"
]

INTROSPECTION_QUERY_STRING = "query IntrospectionQuery { __schema { queryType { name } mutationType { name } subscriptionType { name } types { ...FullType } directives { name description locations args { ...InputValue } } } } fragment FullType on __Type { kind name description fields(includeDeprecated: true) { name description args { ...InputValue } type { ...TypeRef } isDeprecated deprecationReason } inputFields { ...InputValue } interfaces { ...TypeRef } enumValues(includeDeprecated: true) { name description isDeprecated deprecationReason } possibleTypes { ...TypeRef } } fragment InputValue on __InputValue { name description type { ...TypeRef } defaultValue } fragment TypeRef on __Type { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name } } } } } } } }"
