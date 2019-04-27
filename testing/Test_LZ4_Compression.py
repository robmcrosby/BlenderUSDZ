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
filepath = exportsDir + 'testMat.usdc'
#filepath = exportsDir + 'testCopy.usdc'
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
    #print(toc)
    
    offset, size = toc['TOKENS']
    file.seek(offset)
    
    numTokens = readInt(file, 8)
    dataSize = readInt(file, 8)
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    
    tokens = decodeStrings(data, numTokens)
    print('\nTOKENS')
    print(tokens)
    
    offset, size = toc['STRINGS']
    file.seek(offset)
    numStrings = readInt(file, 8)
    data = file.read(numStrings*4)
    strings = decodeInts(data, numStrings, 4)
    print('\nSTRINGS')
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
    reps = decodeInts(data, numFields, 8)
    print('\nFIELDS')
    print('fields:', fields)
    print('reps:', reps)
    
    
    offset, size = toc['FIELDSETS']
    file.seek(offset)
    numFieldSets = readInt(file, 8)
    compressedSize = readInt(file, 8)
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    fieldSets = usdInt32Decompress(data, numFieldSets)
    print('\nFIELDSETS')
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
    #data = file.read(size)
    print('\nPATHS')
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
    #data = file.read(size)
    print('\nSPECS')
    print('pathIndices:', pathIndices)
    print('fsetIndices:', fsetIndices)
    print('specTypes:', specTypes)
    #print(data)

