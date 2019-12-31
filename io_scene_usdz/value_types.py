from enum import Enum

TAB = '   '


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
    GeomSubset = 8


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

def getValueTypeFromStr(typeStr):
    typeStr = typeStr.replace('[]', '')
    if typeStr in ('float2', 'texCoord2f'):
        return ValueType.vec2f
    if typeStr in ('float3', 'color3f', 'normal3f', 'point3f'):
        return ValueType.vec3f
    if typeStr in ('float4', 'color4f'):
        return ValueType.vec4f
    if typeStr in ('double2', 'texCoord2d'):
        return ValueType.vec2d
    if typeStr in ('double3', 'color3d', 'normal3d', 'point3d'):
        return ValueType.vec3d
    if typeStr == 'double4':
        return ValueType.vec4d
    return ValueType[typeStr]

def valueToString(value, reduced = False):
    if type(value) is str:
        return value
    if type(value) is int:
        return '%d' % value
    if type(value) is float:
        return '%.6g' % round(value, 6)
    if type(value) is bool:
        return 'true' if value else 'false'
    if type(value) is list:
        if reduced and len(value) > 3:
            return '[' + ', '.join(valueToString(item) for item in value[:3]) + ', ...]'
        else:
            return '[' + ', '.join(valueToString(item) for item in value) + ']'
    if type(value) is tuple:
        return '(' + ', '.join(valueToString(item) for item in value) + ')'
    return ''

def dictionaryToString(dic, space):
    indent = space + TAB
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
    if type(prop) is UsdAttribute:
        return '<' + prop.getPathStr() + '>'
    if type(prop) is UsdPrim:
        return '<' + prop.getPathStr() + '>'
    return valueToString(prop)

def interleaveLists(lists):
    return [x for x in itertools.chain(*itertools.zip_longest(*lists)) if x is not None]

class UsdAttribute:
    def __init__(self, name = '', value = None, type = ValueType.Invalid):
        self.name = name
        self.value = value
        self.frames = []
        self.qualifiers = []
        self.metadata = {}
        self.valueType = type
        self.valueTypeStr = None
        self.parent = None
        self.pathIndex = -1
        self.pathJump = 0
        if type == ValueType.Invalid:
            self.valueType = self.getValueType()
        if self.isRelationship():
            self.valueTypeStr = 'rel'

    def __str__(self):
        return self.toString()

    def __setitem__(self, key, item):
        self.metadata[key] = item

    def __getitem__(self, key):
        return self.metadata[key]

    def toString(self, space = '', debug = False):
        ret = space
        att = self.value if self.isConnection() else self
        if len(att.qualifiers) > 0:
            ret += ' '.join(q for q in att.qualifiers) + ' '
        ret += att.valueTypeToString()
        ret += ' ' + self.name
        if self.isConnection():
            ret += '.connect = <' + self.value.getPathStr() + '>'
        elif self.isRelationship():
            ret += ' = <' + self.value.getPathStr() + '>'
        elif self.hasTimeSamples():
            ret += self.framesToString(space, debug)
        else:
            if self.value != None:
                ret += ' = ' + self.valueToString(debug)
                if len(self.metadata) > 0:
                    ret += self.metadataToString(space)
        return ret + '\n'

    def metadataToString(self, space):
        indent = space + TAB
        ret = ' (\n'
        for k, v in self.metadata.items():
            ret += indent + k + ' = ' + propertyToString(v, indent) + '\n'
        return ret + space + ')'

    def framesToString(self, space, debug = False):
        indent = space + TAB
        ret = '.timeSamples = {\n'
        if debug and len(self.frames) > 3:
            for frame, value in self.frames[:3]:
                ret += indent + '%d: '%frame + valueToString(value) + ',\n'
            ret += indent + '...\n'
        else:
            for frame, value in self.frames:
                ret += indent + '%d: '%frame + valueToString(value) + ',\n'
        return ret + space + '}'

    def addQualifier(self, qualifier):
        self.qualifiers.append(qualifier)

    def addTimeSample(self, frame, value):
        if self.valueType == ValueType.Invalid:
            self.valueType = getValueType(value)
        self.frames.append((frame, value))

    def valueToString(self, debug = False):
        if self.isConnection():
            return self.value.valueToString(debug)
        if self.valueType == ValueType.token or self.valueType == ValueType.string:
            if type(self.value) is list:
                return '[' + ', '.join('"' + v + '"' for v in self.value) + ']'
            return '"' + valueToString(self.value) + '"'
        if self.valueType == ValueType.asset:
            return '@' + valueToString(self.value) + '@'
        return valueToString(self.value, debug)

    def valueTypeToString(self):
        if self.valueTypeStr != None:
            return self.valueTypeStr + ('[]' if self.isArray() else '')
        return self.valueType.toString() + ('[]' if self.isArray() else '')

    def isArray(self):
        if self.isConnection():
            return self.value.isArray()
        if len(self.frames) > 0:
            return type(self.frames[0][1]) is list
        return self.value != None and type(self.value) is list

    def isConnection(self):
        return type(self.value) is UsdAttribute

    def isRelationship(self):
        return type(self.value) is UsdPrim

    def hasTimeSamples(self):
        return len(self.frames) > 0

    def getPathStr(self):
        if self.isConnection():
            return self.value.getPathStr()
        if self.parent == None:
            return self.name
        return self.parent.getPathStr() + '.' + self.name

    def getPathJump(self):
        self.pathJump = 0
        if self.parent != None and self.parent.attributes[-1] == self:
            self.pathJump = -2
        #print(self.name, ':', self.pathJump)
        return self.pathJump

    def getValueType(self):
        if self.isConnection():
            return self.value.getValueType()
        elif self.isRelationship():
            return ValueType.Invalid
        return getValueType(self.value)


class UsdPrim:
    def __init__(self, name = '', type = ClassType.Scope):
        self.name = name
        self.specifierType = SpecifierType.Def
        self.classType = type
        self.metadata = {}
        self.attributes = []
        self.children = []
        self.parent = None
        self.pathIndex = -1
        self.pathJump = -1

    def __str__(self):
        return self.toString()

    def __setitem__(self, key, item):
        if type(item) is ValueType:
            self.createAttribute(key, type=item)
        else:
            self.createAttribute(key, item)

    def __getitem__(self, key):
        return next((att for att in self.attributes if att.name == key), None)

    def __contains__(self, key):
        return self[key] != None

    def toString(self, space = '', debug = False):
        indent = space + TAB
        line = indent + '\n'
        ret = space + self.specifierType.name.lower() + ' '
        if self.classType != None:
            ret += self.classType.name + ' '
        ret += '"' + self.name + '"'
        if len(self.metadata) > 0:
            ret += self.metadataToString(space)
        else:
            ret += '\n'
        ret += space + '{\n'
        ret += ''.join(att.toString(indent, debug) for att in self.attributes)
        ret += line if len(self.children) > 0 else ''
        ret += line.join(c.toString(indent, debug) for c in self.children)
        return ret + space + '}\n'

    def metadataToString(self, space):
        ret = ' (\n'
        for k, v in self.metadata.items():
            ret += space + TAB + k + ' = ' + propertyToString(v, TAB) + '\n'
        return ret + space + ')\n'

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

    def addChildFront(self, child):
        child.parent = self
        self.children = [child] + self.children
        return child

    def createChild(self, name, type):
        return self.addChild(UsdPrim(name, type))

    def createChildFront(self, name, type):
        return self.addChildFront(UsdPrim(name, type))

    def getAttributesOfTypeStr(self, typeStr):
        return [a for a in self.attributes if a.valueTypeToString() == typeStr]

    def getChild(self, name):
        return next((c for c in self.children if c.name == name), None)

    def getChildOfType(self, type):
        return next((c for c in self.children if c.classType == type), None)

    def getChildrenOfType(self, type):
        children = []
        for child in self.children:
            if child.classType == type:
                children.append(child)
            children += child.getChildrenOfType(type)
        return children

    def getItemAtPathIndex(self, pathIndex):
        for att in self.attributes:
            if att.pathIndex == pathIndex:
                return att
        for child in self.children:
            if child.pathIndex == pathIndex:
                return child
            item = child.getItemAtPathIndex(pathIndex)
            if item != None:
                return item
        return None

    def resolvePaths(self, root):
        if 'references' in self.metadata:
            pathIndex = self.metadata['references']
            self.metadata['references'] = root.getItemAtPathIndex(pathIndex)
        if 'inheritPaths' in self.metadata:
            paths = self.metadata.pop('inheritPaths')
            self.metadata['inherits'] = root.getItemAtPathIndex(paths['path'])
        for att in self.attributes:
            if 'connectionChildren' in att.metadata:
                pathIndex = att.metadata.pop('connectionChildren')
                att.value = root.getItemAtPathIndex(pathIndex)
            if 'connectionPaths' in att.metadata:
                paths = att.metadata.pop('connectionPaths')
                att.value = root.getItemAtPathIndex(paths['path'])
            if 'targetChildren' in att.metadata:
                pathIndex = att.metadata.pop('targetChildren')
                att.value = root.getItemAtPathIndex(pathIndex)
            if 'targetPaths' in att.metadata:
                paths = att.metadata.pop('targetPaths')
                att.value = root.getItemAtPathIndex(paths['path'])
        for child in self.children:
            child.resolvePaths(root)

    def updatePathIndices(self, pathIndex):
        self.pathIndex = pathIndex
        pathIndex += 1
        for child in self.children:
            pathIndex = child.updatePathIndices(pathIndex)
        for att in self.attributes:
            att.pathIndex = pathIndex
            pathIndex += 1
        return pathIndex

    def getPathStr(self):
        if self.parent == None:
            return '/' + self.name
        return self.parent.getPathStr() + '/' + self.name

    def countItems(self):
        #count = len(self.attributes) + len(self.children)
        count = len(self.attributes) + len(self.children)
        for child in self.children:
            count += child.countItems()
        return count

    def getPathJump(self):
        if self.parent == None or (self.parent.children[-1] == self and len(self.parent.attributes) == 0):
            self.pathJump = -1
        else:
            self.pathJump = self.countItems() + 1
        #print(self.name, ':', self.pathJump)
        return self.pathJump


class UsdData:
    def __init__(self):
        self.metadata = {}
        self.children = []
        self.attributes = []
        self.pathIndex = 0
        self.pathJump = -1

    def __str__(self):
        return self.toString()

    def __setitem__(self, key, item):
        self.metadata[key] = item

    def __getitem__(self, key):
        return self.metadata[key]

    def toString(self, debug = False):
        ret = '#usda 1.0\n'
        ret += self.metadataToString()
        ret += '\n'
        return ret + '\n'.join(c.toString('', debug) for c in self.children)

    def getPathStr(self):
        return ''

    def metadataToString(self):
        ret = '(\n'
        for k, v in self.metadata.items():
            ret += TAB + k + ' = ' + propertyToString(v, TAB) + '\n'
        return ret + ')\n'

    def addChild(self, child):
        child.parent = self
        self.children.append(child)
        return child

    def createChild(self, name, type):
        return self.addChild(UsdPrim(name, type))

    def getChildrenOfType(self, type):
        children = []
        for child in self.children:
            if child.classType == type:
                children.append(child)
            children += child.getChildrenOfType(type)
        return children

    def getAllMaterials(self):
        return self.getChildrenOfType(ClassType.Material)

    def updatePathIndices(self):
        pathIndex = 1
        for child in self.children:
            pathIndex = child.updatePathIndices(pathIndex)

    def getPathJump(self):
        self.pathJump = -1 if len(self.children) > 0 else -2
        #print('root:', self.pathJump)
        return self.pathJump

    def getItemAtPathIndex(self, pathIndex):
        for child in self.children:
            if child.pathIndex == pathIndex:
                return child
            item = child.getItemAtPathIndex(pathIndex)
            if item != None:
                return item
        return None

    def resolvePaths(self):
        for child in self.children:
            child.resolvePaths(self)

    def writeUsda(self, filePath):
        f = open(filePath, 'w')
        f.write(str(self))
        f.close()
