from enum import Enum


class SpecifierType(Enum):
    Def = 0
    Over = 1
    Class = 2


class SpecType(Enum):
    Attribute   = 1
    Connection  = 2
    Expression  = 3
    Mapper      = 4
    MapperArg   = 5
    Prim        = 6
    PseudoRoot  = 7
    Relationship = 8
    RelationshipTarget = 9
    Variant     = 10
    VariantSet  = 11


class ValueType(Enum):
    Invalid = 0
    bool = 1
    uchar = 2
    int = 3
    uint = 4
    int64 = 5
    uint64 = 6
    half = 7
    float = 8
    double = 9
    string = 10
    token = 11
    asset = 12
    matrix2d = 13
    matrix3d = 14
    matrix4d = 15
    quatd = 16
    quatf = 17
    quath = 18
    vec2d = 19
    vec2f = 20
    vec2h = 21
    vec2i = 22
    vec3d = 23
    vec3f = 24
    vec3h = 25
    vec3i = 26
    vec4d = 27
    vec4f = 28
    vec4h = 29
    vec4i = 30
    Dictionary = 31
    TokenListOp = 32
    StringListOp = 33
    PathListOp = 34
    ReferenceListOp = 35
    IntListOp = 36
    Int64ListOp = 37
    UIntListOp = 38
    UInt64ListOp = 39
    PathVector = 40
    TokenVector = 41
    Specifier = 42
    Permission = 43
    Variability = 44
    VariantSelectionMap = 45
    TimeSamples = 46
    Payload = 47
    DoubleVector = 48
    LayerOffsetVector = 49
    StringVector = 50
    ValueBlock = 51
    Value = 52
    UnregisteredValue = 53
    UnregisteredValueListOp = 54
    PayloadListOp = 55
