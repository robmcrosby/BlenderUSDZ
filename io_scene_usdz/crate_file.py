import os
import struct
from io_scene_usdz.compression_utils import *
from io_scene_usdz.value_types import *

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

def toSigned32(n):
    n = n & 0xffffffff
    return (n ^ 0x80000000) - 0x80000000

def writeInt32Compressed(file, data):
    buffer = lz4Compress(usdInt32Compress(data))
    writeInt(file, len(buffer), 8)
    file.write(buffer)

def writeToAlign(file, size):
    bufBytes = file.tell() % size
    if bufBytes > 0:
        file.write(bytes(bufBytes))

def readInt(file, size, byteorder='little', signed=False):
    buffer = file.read(size)
    return int.from_bytes(buffer, byteorder=byteorder, signed=signed)

def readInt32Compressed(file, numInts):
    size = readInt(file, 8)
    buffer = lz4Decompress(file.read(size))
    return usdInt32Decompress(buffer, numInts)

def dataKey(data):
    if type(data) == list:
        return tuple(data)
    return data


def writeValue(file, value, vType):
    if type(value) == list:
        writeInt(file, len(value), 8)
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

def decodeRep(data):
    rep = {}
    rep['type'] = ValueType((data >> 48) & 0xFF)
    rep['array'] = (data & ARRAY_BIT) != 0
    rep['inline'] = (data & INLINE_BIT) != 0
    rep['compressed'] = (data & COMPRESSED_BIT) != 0
    rep['payload'] = data & PAYLOAD_MASK
    rep['value'] = None
    return rep

def makeIdentityMatrix(size):
    return tuple((0,)*i + (1,) + (0,)*(size-i-1) for i in range(size))


class CrateFile:
    def __init__(self, file):
        self.file = file
        self.version = 6
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
        self.specsMap = {}
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

    def getStringIndex(self, str):
        tokenIndex = self.getTokenIndex(str)
        if not tokenIndex in self.strings:
            self.strings.append(tokenIndex)
        return self.strings.index(tokenIndex)

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
                token = token.replace('"', '')
                tokens.append(self.getTokenIndex(token))
            ref = self.getDataRefrence(tokens, ValueType.token)
            if ref < 0:
                ref = self.file.tell()
                self.addWritenData(tokens, ValueType.token, ref)
                writeInt(self.file, len(tokens), 8)
                for token in tokens:
                    writeInt(self.file, token, 4)
            return self.addFieldItem(field, ValueType.token, True, False, False, ref)
        token = self.getTokenIndex(data.replace('"', ''))
        return self.addFieldItem(field, ValueType.token, False, True, False, token)

    def addFieldAsset(self, field, data):
        field = self.getTokenIndex(field)
        token = self.getTokenIndex(data.replace('@', ''))
        return self.addFieldItem(field, ValueType.asset, False, True, False, token)

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

    def addReferenceListOp(self, field, item):
        field = self.getTokenIndex(field)
        strIndex = self.getStringIndex('')
        pathIndex = item.pathIndex
        ref = self.file.tell()
        writeInt(self.file, 3, 1) # ListOp Type Flags (Explicit | Explicit Items)
        writeInt(self.file, 1, 8) # Vector Size (size of 1)
        writeInt(self.file, strIndex, 4) # Index to empty string for now
        writeInt(self.file, pathIndex, 8) # Path Index
        writeInt(self.file, 0, 10) # Write rest of SdfRefrence
        self.file.write(b'\xf0\x3f')
        writeInt(self.file, 0, 8)
        return self.addFieldItem(field, ValueType.ReferenceListOp, False, False, False, ref)

    def addFieldSpecifier(self, field, spec):
        field = self.getTokenIndex(field)
        return self.addFieldItem(field, ValueType.Specifier, False, True, False, spec.value)

    def addFieldInt(self, field, data):
        field = self.getTokenIndex(field)
        if type(data) == list:
            compress = len(data) >= 16
            ref = self.getDataRefrence(data, ValueType.int)
            if ref < 0:
                ref = self.file.tell()
                self.addWritenData(data, ValueType.int, ref)
                writeInt(self.file, len(data), 8)
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
                writeInt(self.file, len(data), 8)
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
                writeInt(self.file, len(data), 8)
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
                writeInt(self.file, len(data), 8)
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
                writeInt(self.file, len(data), 8)
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

    def addFieldDictionary(self, field, data):
        field = self.getTokenIndex(field)
        ref = self.file.tell()
        writeInt(self.file, len(data), 8)
        for key, value in data.items():
            writeInt(self.file, self.getStringIndex(key), 4)
            writeInt(self.file, 8, 8)
            writeInt(self.file, self.getStringIndex(value), 4)
            writeInt(self.file, 1074397184, 4)
        return self.addFieldItem(field, ValueType.Dictionary, False, False, False, ref)

    def addFieldTimeSamples(self, field, data, vType):
        field = self.getTokenIndex(field)
        vType = getValueTypeFromStr(vType)
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
            #print((ref, vType.value, elem))
            writeInt(self.file, ref, 6)
            writeInt(self.file, vType.value, 1)
            writeInt(self.file, elem, 1)
        return self.addFieldItem(field, ValueType.TimeSamples, False, False, False, reference)

    def addField(self, field, value, vType = ValueType.UnregisteredValue):
        if vType == ValueType.UnregisteredValue:
            vType = getValueType(value)
        if vType == ValueType.token:
            return self.addFieldToken(field, value)
        if vType == ValueType.asset:
            return self.addFieldAsset(field, value)
        if vType == ValueType.TokenVector:
            return self.addFieldTokenVector(field, value)
        if vType == ValueType.Specifier:
            return self.addFieldSpecifier(field, value)
        if vType == ValueType.int:
            return self.addFieldInt(field, value)
        if vType == ValueType.float:
            return self.addFieldFloat(field, value)
        if vType.name[:3] == 'vec':
            return self.addFieldVector(field, value, vType)
        if vType.name[:6] == 'matrix':
            return self.addFieldMatrix(field, value, vType)
        if vType == ValueType.bool:
            return self.addFieldBool(field, value)
        if vType == ValueType.Variability:
            return self.addFieldVariability(field, value)
        if vType == ValueType.Dictionary:
            return self.addFieldDictionary(field, value)
        #print('type: ', vType.name, value)
        return self.addFieldItem(field, vType, False, True, False, value)

    def addPath(self, path, token, jump, prim):
        if prim:
            token *= -1
        self.paths.append((path, token, jump))

    def addSpec(self, fset, sType):
        path = len(self.specs)
        self.specs.append((path, fset, sType.value))
        self.specsMap[path] = (fset, sType.value)
        return path

    def writeBootStrap(self, tocOffset = 0):
        self.file.seek(0)
        self.file.write(b'PXR-USDC')
        # Version
        self.file.write(b'\x00\x07\x00\x00\x00\x00\x00\x00')
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
        self.toc.append(('TOKENS', start, size))

    def writeStringsSection(self):
        start = self.file.tell()
        writeInt(self.file, len(self.strings), 8)
        for i in self.strings:
            writeInt(self.file, i, 4)
        size = self.file.tell() - start
        self.toc.append(('STRINGS', start, size))

    def writeFieldsSection(self):
        start = self.file.tell()
        writeInt(self.file, len(self.fields), 8)
        writeInt32Compressed(self.file, self.fields)
        buffer = lz4Compress(encodeInts(self.reps, 8))
        writeInt(self.file, len(buffer), 8)
        self.file.write(buffer)
        size = self.file.tell() - start
        self.toc.append(('FIELDS', start, size))

    def writeFieldSetsSection(self):
        start = self.file.tell()
        writeInt(self.file, len(self.fsets), 8)
        writeInt32Compressed(self.file, self.fsets)
        size = self.file.tell() - start
        self.toc.append(('FIELDSETS', start, size))

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
        self.toc.append(('PATHS', start, size))

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
        self.toc.append(('SPECS', start, size))

    def writeSections(self):
        self.writeTokensSection()
        self.writeStringsSection()
        self.writeFieldsSection()
        self.writeFieldSetsSection()
        self.writePathsSection()
        self.writeSpecsSection()

    def writeTableOfContents(self):
        tocStart = self.file.tell()
        #print('tocStart: ', tocStart)
        writeInt(self.file, len(self.toc), 8)
        for name, start, size in self.toc:
            self.file.write(name.encode('utf-8'))
            self.file.write(bytes(16-len(name)))
            writeInt(self.file, start, 8)
            writeInt(self.file, size, 8)
        self.writeBootStrap(tocStart)

    def writeUsdConnection(self, usdAtt):
        fset = []
        pathIndex = usdAtt.value.pathIndex
        fset.append(self.addField('typeName', usdAtt.value.valueTypeToString()))
        for q in usdAtt.value.qualifiers:
            if q == 'uniform':
                fset.append(self.addField('variability', True, ValueType.Variability))
            elif q == 'custom':
                fset.append(self.addField('custom', True))
        fset.append(self.addFieldPathListOp('connectionPaths', pathIndex))
        fset.append(self.addFieldPathVector('connectionChildren', pathIndex))
        fset = self.addFieldSet(fset)
        usdAtt.pathIndex = self.addSpec(fset, SpecType.Attribute)
        nameToken = self.getTokenIndex(usdAtt.name)
        pathJump = usdAtt.getPathJump()
        self.addPath(usdAtt.pathIndex, nameToken, pathJump, True)

    def writeUsdRelationship(self, usdAtt):
        fset = []
        pathIndex = usdAtt.value.pathIndex
        fset.append(self.addField('variability', True, ValueType.Variability))
        fset.append(self.addFieldPathListOp('targetPaths', pathIndex))
        fset.append(self.addFieldPathVector('targetChildren', pathIndex))
        fset = self.addFieldSet(fset)
        usdAtt.pathIndex = self.addSpec(fset, SpecType.Relationship)
        nameToken = self.getTokenIndex(usdAtt.name)
        pathJump = usdAtt.getPathJump()
        self.addPath(usdAtt.pathIndex, nameToken, pathJump, True)

    def writeUsdAttribute(self, usdAtt):
        fset = []
        fset.append(self.addField('typeName', usdAtt.valueTypeToString()))
        for q in usdAtt.qualifiers:
            if q == 'uniform':
                fset.append(self.addField('variability', True, ValueType.Variability))
            elif q == 'custom':
                fset.append(self.addField('custom', True))
        for name, value in usdAtt.metadata.items():
            fset.append(self.addField(name, value))
        if usdAtt.value != None:
            fset.append(self.addField('default', usdAtt.value, usdAtt.valueType))
        if usdAtt.hasTimeSamples():
            fset.append(self.addFieldTimeSamples('timeSamples', usdAtt.frames, usdAtt.valueType.name))
        fset = self.addFieldSet(fset)
        usdAtt.pathIndex = self.addSpec(fset, SpecType.Attribute)
        nameToken = self.getTokenIndex(usdAtt.name)
        pathJump = usdAtt.getPathJump()
        self.addPath(usdAtt.pathIndex, nameToken, pathJump, True)

    def writeUsdPrim(self, usdPrim):
        # Add Prim Properties
        fset = []
        fset.append(self.addField('specifier', usdPrim.specifierType))
        if usdPrim.classType != None:
            fset.append(self.addField('typeName', usdPrim.classType.name))
        for name, value in usdPrim.metadata.items():
            if name == 'inherits':
                path = value.pathIndex
                fset.append(self.addFieldPathListOp('inheritPaths', path))
            elif name == 'references':
                fset.append(sself.addReferenceListOp(field, value))
            else:
                fset.append(self.addField(name, value))
        if len(usdPrim.attributes) > 0:
            tokens = [att.name for att in usdPrim.attributes]
            fset.append(self.addFieldTokenVector('properties', tokens))
        if len(usdPrim.children) > 0:
            tokens = [child.name for child in usdPrim.children]
            fset.append(self.addFieldTokenVector('primChildren', tokens))
        fset = self.addFieldSet(fset)
        usdPrim.pathIndex = self.addSpec(fset, SpecType.Prim)
        nameToken = self.getTokenIndex(usdPrim.name)
        pathJump = usdPrim.getPathJump()
        # Add Prim Path
        self.addPath(usdPrim.pathIndex, nameToken, pathJump, False)
        # Write Prim Children
        for child in usdPrim.children:
            self.writeUsdPrim(child)
        # Write Prim Attributes
        for attribute in usdPrim.attributes:
            if attribute.isConnection():
                self.writeUsdConnection(attribute)
            elif attribute.isRelationship():
                self.writeUsdRelationship(attribute)
            else:
                self.writeUsdAttribute(attribute)

    def writeUsd(self, usdData):
        usdData.updatePathIndices()
        self.writeBootStrap()
        # Add Root Metadata
        fset = []
        for name, value in usdData.metadata.items():
            if type(value) is float:
                fset.append(self.addFieldDouble(name, value))
            else:
                fset.append(self.addField(name, value))
        if len(usdData.children) > 0:
            tokens = [c.name for c in usdData.children]
            fset.append(self.addFieldTokenVector('primChildren', tokens))
        fset = self.addFieldSet(fset)
        usdData.pathIndex = self.addSpec(fset, SpecType.PseudoRoot)
        # Add First Path
        nameToken = self.getTokenIndex('')
        pathJump = usdData.getPathJump()
        self.addPath(usdData.pathIndex, nameToken, pathJump, False)
        # Write the Children
        for child in usdData.children:
            self.writeUsdPrim(child)
        # Finish Writing the Crate File
        self.writeSections()
        self.writeTableOfContents()

    def getFieldSetMetadata(self, fset):
        metadata = {}
        fset = self.getFieldSet(fset)
        for field in fset:
            if field < len(self.reps):
                name = self.getTokenStr(self.fields[field])
                value = self.getRepValue(self.reps[field])
                metadata[name] = value
        return metadata


    def readUsdItem(self, parent = None, index = 0):
        path, token, jump = self.paths[index]
        if not path in self.specsMap:
            return (index + 1, -1)
        fset, spec = self.specsMap[path]
        specType = SpecType(spec)
        metadata = self.getFieldSetMetadata(fset)
        name = self.getTokenStr(token)
        if specType == SpecType.Prim:
            classType = None
            if 'typeName' in metadata:
                classType = ClassType[metadata.pop('typeName')]
            prim = parent.createChild(name, classType)
            if 'specifier' in metadata:
                specifier = metadata.pop('specifier')['payload']
                if specifier == 0:
                    prim.specifierType = SpecifierType.Def
                elif specifier == 1:
                    prim.specifierType = SpecifierType.Over
                else:
                    prim.specifierType = SpecifierType.Class
            if 'properties' in metadata:
                metadata.pop('properties')
            if 'primChildren' in metadata:
                metadata.pop('primChildren')
            prim.metadata = metadata
            prim.pathIndex = path
            index += 1
            itemJump = jump
            while index < len(self.paths) and itemJump != -2:
                index, itemJump = self.readUsdItem(prim, index)
            jump = -2 if jump == -1 else -1
            return (index, jump)
        elif specType == SpecType.Attribute:
            valueTypeStr = metadata.pop('typeName').replace('[]', '')
            valueType = getValueTypeFromStr(valueTypeStr)
            value = metadata.pop('default') if 'default' in metadata else None
            if valueType == ValueType.asset and type(value) == str:
                value = value.replace('@', '')
            att = parent.createAttribute(name, value, valueType)
            att.pathIndex = path
            if att.valueType.name != valueTypeStr:
                att.valueTypeStr = valueTypeStr
            if 'variability' in metadata and metadata.pop('variability') == 1:
                att.addQualifier('uniform')
            if 'custom' in metadata and metadata.pop('custom') == 1:
                att.addQualifier('custom')
            if 'timeSamples' in metadata:
                att.frames = metadata.pop('timeSamples')
            att.metadata = metadata
        elif specType == SpecType.Relationship:
            rel = parent.createAttribute(name)
            rel.pathIndex = path
            rel.valueTypeStr = 'rel'
            if 'variability' in metadata and metadata.pop('variability') == 1:
                rel.addQualifier('uniform')
            if 'custom' in metadata and metadata.pop('custom') == 1:
                rel.addQualifier('custom')
            rel.metadata = metadata
        return (index + 1, jump)

    def readUsd(self):
        self.readTableOfContents()
        path, token, jump = self.paths[0]
        fset, spec = self.specsMap[path]
        data = UsdData()
        data.metadata = self.getFieldSetMetadata(fset)
        if 'primChildren' in data.metadata:
            data.metadata.pop('primChildren')
        index = 1
        while index < len(self.paths):
            index, jump = self.readUsdItem(data, index)
        data.resolvePaths()
        return data

    def getTableItem(self, sectionName):
        for name, start, size in self.toc:
            if sectionName == name:
                return (start, size)
        return (0, 0)

    def seekTableOfContents(self):
        self.file.seek(9)
        self.version = readInt(self.file, 1)
        self.file.seek(16)
        tocStart = readInt(self.file, 8)
        self.file.seek(tocStart)

    def readTokensSection(self):
        start, size = self.getTableItem('TOKENS')
        if start > 0 and size > 0:
            self.file.seek(start+8)
            compressedSize = readInt(self.file, 8)
            buffer = bytearray(self.file.read(compressedSize))
            buffer = lz4Decompress(buffer)
            self.tokens = buffer.decode('utf-8').split('\0')
            #print(self.tokens)
            self.tokenMap = {}
            index = 0
            for token in self.tokens:
                self.tokenMap[token] = index
                index += 1

    def readStringsSection(self):
        start, size = self.getTableItem('STRINGS')
        if start > 0 and size > 0:
            self.file.seek(start)
            numStrings = readInt(self.file, 8)
            self.strings = [readInt(self.file, 4) for i in range(numStrings)]

    def readFieldsSection(self):
        start, size = self.getTableItem('FIELDS')
        if start > 0 and size > 0:
            self.file.seek(start)
            numFields = readInt(self.file, 8)
            self.fields = readInt32Compressed(self.file, numFields)
            #print(self.fields)
            size = readInt(self.file, 8)
            buffer = lz4Decompress(self.file.read(size))
            self.reps = decodeInts(buffer, numFields, 8)
            #print(self.reps)

    def readFieldSetsSection(self):
        start, size = self.getTableItem('FIELDSETS')
        if start > 0 and size > 0:
            self.file.seek(start)
            numSets = readInt(self.file, 8)
            self.fsets = readInt32Compressed(self.file, numSets)
            #print(self.fsets)

    def readPathsSection(self):
        start, size = self.getTableItem('PATHS')
        if start > 0 and size > 0:
            self.file.seek(start)
            numPaths = readInt(self.file, 8)
            numPaths = readInt(self.file, 8)
            paths = readInt32Compressed(self.file, numPaths)
            tokens = readInt32Compressed(self.file, numPaths)
            jumps = readInt32Compressed(self.file, numPaths)
            self.paths = []
            for i in range(0, numPaths):
                self.paths.append((paths[i], tokens[i], jumps[i]))
            #print(self.paths)

    def readSpecsSection(self):
        start, size = self.getTableItem('SPECS')
        if start > 0 and size > 0:
            self.file.seek(start)
            numSpecs = readInt(self.file, 8)
            paths = readInt32Compressed(self.file, numSpecs)
            fsets = readInt32Compressed(self.file, numSpecs)
            types = readInt32Compressed(self.file, numSpecs)
            self.specs = []
            for i in range(0, numSpecs):
                self.specs.append((paths[i], fsets[i], types[i]))
                self.specsMap[paths[i]] = (fsets[i], types[i])
            #print(self.specs)

    def readTableOfContents(self):
        self.toc = []
        self.seekTableOfContents()
        numItems = readInt(self.file, 8)
        for i in range(0, numItems):
            name = self.file.read(16).decode('utf-8').rstrip('\0')
            start = readInt(self.file, 8)
            size = readInt(self.file, 8)
            self.toc.append((name, start, size))
        # Read Each Section
        self.readTokensSection()
        self.readStringsSection()
        self.readFieldsSection()
        self.readFieldSetsSection()
        self.readPathsSection()
        self.readSpecsSection()

    def getFieldSet(self, index):
        fset = []
        while index < len(self.fsets) and self.fsets[index] >= 0:
            fset.append(self.fsets[index])
            index += 1
        return fset

    def getTokenStr(self, index):
        index = abs(index)
        if index < len(self.tokens):
            return self.tokens[index]
        return ''

    def getStringStr(self, index):
        if index < len(self.strings):
            return self.getTokenStr(self.strings[index])
        return ''

    def readFloatVector(self, size):
        buffer = self.file.read(4*size)
        if len(buffer) < 4*size:
            return (0.0,)*size
        return struct.unpack('<%df'%size, buffer)
        #return struct.unpack('<%df'%size, self.file.read(4*size))

    def readDoubleVector(self, size):
        buffer = self.file.read(8*size)
        if len(buffer) < 8*size:
            return (0.0,)*size
        return struct.unpack('<%dd'%size, buffer)
        #return struct.unpack('<%dd'%size, self.file.read(8*size))

    def readMatrix(self, size):
        return tuple(self.readDoubleVector(size) for i in range(size))

    def readDictionary(self, loc):
        self.file.seek(loc)
        numItems = readInt(self.file, 8)
        dic = {}
        for i in range(numItems):
            key = self.getStringStr(readInt(self.file, 4))
            itemSize = readInt(self.file, 8)
            loc = self.file.tell()
            if itemSize > 4:
                self.file.seek(loc + itemSize - 4)
                vt = ValueType((readInt(self.file, 4) >> 16) & 0xFF)
                self.file.seek(loc)
                if vt == ValueType.Dictionary:
                    dic[key] = self.readDictionary(loc)
                elif vt == ValueType.string:
                    dic[key] = self.getStringStr(readInt(self.file, 4))
                elif vt == ValueType.bool:
                    dic[key] = readInt(self.file, 4) > 0
                elif vt == ValueType.float:
                    dic[key] = struct.unpack('<f', self.file.read(4))[0]
                elif vt == ValueType.double:
                    dic[key] = struct.unpack('<d', self.file.read(8))[0]
                #else:
                #    print('Unhandled Dictionary Type:', vt.name)
            self.file.seek(loc + itemSize)
        return dic

    def decodeInlineFloatVector(payload, size):
        data = rep['payload'].to_bytes(4*size, byteorder='big')

    def decodeRepFloatVector(self, rep, size):
        if rep['inline']:
            data = rep['payload'].to_bytes(8, byteorder='little')
            return tuple(float(data[i]) for i in range(size))
        self.file.seek(rep['payload'])
        if rep['array']:
            countBytes = 4 if self.version < 7 else 8
            count = readInt(self.file, countBytes)
            return [self.readFloatVector(size) for i in range(count)]
        return self.readFloatVector(size)

    def decodeRepDoubleVector(self, rep, size):
        if rep['inline']:
            data = rep['payload'].to_bytes(8, byteorder='little')
            return tuple(float(data[i]) for i in range(size))
        self.file.seek(rep['payload'])
        if rep['array']:
            countBytes = 4 if self.version < 7 else 8
            count = readInt(self.file, countBytes)
            return [self.readDoubleVector(size) for i in range(count)]
        return self.readDoubleVector(size)

    def decodeRepMatrix(self, rep, size):
        if rep['inline']:
            return makeIdentityMatrix(size)
        self.file.seek(rep['payload'])
        if rep['array']:
            countBytes = 4 if self.version < 7 else 8
            count = readInt(self.file, countBytes)
            return [self.readMatrix(size) for i in range(count)]
        return self.readMatrix(size)

    def readTimeFrames(self, ref):
        self.file.seek(ref)
        self.file.seek(ref + readInt(self.file, 8))
        ref = readInt(self.file, 6) - 8
        vType = ValueType(readInt(self.file, 1))
        self.file.seek(ref + 8)
        if vType == ValueType.DoubleVector:
            return self.readDoubleVector(readInt(self.file, 8))
        print('UnHandled frames value type:', vType.name)
        return []

    def readSampleReps(self, ref):
        self.file.seek(ref)
        self.file.seek(ref + readInt(self.file, 8) + 8)
        count = readInt(self.file, readInt(self.file, 8))
        reps = []
        for i in range(count):
            # Read the refrence and value type
            payload = readInt(self.file, 6)
            vType = readInt(self.file, 1)
            rep = (payload & PAYLOAD_MASK) | (vType << 48)
            elem = readInt(self.file, 1)
            if elem > 0:
                if elem == 64:
                    rep |= INLINE_BIT
                else:
                    rep |= ARRAY_BIT
            reps.append(rep)
        return reps

    def readTimeSamples(self, ref):
        frames = self.readTimeFrames(ref)
        reps = self.readSampleReps(ref)
        return [(f, self.getRepValue(r)) for f, r in zip(frames, reps)]

    def getRepValue(self, rep):
        rep = decodeRep(rep)
        if rep['type'] == ValueType.token:
            if not rep['inline']:
                self.file.seek(rep['payload'])
                numBytes = 4 if self.version < 7 else 8
                numTokens = readInt(self.file, numBytes)
                tokens = []
                for i in range(numTokens):
                    token = readInt(self.file, 4)
                    if (token < len(self.tokens)):
                        tokens.append(self.tokens[token])
                return tokens
            elif rep['payload'] < len(self.tokens):
                return self.tokens[rep['payload']]
        elif rep['type'] == ValueType.asset:
            return '@' + self.tokens[rep['payload']] + '@'
        elif rep['type'] == ValueType.TokenVector:
            self.file.seek(rep['payload'])
            numTokens = readInt(self.file, 8)
            tokens = []
            for i in range(numTokens):
                token = readInt(self.file, 4)
                if (token < len(self.tokens)):
                    tokens.append(self.tokens[token])
            return tokens
        elif rep['type'] == ValueType.PathListOp:
            self.file.seek(rep['payload'])
            listOp = {}
            listOp['op'] = readInt(self.file, 8)
            self.file.seek(self.file.tell()+1)
            listOp['path'] = readInt(self.file, 4)
            return listOp
        elif rep['type'] == ValueType.Variability or rep['type'] == ValueType.bool:
            #print('Boolean:', rep)
            return True if rep['payload'] > 0 else False
        elif rep['type'] == ValueType.PathVector:
            self.file.seek(rep['payload'])
            numPaths = readInt(self.file, 8)
            path = readInt(self.file, 4)
            #print('numPaths', numPaths, 'path', path)
            return path
        elif rep['type'] == ValueType.ReferenceListOp:
            self.file.seek(rep['payload'] + 1)
            numRefs = readInt(self.file, 8)
            strIndex = readInt(self.file, 4)
            pathIndex = readInt(self.file, 8)
            return pathIndex
        elif rep['type'] == ValueType.int:
            if rep['inline']:
                return rep['payload']
            self.file.seek(rep['payload'])
            if rep['array']:
                countBytes = 4 if self.version < 7 else 8
                count = readInt(self.file, countBytes)
                if rep['compressed']:
                    return readInt32Compressed(self.file, count)
                return [readInt(self.file, 4, signed=True) for i in range(count)]
            return readInt(self.file, 4, signed=True)
        elif rep['type'] == ValueType.float:
            if rep['inline']:
                return struct.unpack('<f', rep['payload'].to_bytes(4, byteorder='little'))[0]
            self.file.seek(rep['payload'])
            if rep['array']:
                countBytes = 4 if self.version < 7 else 8
                count = readInt(self.file, countBytes)
                return list(struct.unpack('<%df'%count, self.file.read(4*count)))
            return struct.unpack('<f', self.file.read(4))
        elif rep['type'] == ValueType.double:
            if rep['inline']:
                return struct.unpack('<f', rep['payload'].to_bytes(4, byteorder='little'))[0]
            self.file.seek(rep['payload'])
            if rep['array']:
                countBytes = 4 if self.version < 7 else 8
                count = readInt(self.file, countBytes)
                return list(struct.unpack('<%dd'%count, self.file.read(8*count)))
            return struct.unpack('<d', self.file.read(8))
        elif rep['type'] == ValueType.vec2f:
            return self.decodeRepFloatVector(rep, 2)
        elif rep['type'] == ValueType.vec3f:
            return self.decodeRepFloatVector(rep, 3)
        elif rep['type'] in (ValueType.vec4f, ValueType.quatf):
            return self.decodeRepFloatVector(rep, 4)
        elif rep['type'] == ValueType.vec2d:
            return self.decodeRepDoubleVector(rep, 2)
        elif rep['type'] == ValueType.vec3d:
            return self.decodeRepDoubleVector(rep, 3)
        elif rep['type'] in (ValueType.vec4d, ValueType.quatd):
            return self.decodeRepDoubleVector(rep, 4)
        elif rep['type'] == ValueType.matrix2d:
            return self.decodeRepMatrix(rep, 2)
        elif rep['type'] == ValueType.matrix3d:
            return self.decodeRepMatrix(rep, 3)
        elif rep['type'] == ValueType.matrix4d:
            return self.decodeRepMatrix(rep, 4)
        elif rep['type'] == ValueType.Dictionary:
            return self.readDictionary(rep['payload'])
        elif rep['type'] == ValueType.TimeSamples:
            return self.readTimeSamples(rep['payload'])
        #else:
        #    print('UnHandled Type:', rep)
        return rep
