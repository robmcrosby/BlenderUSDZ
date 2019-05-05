import os
import struct
from enum import Enum
from io_scene_usdz.compression_utils import *

ARRAY_BIT = (1 << 63)
INLINE_BIT = (1 << 62)
COMPRESSED_BIT = (1 << 61)
PAYLOAD_MASK = (1 << 48) - 1

def writeInt32Compressed(file, data):
    buffer = lz4Compress(usdInt32Compress(data))
    file.write(len(buffer).to_bytes(8, byteorder='little'))
    file.write(buffer)

def writeToAlign(file, size):
    bufBytes = file.tell() % size
    if bufBytes > 0:
        file.write(bytes(bufBytes))

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
            return ValueType.TokenVector
        return getValueType(value[0])
    if t == SpecifierType:
        return ValueType.Specifier
    return ValueType.Invalid



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

    def addFieldToken(self, field, token):
        field = self.getTokenIndex(field)
        token = self.getTokenIndex(token.replace('"', ''))
        return self.addFieldItem(field, ValueType.token, False, True, False, token)

    def addFieldTokenVector(self, field, tokens):
        field = self.getTokenIndex(field)
        ref = self.file.tell()
        self.file.write(len(tokens).to_bytes(8, byteorder='little'))
        for token in tokens:
            token = token.replace('"', '')
            self.file.write(self.getTokenIndex(token).to_bytes(4, byteorder='little'))
        self.file.write(bytes(4))
        return self.addFieldItem(field, ValueType.TokenVector, False, False, False, ref)

    def addFieldSpecifier(self, field, spec):
        field = self.getTokenIndex(field)
        return self.addFieldItem(field, ValueType.Specifier, False, True, False, spec.value)

    def addFieldInt(self, field, data):
        field = self.getTokenIndex(field)
        if type(data) == list:
            ref = self.file.tell()
            self.file.write(len(data).to_bytes(4, byteorder='little'))
            if len(data) > 16:
                # Compress the data
                writeInt32Compressed(self.file, data)
                #buffer = lz4Compress(encodeInts(data, 4, signed=True))
                #self.file.write(len(buffer).to_bytes(8, byteorder='little'))
                #self.file.write(buffer)
                #writeToAlign(self.file)
                return self.addFieldItem(field, ValueType.int, True, False, True, ref)
            for i in data:
                self.file.write(i.to_bytes(4, byteorder='little', signed=True))
            #writeToAlign(self.file)
            return self.addFieldItem(field, ValueType.int, True, False, False, ref)
        return self.addFieldItem(field, ValueType.int, False, True, False, data)

    def addFieldFloat(self, field, data):
        field = self.getTokenIndex(field)
        if type(data) == list:
            ref = self.file.tell()
            self.file.write(len(data).to_bytes(4, byteorder='little'))
            for f in data:
                self.file.write(struct.pack('<f', f))
            #writeToAlign(self.file)
            return self.addFieldItem(field, ValueType.float, True, False, False, ref)
        data = int.from_bytes(struct.pack('<f', data), 'little')
        return self.addFieldItem(field, ValueType.float, False, True, False, data)

    def addFieldVector(self, field, data, vType):
        field = self.getTokenIndex(field)
        ref = self.file.tell()
        packStr = '<'+vType.name[-2:]
        if type(data) == list:
            self.file.write(len(data).to_bytes(4, byteorder='little'))
            for v in data:
                self.file.write(struct.pack(packStr, *v))
            #writeToAlign(self.file)
            return self.addFieldItem(field, vType, True, False, False, ref)
        self.file.write(struct.pack(packStr, *data))
        #writeToAlign(self.file)
        return self.addFieldItem(field, vType, False, False, False, ref)

    def addFieldMatrix(self, field, data, vType):
        field = self.getTokenIndex(field)
        ref = self.file.tell()
        packStr = '<'+vType.name[-2:]
        if type(data) == list:
            self.file.write(len(data).to_bytes(4, byteorder='little'))
            for matrix in data:
                for row in matrix:
                    self.file.write(struct.pack(packStr, *row))
            #writeToAlign(self.file)
            return self.addFieldItem(field, vType, True, False, False, ref)
        for row in data:
            self.file.write(struct.pack(packStr, *row))
        #writeToAlign(self.file)
        return self.addFieldItem(field, vType, False, False, False, ref)

    def addFieldBool(self, field, data):
        field = self.getTokenIndex(field)
        data = 1 if data else 0
        return self.addFieldItem(field, ValueType.bool, False, True, False, data)

    def addFieldVariability(self, field, data):
        field = self.getTokenIndex(field)
        data = 1 if data else 0
        return self.addFieldItem(field, ValueType.Variability, False, True, False, data)

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

    def addPath(self, token, jump, prim):
        path = len(self.paths)
        token = self.getTokenIndex(token)
        if prim:
            token *= -1
        self.paths.append((path, token, jump))
        return path

    def addSpec(self, path, fset, sType):
        self.specs.append((path, fset, sType.value))

    def writeBootStrap(self, tocOffset = 0):
        self.file.seek(0)
        self.file.write(b'PXR-USDC')
        # Version
        self.file.write(b'\x00\x06\x00\x00\x00\x00\x00\x00')
        # Table of Contents Offset
        print('tocOffset: ', tocOffset)
        self.file.write(tocOffset.to_bytes(8, byteorder='little'))
        self.file.write(bytes(64))

    def writeTokensSection(self):
        start = self.file.tell()
        self.file.write(len(self.tokens).to_bytes(8, byteorder='little'))
        buffer = bytearray()
        for token in self.tokens:
            buffer += token.encode() + b'\0'
        self.file.write(len(buffer).to_bytes(8, byteorder='little'))
        buffer = lz4Compress(buffer)
        self.file.write(len(buffer).to_bytes(8, byteorder='little'))
        self.file.write(buffer)
        size = self.file.tell() - start
        self.toc.append((b'TOKENS', start, size))

    def writeStringsSection(self):
        start = self.file.tell()
        self.file.write(bytes(8))
        #self.file.write(len(self.strings).to_bytes(8, 'little'))
        #writeInt32Compressed(self.file, self.strings)
        size = self.file.tell() - start
        self.toc.append((b'STRINGS', start, size))

    def writeFieldsSection(self):
        start = self.file.tell()
        self.file.write(len(self.fields).to_bytes(8, byteorder='little'))
        writeInt32Compressed(self.file, self.fields)
        buffer = lz4Compress(encodeInts(self.reps, 8))
        self.file.write(len(buffer).to_bytes(8, byteorder='little'))
        self.file.write(buffer)
        size = self.file.tell() - start
        self.toc.append((b'FIELDS', start, size))

    def writeFieldSetsSection(self):
        start = self.file.tell()
        self.file.write(len(self.fsets).to_bytes(8, byteorder='little'))
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
        self.file.write(len(self.paths).to_bytes(8, byteorder='little'))
        self.file.write(len(self.paths).to_bytes(8, byteorder='little'))
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
        self.file.write(len(self.specs).to_bytes(8, byteorder='little'))
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
        self.file.write(len(self.toc).to_bytes(8, byteorder='little'))
        for name, start, size in self.toc:
            self.file.write(name)
            self.file.write(bytes(16-len(name)))
            self.file.write(start.to_bytes(8, byteorder='little'))
            self.file.write(size.to_bytes(8, byteorder='little'))
        self.writeBootStrap(tocStart)
