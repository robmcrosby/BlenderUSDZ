import bpy
import os
import sys
import importlib

from struct import *

scriptPath = bpy.path.abspath("//") + '//..'
if not scriptPath in sys.path:
    sys.path.append(scriptPath)

import io_scene_usdz

importlib.reload(io_scene_usdz)

import io_scene_usdz.compression_utils

importlib.reload(io_scene_usdz.compression_utils)


from io_scene_usdz.compression_utils import lz4Decompress, lz4Compress, usdInt32Decompress, usdInt32Compress


exportsDir = bpy.path.abspath("//") + 'exports/'
#filepath = exportsDir + 'test.usdc'
#filepath = exportsDir + 'testMat.usdc'
filepath = exportsDir + 'testCopy.usdc'
#filepath = exportsDir + 'testEmpty.usdc'

print(filepath)


def readInt(file, size, byteorder='little', signed=False):
    return int.from_bytes(file.read(size), byteorder, signed=signed)

def readStr(file, size, encoding='utf-8'):
    data = file.read(size)
    return data[:data.find(0)].decode(encoding=encoding)

def decodeStrings(data, count):
    strings = []
    while count > 0:
        p = data.find(0)
        if p < 0:
            break
        strings.append(data[:p].decode("utf-8"))
        data = data[p+1:]
        count -= 1
    return strings

def decodeInts(data, count, size, byteorder='little', signed=False):
    ints = []
    for i in range(count):
        if i * size > len(data):
            print('Over Run Data')
            break
        value = int.from_bytes(data[i*size:i*size + size], byteorder, signed=signed)
        ints.append(value)
    return ints
    

SpecTypes = {
    1 :'Attribute',
    2 :'Connection',
    3 :'Expression',
    4 :'Mapper',
    5 :'MapperArg',
    6 :'Prim',
    7 :'PseudoRoot',
    8 :'Relationship',
    9 :'RelationshipTarget',
    10:'Variant',
    11:'VariantSet'
}
def getSpecType(type):
    return SpecTypes.get(type, 'Unknown')


ValueTypes = {
    0 :'Invalid',
    1 :'Bool',
    2 :'UChar',
    3 :'Int',
    4 :'UInt',
    5 :'Int64',
    6 :'UInt64',
    7 :'Half',
    8 :'Float',
    9 :'Double',
    10:'String',
    11:'Token',
    12:'AssetPath',
    13:'Matrix2d',
    14:'Matrix3d',
    15:'Matrix4d',
    16:'Quatd',
    17:'Quatf',
    18:'Quath',
    19:'Vec2d',
    20:'Vec2f',
    21:'Vec2h',
    22:'Vec2i',
    23:'Vec3d',
    24:'Vec3f',
    25:'Vec3h',
    26:'Vec3i',
    27:'Vec4d',
    28:'Vec4f',
    29:'Vec4h',
    30:'Vec4i',
    31:'Dictionary',
    32:'TokenListOp',
    33:'StringListOp',
    34:'PathListOp',
    35:'ReferenceListOp',
    36:'IntListOp',
    37:'Int64ListOp',
    38:'UIntListOp',
    39:'UInt64ListOp',
    40:'PathVector',
    41:'TokenVector',
    42:'Specifier',
    43:'Permission',
    44:'Variability',
    45:'VariantSelectionMap',
    46:'TimeSamples',
    47:'Payload',
    48:'DoubleVector',
    49:'LayerOffsetVector',
    50:'StringVector',
    51:'ValueBlock',
    52:'Value',
    53:'UnregisteredValue',
    54:'UnregisteredValueListOp',
    55:'PayloadListOp'
}
def getValueType(type):
    return ValueTypes.get(type, 'Unknown:%d' % type)


SpecifierTypes = {
    0:'Def',
    1:'Over',
    2:'Class'
}
def getSpecifierType(type):
    return SpecifierTypes.get(type, 'Unknown:%d' % type)


def getFieldSet(tokens, fields, fieldSets, index):
    fieldSet = []
    if len(fieldSets) > 0:
        i = fieldSets[index]
        while i >= 0 and index+1 < len(fieldSets) and i < len(fields):
            fieldSet.append(tokens[fields[i]])
            index += 1
            i = fieldSets[index]
    return fieldSet


ARRAY_BIT = (1 << 63)
INLINE_BIT = (1 << 62)
COMPRESSED_BIT = (1 << 61)
PAYLOAD_MASK = (1 << 48) - 1

def decodeRep(data):
    rep = {}
    rep['type'] = getValueType((data >> 48) & 0xFF)
    rep['array'] = (data & ARRAY_BIT) != 0
    rep['inline'] = (data & INLINE_BIT) != 0
    rep['compressed'] = (data & COMPRESSED_BIT) != 0
    rep['payload'] = data & PAYLOAD_MASK
    return rep

def decodeReps(data, numReps):
    reps = []
    values = decodeInts(data, numFields, 8)
    for value in values:
        reps.append(decodeRep(value))
    return reps

def getRepValue(rep, file, tokens):
    if rep['type'] == 'Token':
        if rep['inline']:
            return tokens[rep['payload']]
        elif rep['array']:
            file.seek(rep['payload'])
            num = readInt(file, 4)
            values = []
            while num > 0:
                values.append(tokens[readInt(file, 4)])
                num -= 1
            return values
    elif rep['type'] == 'TokenVector':
        file.seek(rep['payload'])
        num = readInt(file, 8)
        values = []
        while num > 0:
            values.append(tokens[readInt(file, 4)])
            num -= 1
        return values
    elif rep['type'] == 'Specifier':
        return getSpecifierType(rep['payload'])
    elif rep['type'] == 'Int':
        if not rep['inline'] and rep['array']:
            file.seek(rep['payload'])
            num = readInt(file, 4)
            values = []
            while num > 0:
                values.append(readInt(file, 4, signed=True))
                num -= 1
            return values
    elif rep['type'] == 'Vec2f':
        if not rep['inline'] and rep['array']:
            file.seek(rep['payload'])
            num = readInt(file, 4)
            values = []
            while num > 0:
                values.append(unpack('<ff', file.read(8)))
                num -= 1
            return values
    elif rep['type'] == 'Vec3f':
        if not rep['inline'] and rep['array']:
            file.seek(rep['payload'])
            num = readInt(file, 4)
            values = []
            while num > 0:
                values.append(unpack('<fff', file.read(12)))
                num -= 1
            return values
    elif rep['type'] == 'Bool' or rep['type'] == 'Variability':
        if rep['inline'] and not rep['array']:
            return rep['payload'] != 0
    elif rep['type'] == 'Matrix4d':
        if not rep['inline'] and not rep['array']:
            file.seek(rep['payload'])
            num = 4
            values = []
            while num > 0:
                values.append(unpack('<dddd', file.read(32)))
                num -= 1
            return values
    return None


with open(filepath, 'rb') as file:
    file.seek(16)
    tocOffset = readInt(file, 8)
    
    file.seek(tocOffset)
    tocItems = readInt(file, 8)
    toc = {}
    for i in range(tocItems):
        key = readStr(file, 16)
        offset = readInt(file, 8)
        size = readInt(file, 8)
        toc[key] = (offset, size)
    print(toc)
    
    offset, size = toc['TOKENS']
    file.seek(offset)
    
    numTokens = readInt(file, 8)
    dataSize = readInt(file, 8)
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    
    tokens = decodeStrings(data, numTokens)
    print('\nTOKENS (', offset, ':', offset+size, ')')
    print(tokens)
    
    offset, size = toc['STRINGS']
    file.seek(offset)
    numStrings = readInt(file, 8)
    data = file.read(numStrings*4)
    strings = decodeInts(data, numStrings, 4)
    print('\nSTRINGS (', offset, ':', offset+size, ')')
    print(strings)
    
    offset, size = toc['FIELDS']
    file.seek(offset)
    numFields = readInt(file, 8)
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    fields = usdInt32Decompress(data, numFields)
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    reps = decodeReps(data, numFields) #decodeInts(data, numFields, 8)
    print('\nFIELDS (', offset, ':', offset+size, ')')
    
    for i in range(len(fields)):
        field = tokens[fields[i]]
        rep = reps[i]
        value = getRepValue(rep, file, tokens)
        if value != None:
            print(i, '\t', field, '\t= (', rep['type'], ') ',value)
        else:
            print(i, '\t', field,'\t= ',rep)
    
    #print('fields:', fields)
    #for rep in reps:
    #    print(rep)
    #    value = getRepValue(rep, file, tokens)
    #    if value != None:
    #        print('   ', value)
    #print('reps:', reps)
    
    offset, size = toc['FIELDSETS']
    file.seek(offset)
    numFieldSets = readInt(file, 8)
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    fieldSets = usdInt32Decompress(data, numFieldSets)
    print('\nFIELDSETS (', offset, ':', offset+size, ')')
    i = 0
    while i < len(fieldSets):
        index = i
        set = []
        while i < len(fieldSets) and fieldSets[i] >= 0:
            set.append(fieldSets[i])
            i += 1
        print(index, ':', set)
        i += 1
    #print(fieldSets)
    
    offset, size = toc['PATHS']
    file.seek(offset)
    totalPaths = readInt(file, 8)
    numPaths = readInt(file, 8)
    # Get Path Indices
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    pathIndices = usdInt32Decompress(data, numPaths)
    # Get Element Token Indices
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    elementTokenIndices = usdInt32Decompress(data, numPaths)
    # Get Jumps
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    jumps = usdInt32Decompress(data, numPaths)
    
    paths = []
    for i in range(numPaths):
        path = {}
        path['index'] = pathIndices[i]
        path['element'] = tokens[abs(elementTokenIndices[i])]
        path['prim'] = elementTokenIndices[i] < 0
        path['jump'] = jumps[i]
        path['type'] = 'both'
        if path['jump'] == 0:
            path['type'] = 'sibling'
        elif path['jump'] == -1:
            path['type'] = 'child'
        elif path['jump'] == -2:
            path['type'] = 'leaf'
        paths.append(path)
    
    #data = file.read(size)
    print('\nPATHS (', offset, ':', offset+size, ')')
    for path in paths:
        print(path['index'], ':', path['element'], 'prim:', path['prim'], 'jump:', path['jump'], path['type'])
    #print('pathIndices:', pathIndices)
    #print('elementTokenIndices:', elementTokenIndices)
    #print('jumps:', jumps)
    #print(data)
    
    offset, size = toc['SPECS']
    file.seek(offset)
    numSpecs = readInt(file, 8)
    # Get path indices
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    pathIndices = usdInt32Decompress(data, numSpecs)
    # Get fset indices
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    fsetIndices = usdInt32Decompress(data, numSpecs)
    # Get spec types
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    specTypes = usdInt32Decompress(data, numSpecs)
    
    specs = []
    for i in range(numSpecs):
        spec = {}
        spec['path'] = pathIndices[i]
        #spec['fset'] = getFieldSet(tokens, fields, fieldSets, fsetIndices[i])
        spec['fset'] = fsetIndices[i]
        spec['type'] = getSpecType(specTypes[i])
        #spec['value'] = 
        specs.append(spec)
    
    print('\nSPECS (', offset, ':', offset+size, ')')
    for spec in specs:
        print(spec['path'], ':', spec['type'], spec['fset'])
    #print('pathIndices:', pathIndices)
    #print('fsetIndices:', fsetIndices)
    #print('specTypes:', specTypes)
    #print(data)
