from enum import Enum

TAB_SPACE = '   '


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


class ClassType(Enum):
    PseudoRoot = 0
    Xform = 1
    Mesh = 2
    SkelRoot = 3
    Skeleton = 4
    SkelAnimation = 5
    Material = 6
    Shader = 7

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


def getTupleValueType(value):
    l = len(value)
    if l > 0:
        t = type(value[0])
        if t == int:
            if l == 2:
                return ValueType.vec2i
            if l == 3:
                return ValueType.vec3i
            if l == 4:
                return ValueType.vec4i
        elif t == float:
            if l == 2:
                return ValueType.vec2f
            if l == 3:
                return ValueType.vec3f
            if l == 4:
                return ValueType.vec4f
        elif t == tuple and len(value[0]) > 0 and type(value[0][0]) == float:
            l = len(value[0])
            if l == 2:
                return ValueType.matrix2d
            if l == 3:
                return ValueType.matrix3d
            if l == 4:
                return ValueType.matrix4d
    return ValueType.Invalid


def getValueType(value):
    t = type(value)
    if t == bool:
        return ValueType.bool
    if t == int:
        return ValueType.int
    if t == float:
        return ValueType.float
    if t == str:
        if len(value) > 0 and value[0] == '@':
            return ValueType.asset
        return ValueType.token
    if t == tuple:
        return getTupleValueType(value)
    if t == list and len(value) > 0:
        if type(value[0]) == str:
            return ValueType.token
        return getValueType(value[0])
    if t == SpecifierType:
        return ValueType.Specifier
    if t == dict:
        return ValueType.Dictionary
    return ValueType.Invalid


def getValueTypeStr(typeStr):
    typeStr = typeStr.replace('[]', '')
    if typeStr == 'float3':
        return ValueType.vec3f
    return ValueType[typeStr]

def valueToString(value, reduced = False):
    if type(value) is str:
        return value
    if type(value) is int:
        return '%d' % value
    if type(value) is float:
        return '%.6g' % round(value, 6)
    if type(value) is list:
        if reduced and len(value) > 3:
            return '[' + ', '.join(valueToString(item) for item in value[:3]) + ', ...]'
        else:
            return '[' + ', '.join(valueToString(item) for item in value) + ']'
    if type(value) is tuple:
        return '(' + ', '.join(valueToString(item) for item in value) + ')'
    return ''


class UsdAttribute:
    def __init__(self, name = '', value = None, type = ValueType.Invalid):
        self.name = name
        self.value = value
        self.valueType = type
        self.parent = None
        if type == ValueType.Invalid:
            self.valueType = getValueType(value)

    def __str__(self):
        ret = self.valueType.name+' '+self.name
        if self.value != None:
            ret += ' = '+valueToString(self.value)
        return ret

    def getPathStr(self):
        if self.parent == None:
            return self.name
        return self.parent.getPathStr() + '/' + self.name

class UsdClass:
    def __init__(self, name = '', type = ClassType.PseudoRoot):
        self.name = name
        self.classType = type
        self.properties = {}
        self.attributes = []
        self.children = []
        self.parent = None


    def __str__(self):
        return self.toString()


    def toString(self, indent = ''):
        ret = indent
        if self.classType == ClassType.PseudoRoot:
            ret += '#usda 1.0\n'
            ret += self.propertiesToString(indent)
            ret += indent+'\n'
            ret += self.childrenToString(indent)
            ret += '\n'
        else:
            ret += 'def '+self.classType.name+' "'+self.name+'"\n'
            ret += indent+'{\n'
            ret += self.attributesToString(indent+TAB_SPACE)
            #ret += self.childrenToString(indent+TAB_SPACE)
            ret += indent + '}\n'
        return ret


    def propertiesToString(self, indent):
        ret = indent + '(\n'
        ret += indent + ')\n'
        return ret

    def attributesToString(self, indent):
        ret = ''
        for att in self.attributes:
            ret += indent + str(att) + '\n'
        ret += indent+'\n'
        return ret

    def childrenToString(self, indent):
        ret = ''
        for child in self.children:
            ret += child.toString(indent)
        return ret

    def addAttribute(self, attribute):
        attribute.parent = self
        self.attributes.append(attribute)
        return attribute

    def createAttribute(self, name, value = None, type = ValueType.Invalid):
        return self.addAttribute(UsdAttribute(name, value, type))

    def addChild(self, child):
        child.parent = self
        self.children.append(child)
        return child

    def createChild(self, name, type):
        return self.addClass(UsdClass(name, type))

    def getPathStr(self):
        if self.parent == None:
            return self.name
        return self.parent.getPathStr() + '/' + self.name
