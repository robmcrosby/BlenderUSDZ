import os
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
    Bool = 1
    UChar = 2
    Int = 3
    UInt = 4
    Int64 = 5
    UInt64 = 6
    Half = 7
    Float = 8
    Double = 9
    String = 10
    Token = 11
    AssetPath = 12
    Matrix2d = 13
    Matrix3d = 14
    Matrix4d = 15
    Quatd = 16
    Quatf = 17
    Quath = 18
    Vec2d = 19
    Vec2f = 20
    Vec2h = 21
    Vec2i = 22
    Vec3d = 23
    Vec3f = 24
    Vec3h = 25
    Vec3i = 26
    Vec4d = 27
    Vec4f = 28
    Vec4h = 29
    Vec4i = 30
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


class CrateFile:
    def __init__(self, file):
        self.file = file
        self.toc = []
        self.tokenMap = {}
        self.tokens = []
        self.strings = []
        self.fields = []
        self.reps = []
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

    def addField(self, field, vType, array, inline, compressed, payload = 0):
        repIndex = len(self.reps)
        self.fields.append(field)
        rep = (vType.value << 48) | (payload & PAYLOAD_MASK)
        if array:
            rep |= ARRAY_BIT
        if inline:
            rep |= INLINE_BIT
        if compressed:
            rep |= COMPRESSED_BIT
        self.reps.append(rep)
        return repIndex

    def addPath(self, token, jump):
        path = len(self.paths)
        token = self.getTokenIndex(token)
        self.paths.append((path, token, jump))
        return path

    def addSpec(self, path, fset, sType):
        self.specs.append((path, fset, sType.value))

    def addTokenField(self, field, token):
        field = self.getTokenIndex(field)
        token = self.getTokenIndex(token)
        return self.addField(field, ValueType.Token, False, True, False, token)

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
