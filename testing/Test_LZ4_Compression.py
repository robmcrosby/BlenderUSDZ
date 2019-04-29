import bpy
import os
import sys
import importlib

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
#filepath = exportsDir + 'testCopy.usdc'
filepath = exportsDir + 'testEmpty.usdc'

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
    0 :'Bool',
    1 :'UChar',
    2 :'Int',
    3 :'UInt',
    4 :'Int64',
    5 :'UInt64',
    6 :'Half',
    7 :'Float',
    8 :'Double',
    9 :'String',
    10:'Token',
    11:'AssetPath',
    12:'Matrix2d',
    13:'Matrix3d',
    14:'Matrix4d',
    15:'Quatd',
    16:'Quatf',
    17:'Quath',
    18:'Vec2d',
    19:'Vec2f',
    20:'Vec2h',
    21:'Vec2i',
    22:'Vec3d',
    23:'Vec3f',
    24:'Vec3h',
    25:'Vec3i',
    26:'Vec4d',
    27:'Vec4f',
    28:'Vec4h',
    29:'Vec4i'
}
def getValueType(type):
    return ValueTypes.get(type, 'Unknown:%d' % type)



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
    #rep['array'] = ((data >> 63) & 1) == 1
    #rep['inline'] = ((data >> 62) & 1) == 1
    #rep['compressed'] = ((data >> 61) & 1) == 1
    return rep

def decodeReps(data, numReps):
    reps = []
    values = decodeInts(data, numFields, 8)
    for value in values:
        reps.append(decodeRep(value))
    return reps


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
    print('fields:', fields)
    #for rep in reps:
    #    print(rep)
    print('reps:', reps)
    
    
    offset, size = toc['FIELDSETS']
    file.seek(offset)
    numFieldSets = readInt(file, 8)
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    fieldSets = usdInt32Decompress(data, numFieldSets)
    print('\nFIELDSETS (', offset, ':', offset+size, ')')
    print(fieldSets)
    
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
    #for path in paths:
    #    print(path)
    print('pathIndices:', pathIndices)
    print('elementTokenIndices:', elementTokenIndices)
    print('jumps:', jumps)
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
        spec['fset'] = getFieldSet(tokens, fields, fieldSets, fsetIndices[i])
        spec['type'] = getSpecType(specTypes[i])
        #spec['value'] = 
        specs.append(spec)
    
    print('\nSPECS (', offset, ':', offset+size, ')')
    #for spec in specs:
    #    print(spec)
    print('pathIndices:', pathIndices)
    print('fsetIndices:', fsetIndices)
    print('specTypes:', specTypes)
    #print(data)

