import os
import struct
from enum import Enum
from io_scene_usdz.compression_utils import *

ARRAY_BIT = (1 << 63)
INLINE_BIT = (1 << 62)
COMPRESSED_BIT = (1 << 61)
PAYLOAD_MASK = (1 << 48) - 1

def writeInt(file, value, size, byteorder='little', signed=False):
    file.write(value.to_bytes(size, byteorder=byteorder, signed=signed))

def writeFloat(file, value, byteorder='little'):
    packStr = '<f' if byteorder.lower() == 'little' else '>f'
    file.write(struct.pack(packStr, value))

def writeDouble(file, value, byteorder='little'):
    packStr = '<d' if byteorder.lower() == 'little' else '>d'
    file.write(struct.pack(packStr, value))

def writeInt32Compressed(file, data):
    buffer = lz4Compress(usdInt32Compress(data))
    writeInt(file, len(buffer), 8)
    file.write(buffer)

def writeToAlign(file, size):
    bufBytes = file.tell() % size
    if bufBytes > 0:
        file.write(bytes(bufBytes))

def dataKey(data):
    if type(data) == list:
        return tuple(data)
    return data

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
    AssetPath = 12
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
        return ValueType.token
    if t == tuple:
        return getTupleValueType(value)
    if t == list and len(value) > 0:
        if type(value[0]) == str:
            return ValueType.token
        return getValueType(value[0])
    if t == SpecifierType:
        return ValueType.Specifier
    return ValueType.Invalid

def getValueTypeStr(typeStr):
    typeStr = typeStr.replace('[]', '')
    if typeStr == 'float3':
        return ValueType.vec3f
    return ValueType[typeStr]

def writeValue(file, value, vType):
    if type(value) == list:
        writeInt(file, len(value), 4)
        for v in value:
            writeValue(file, v, vType)
    elif vType.name[:6] == 'matrix':
        packStr = '<'+vType.name[-2:]
        for row in value:
            file.write(struct.pack(packStr, *row))
    elif vType.name[:3] == 'vec':
        packStr = '<'+vType.name[-2:]
        file.write(struct.pack(packStr, *value))
    elif vType.name == 'quatf':
        packStr = '<ffff'
        value = (value[1], value[2], value[3], value[0])
        file.write(struct.pack(packStr, *value))


def isWholeHalfs(vector):
    for f in vector:
        if not f.is_integer():
            return False
        i = int(f)
        if i.bit_length() > 16:
            return False
    return True

def isWholeBytes(vector):
    for f in vector:
        if not f.is_integer():
            return False
        i = int(f)
        if i.bit_length() > 8:
            return False
    return True

def compare(lhs, rhs):
    lhType = type(lhs)
    rhType = type(rhs)
    if lhType != rhType:
        return False
    if lhType == list or lhType == tuple:
        if len(lhs) != len(rhs):
            return False
        for i in range(len(lhs)):
            if not compare(lhs[i], rhs[i]):
                return False
            return True
    return lhs == rhs


class CrateFile:
    def __init__(self, file):
        self.file = file
        self.toc = []
        self.tokenMap = {}
        self.tokens = []
        self.strings = []
        self.fields = []
        self.reps = []
        self.repsMap = {}
        self.fsets = []
        self.paths = []
        self.specs = []
        self.writenData = {}
        self.framesRef = -1

    def addWritenData(self, data, vType, ref):
        key = (dataKey(data), vType)
        self.writenData[key] = ref

    def getDataRefrence(self, data, vType):
        key = (dataKey(data), vType)
        if key in self.writenData:
            return self.writenData[key]
        return -1

    def getTokenIndex(self, token):
        if not token in self.tokenMap:
            self.tokenMap[token] = len(self.tokens)
            self.tokens.append(token)
        return self.tokenMap[token]

    def addFieldSet(self, fset):
        index = len(self.fsets)
        self.fsets += fset
        self.fsets.append(-1)
        return index

    def addFieldItem(self, field, vType, array, inline, compressed, payload = 0):
        repIndex = len(self.reps)
        rep = (vType.value << 48) | (payload & PAYLOAD_MASK)
        if array:
            rep |= ARRAY_BIT
        if compressed:
            rep |= COMPRESSED_BIT
        if inline:
            rep |= INLINE_BIT
        key = (field, rep)
        if key in self.repsMap:
            return self.repsMap[key]
        self.repsMap[key] = repIndex
        self.fields.append(field)
        self.reps.append(rep)
        return repIndex

    def addFieldToken(self, field, data):
        field = self.getTokenIndex(field)
        if type(data) == list:
            tokens = []
            for token in data:
                tokens.append(self.getTokenIndex(token.replace('"', '')))
            ref = self.getDataRefrence(tokens, ValueType.token)
            if ref < 0:
                ref = self.file.tell()
                self.addWritenData(tokens, ValueType.token, ref)
                writeInt(self.file, len(tokens), 4)
                for token in tokens:
                    writeInt(self.file, token, 4)
            return self.addFieldItem(field, ValueType.token, True, False, False, ref)
        token = self.getTokenIndex(data.replace('"', ''))
        return self.addFieldItem(field, ValueType.token, False, True, False, token)

    def addFieldTokenVector(self, field, tokens):
        field = self.getTokenIndex(field)
        data = []
        for token in tokens:
            token = token.replace('"', '')
            data.append(self.getTokenIndex(token))
        ref = self.getDataRefrence(data, ValueType.TokenVector)
        if ref < 0:
            ref = self.file.tell()
            self.addWritenData(data, ValueType.TokenVector, ref)
            writeInt(self.file, len(data), 8)
            for token in data:
                writeInt(self.file, token, 4)
            self.file.write(bytes(4))
        return self.addFieldItem(field, ValueType.TokenVector, False, False, False, ref)

    def addFieldPathListOp(self, field, pathIndex):
        field = self.getTokenIndex(field)
        ref = self.file.tell()
        op = 259
        writeInt(self.file, op, 8)
        self.file.write(bytes(1))
        writeInt(self.file, pathIndex, 4)
        return self.addFieldItem(field, ValueType.PathListOp, False, False, False, ref)

    def addFieldPathVector(self, field, pathIndex):
        field = self.getTokenIndex(field)
        ref = self.file.tell()
        writeInt(self.file, 1, 8)
        writeInt(self.file, pathIndex, 4)
        return self.addFieldItem(field, ValueType.PathVector, False, False, False, ref)

    def addFieldSpecifier(self, field, spec):
        field = self.getTokenIndex(field)
        return self.addFieldItem(field, ValueType.Specifier, False, True, False, spec.value)

    def addFieldInt(self, field, data):
        field = self.getTokenIndex(field)
        if type(data) == list:
            compress = len(data) > 16
            ref = self.getDataRefrence(data, ValueType.int)
            if ref < 0:
                ref = self.file.tell()
                self.addWritenData(data, ValueType.int, ref)
                writeInt(self.file, len(data), 4)
                if compress:
                    writeInt32Compressed(self.file, data)
                else:
                    for i in data:
                        writeInt(self.file, i, 4, signed=True)
            return self.addFieldItem(field, ValueType.int, True, False, compress, ref)
        return self.addFieldItem(field, ValueType.int, False, True, False, data)

    def addFieldFloat(self, field, data):
        field = self.getTokenIndex(field)
        if type(data) == list:
            ref = self.getDataRefrence(data, ValueType.float)
            if ref < 0:
                ref = self.file.tell()
                self.addWritenData(data, ValueType.float, ref)
                writeInt(self.file, len(data), 4)
                for f in data:
                    writeFloat(self.file, f)
            return self.addFieldItem(field, ValueType.float, True, False, False, ref)
        data = int.from_bytes(struct.pack('<f', data), 'little')
        return self.addFieldItem(field, ValueType.float, False, True, False, data)

    def addFieldDouble(self, field, data):
        field = self.getTokenIndex(field)
        if type(data) == list:
            ref = self.getDataRefrence(data, ValueType.double)
            if ref < 0:
                ref = self.file.tell()
                self.addWritenData(data, ValueType.double, ref)
                writeInt(self.file, len(data), 4)
                for d in data:
                    writeDouble(self.file, d)
            return self.addFieldItem(field, ValueType.double, True, False, False, ref)
        data = int.from_bytes(struct.pack('<f', data), 'little')
        return self.addFieldItem(field, ValueType.double, False, True, False, data)

    def addFieldVector(self, field, data, vType):
        field = self.getTokenIndex(field)
        packStr = '<'+vType.name[-2:]
        if type(data) == list:
            ref = self.getDataRefrence(data, vType)
            if ref < 0:
                ref = self.file.tell()
                self.addWritenData(data, vType, ref)
                writeInt(self.file, len(data), 4)
                for v in data:
                    self.file.write(struct.pack(packStr, *v))
            return self.addFieldItem(field, vType, True, False, False, ref)
        if isWholeBytes(data):
            nBytes = 2 * len(data)
            data = [int(f) for f in data]
            packStr = packStr.replace('f', 'b')
            data = struct.pack(packStr, *data)
            data = int.from_bytes(data, 'little')
            return self.addFieldItem(field, vType, False, True, False, data)
        else:
            ref = self.getDataRefrence(data, vType)
            if ref < 0:
                ref = self.file.tell()
                self.addWritenData(data, vType, ref)
                self.file.write(struct.pack(packStr, *data))
            return self.addFieldItem(field, vType, False, False, False, ref)

    def addFieldMatrix(self, field, data, vType):
        field = self.getTokenIndex(field)
        ref = self.getDataRefrence(data, vType)
        if ref < 0:
            ref = self.file.tell()
            self.addWritenData(data, vType, ref)
            packStr = '<'+vType.name[-2:]
            if type(data) == list:
                writeInt(self.file, len(data), 4)
                for matrix in data:
                    for row in matrix:
                        self.file.write(struct.pack(packStr, *row))
            else:
                for row in data:
                    self.file.write(struct.pack(packStr, *row))
        if type(data) == list:
            return self.addFieldItem(field, vType, True, False, False, ref)
        return self.addFieldItem(field, vType, False, False, False, ref)

    def addFieldBool(self, field, data):
        field = self.getTokenIndex(field)
        data = 1 if data else 0
        return self.addFieldItem(field, ValueType.bool, False, True, False, data)

    def addFieldVariability(self, field, data):
        field = self.getTokenIndex(field)
        data = 1 if data else 0
        return self.addFieldItem(field, ValueType.Variability, False, True, False, data)

    def addFieldTimeSamples(self, field, data, vType):
        field = self.getTokenIndex(field)
        vType = getValueTypeStr(vType)
        count = len(data)
        size = 8*(count+2)
        elem = 0
        if type(data[0][1]) == list and len(data[0][1]) > 1:
            elem = 128
        frames = []
        refs = []
        refMap = {}
        for frame, value in data:
            frames.append(float(frame))
            key = dataKey(value)
            if key in refMap:
                refs.append(refMap[key])
            else:
                ref = self.file.tell()
                writeValue(self.file, value, vType)
                refMap[key] = ref
                refs.append(ref)
        reference = self.file.tell()
        if self.framesRef > 0:
            writeInt(self.file, 8, 8)
            writeInt(self.file, self.framesRef + 8, 6)
            writeInt(self.file, ValueType.DoubleVector.value, 1)
            writeInt(self.file, 0, 1)
        else:
            self.framesRef = reference
            writeInt(self.file, size, 8)
            writeInt(self.file, count, 8)
            for frame in frames:
                writeDouble(self.file, frame)
            writeInt(self.file, reference + 8, 6)
            writeInt(self.file, ValueType.DoubleVector.value, 1)
            writeInt(self.file, 0, 1)
        writeInt(self.file, 8, 8)
        writeInt(self.file, count, 8)
        for ref in refs:
            print((ref, vType.value, elem))
            writeInt(self.file, ref, 6)
            writeInt(self.file, vType.value, 1)
            writeInt(self.file, elem, 1)
        return self.addFieldItem(field, ValueType.TimeSamples, False, False, False, reference)

    def addField(self, field, value, type = ValueType.UnregisteredValue):
        if type == ValueType.UnregisteredValue:
            type = getValueType(value)
        if type == ValueType.token:
            return self.addFieldToken(field, value)
        if type == ValueType.TokenVector:
            return self.addFieldTokenVector(field, value)
        if type == ValueType.Specifier:
            return self.addFieldSpecifier(field, value)
        if type == ValueType.int:
            return self.addFieldInt(field, value)
        if type == ValueType.float:
            return self.addFieldFloat(field, value)
        if type.name[:3] == 'vec':
            return self.addFieldVector(field, value, type)
        if type.name[:6] == 'matrix':
            return self.addFieldMatrix(field, value, type)
        if type == ValueType.bool:
            return self.addFieldBool(field, value)
        if type == ValueType.Variability:
            return self.addFieldVariability(field, value)
        print('type: ', type.name, value)
        return self.addFieldItem(field, type, False, True, False, value)

    def addPath(self, path, token, jump, prim):
        if prim:
            token *= -1
        self.paths.append((path, token, jump))

    def addSpec(self, fset, sType):
        path = len(self.specs)
        self.specs.append((path, fset, sType.value))
        return path

    def writeBootStrap(self, tocOffset = 0):
        self.file.seek(0)
        self.file.write(b'PXR-USDC')
        # Version
        self.file.write(b'\x00\x06\x00\x00\x00\x00\x00\x00')
        # Table of Contents Offset
        #print('tocOffset: ', tocOffset)
        writeInt(self.file, tocOffset, 8)
        self.file.write(bytes(64))

    def writeTokensSection(self):
        start = self.file.tell()
        writeInt(self.file, len(self.tokens), 8)
        buffer = bytearray()
        for token in self.tokens:
            buffer += token.encode() + b'\0'
        writeInt(self.file, len(buffer), 8)
        buffer = lz4Compress(buffer)
        writeInt(self.file, len(buffer), 8)
        self.file.write(buffer)
        size = self.file.tell() - start
        self.toc.append((b'TOKENS', start, size))

    def writeStringsSection(self):
        start = self.file.tell()
        self.file.write(bytes(8))
        # This section is empty for now
        size = self.file.tell() - start
        self.toc.append((b'STRINGS', start, size))

    def writeFieldsSection(self):
        start = self.file.tell()
        writeInt(self.file, len(self.fields), 8)
        writeInt32Compressed(self.file, self.fields)
        buffer = lz4Compress(encodeInts(self.reps, 8))
        writeInt(self.file, len(buffer), 8)
        self.file.write(buffer)
        size = self.file.tell() - start
        self.toc.append((b'FIELDS', start, size))

    def writeFieldSetsSection(self):
        start = self.file.tell()
        writeInt(self.file, len(self.fsets), 8)
        writeInt32Compressed(self.file, self.fsets)
        size = self.file.tell() - start
        self.toc.append((b'FIELDSETS', start, size))

    def writePathsSection(self):
        start = self.file.tell()
        paths = []
        tokens = []
        jumps = []
        for path, token, jump in self.paths:
            paths.append(path)
            tokens.append(token)
            jumps.append(jump)
        writeInt(self.file, len(self.paths), 8)
        writeInt(self.file, len(self.paths), 8)
        writeInt32Compressed(self.file, paths)
        writeInt32Compressed(self.file, tokens)
        writeInt32Compressed(self.file, jumps)
        size = self.file.tell() - start
        self.toc.append((b'PATHS', start, size))

    def writeSpecsSection(self):
        start = self.file.tell()
        paths = []
        fsets = []
        types = []
        for path, fset, type in self.specs:
            paths.append(path)
            fsets.append(fset)
            types.append(type)
        writeInt(self.file, len(self.specs), 8)
        writeInt32Compressed(self.file, paths)
        writeInt32Compressed(self.file, fsets)
        writeInt32Compressed(self.file, types)
        size = self.file.tell() - start
        self.toc.append((b'SPECS', start, size))

    def writeSections(self):
        self.writeTokensSection()
        self.writeStringsSection()
        self.writeFieldsSection()
        self.writeFieldSetsSection()
        self.writePathsSection()
        self.writeSpecsSection()

    def writeTableOfContents(self):
        tocStart = self.file.tell()
        print('tocStart: ', tocStart)
        writeInt(self.file, len(self.toc), 8)
        for name, start, size in self.toc:
            self.file.write(name)
            self.file.write(bytes(16-len(name)))
            writeInt(self.file, start, 8)
            writeInt(self.file, size, 8)
        self.writeBootStrap(tocStart)
