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
    Scope = 0
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

    def toString(self):
        if self == ValueType.vec2f:
            return 'float2'
        if self == ValueType.vec3f:
            return 'float3'
        if self == ValueType.vec4f:
            return 'float4'
        return self.name


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

def dictionaryToString(dic, space):
    indent = space + TAB_SPACE
    ret = '{\n'
    for key, value in dic.items():
        if type(value) is dict:
            ret += indent + 'dictionary ' + key + ' = '
            ret += dictionaryToString(value, indent)
        elif type(value) is str:
            ret += indent + 'string ' + key + ' = "' + value + '"\n'
        elif type(value) is bool:
            ret += indent + 'bool ' + key + ' = '
            ret += '1\n' if value else '0\n'
        else:
            valueType = getValueType(value)
            ret += indent + valueType.toString() + ' ' + key + ' = '
            ret += valueToString(value) + '\n'
    return ret + space + '}\n'

def propertyToString(prop, space):
    if type(prop) is str:
        return '"' + prop + '"'
    if type(prop) is dict:
        return dictionaryToString(prop, space)
    return valueToString(prop)

class UsdAttribute:
    def __init__(self, name = '', value = None, type = ValueType.Invalid):
        self.name = name
        self.value = value
        self.frames = []
        self.qualifiers = []
        self.properties = {}
        self.valueType = type
        self.valueTypeStr = None
        self.parent = None
        if type == ValueType.Invalid:
            self.valueType = self.getValueType()
        if self.isRelationship():
            self.valueTypeStr = 'rel'

    def __str__(self):
        return self.toString()

    def __setitem__(self, key, item):
        self.properties[key] = item

    def __getitem__(self, key):
        return self.properties[key]

    def toString(self, space = ''):
        ret = space
        att = self.value if self.isConnection() else self
        if len(att.qualifiers) > 0:
            ret += ' '.join(q for q in att.qualifiers) + ' '
        ret += att.valueTypeToString()
        ret += '[]' if att.isArray() else ''
        ret += ' ' + self.name
        if self.isConnection():
            ret += '.connect = <' + self.value.getPathStr() + '>'
        elif self.isRelationship():
            ret += ' = <' + self.value.getPathStr() + '>'
        elif len(self.frames) > 0:
            ret += self.framesToString(space)
        else:
            if self.value != None:
                ret += ' = ' + self.valueToString()
                if len(self.properties) > 0:
                    ret += self.propertiesToString(space)
        return ret + '\n'

    def propertiesToString(self, space):
        indent = space + TAB_SPACE
        ret = ' (\n'
        for k, v in self.properties.items():
            ret += indent + k + ' = ' + propertyToString(v, indent) + '\n'
        return ret + space + ')'

    def framesToString(self, space):
        indent = space + TAB_SPACE
        ret = '.timeSamples = {\n'
        for frame, value in self.frames:
            ret += indent + '%d: '%frame + valueToString(value) + ',\n'
        return ret + space + '}'

    def addQualifier(self, qualifier):
        self.qualifiers.append(qualifier)

    def addTimeSample(self, frame, value):
        if self.valueType == ValueType.Invalid:
            self.valueType = getValueType(value)
        self.frames.append((frame, value))

    def valueToString(self):
        if self.isConnection():
            return self.value.valueToString()
        if self.valueType == ValueType.token or self.valueType == ValueType.string:
            if type(self.value) is list:
                return '[' + ', '.join('"' + v + '"' for v in self.value) + ']'
            return '"' + valueToString(self.value) + '"'
        if self.valueType == ValueType.asset:
            return '@' + valueToString(self.value) + '@'
        return valueToString(self.value)

    def valueTypeToString(self):
        if self.valueTypeStr != None:
            return self.valueTypeStr
        return self.valueType.toString()

    def isArray(self):
        if self.isConnection():
            return self.value.isArray()
        if len(self.frames) > 0:
            return type(self.frames[0][1]) is list
        return self.value != None and type(self.value) is list

    def isConnection(self):
        return type(self.value) is UsdAttribute

    def isRelationship(self):
        return type(self.value) is UsdClass

    def getPathStr(self):
        if self.isConnection():
            return self.value.getPathStr()
        if self.parent == None:
            return self.name
        return self.parent.getPathStr() + '.' + self.name

    def getValueType(self):
        if self.isConnection():
            return self.value.getValueType()
        elif self.isRelationship():
            return ValueType.Invalid
        return getValueType(self.value)


class UsdClass:
    def __init__(self, name = '', type = ClassType.Scope):
        self.name = name
        self.classType = type
        self.attributes = []
        self.children = []
        self.parent = None

    def __str__(self):
        return self.toString()

    def __setitem__(self, key, item):
        if type(item) is ValueType:
            self.createAttribute(key, type=item)
        else:
            self.createAttribute(key, item)

    def __getitem__(self, key):
        return next((att for att in self.attributes if att.name == key), None)

    def toString(self, space = ''):
        indent = space + TAB_SPACE
        line = indent + '\n'
        ret = space + 'def ' + self.classType.name + ' "' + self.name + '"\n'
        ret += space + '{\n'
        ret += ''.join(att.toString(indent) for att in self.attributes)
        ret += line if len(self.children) > 0 else ''
        ret += line.join(c.toString(indent) for c in self.children)
        return ret + space + '}\n'

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
        return self.addChild(UsdClass(name, type))

    def getChild(self, name):
        return next((c for c in self.children if c.name == name), None)

    def getPathStr(self):
        if self.parent == None:
            return '/' + self.name
        return self.parent.getPathStr() + '/' + self.name


class UsdData:
    def __init__(self):
        self.properties = {}
        self.children = []

    def __str__(self):
        return self.toString()

    def __setitem__(self, key, item):
        self.properties[key] = item

    def __getitem__(self, key):
        return self.properties[key]

    def toString(self):
        ret = '#usda 1.0\n'
        ret += self.propertiesToString()
        ret += '\n'
        return ret + ''.join(c.toString() for c in self.children)

    def propertiesToString(self):
        ret = '(\n'
        for k, v in self.properties.items():
            ret += TAB_SPACE + k + ' = ' + propertyToString(v, TAB_SPACE) + '\n'
        return ret + ')\n'

    def addChild(self, child):
        child.parent = None
        self.children.append(child)
        return child

    def createChild(self, name, type):
        return self.addChild(UsdClass(name, type))

    def writeUsda(self, filePath):
        f = open(filePath, 'w')
        f.write(str(self))
        f.close()
