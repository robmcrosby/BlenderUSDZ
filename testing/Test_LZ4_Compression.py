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
filepath = exportsDir + 'testCopy.usdc'
#filepath = exportsDir + 'testEmpty.usdc'

print(filepath)


def readInt(file, size, byteorder='little'):
    return int.from_bytes(file.read(size), byteorder=byteorder)

def readStr(file, size, encoding='utf-8'):
    data = file.read(size)
    return data[:data.find(0)].decode(encoding=encoding)

def readStrings(data, count):
    strings = []
    while count > 0:
        p = data.find(0)
        if p < 0:
            break
        strings.append(data[:p].decode("utf-8"))
        data = data[p+1:]
        count -= 1
    return strings

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
    #print('%d tokens found' % numTokens)
    #print('data size %d' % dataSize)
    #print('comrpessed size %d' % compressedSize)
    
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    
    tokens = readStrings(data, numTokens)
    #print(tokens)
    
    offset, size = toc['STRINGS']
    file.seek(offset)
    data = file.read(size)
    #print('STRINGS')
    #print(data)
    
    offset, size = toc['FIELDS']
    file.seek(offset)
    
    #data = file.read(size)
    numFields = readInt(file, 8)
    compressedSize = readInt(file, 8)
    print('Number of Fields %d' % numFields)
    print('comrpessed size %d' % compressedSize)
    data = file.read(compressedSize)
    print(data)
    data = lz4Decompress(data)
    fields = usdInt32Decompress(data, numFields)
    #print('FIELDS')
    #print(fields)
    data = usdInt32Compress(fields)
    data = lz4Compress(data)
    print(data)
    
    
    offset, size = toc['FIELDSETS']
    file.seek(offset)
    data = file.read(size)
    #print('FIELDSETS')
    #print(data)
    
    offset, size = toc['PATHS']
    file.seek(offset)
    data = file.read(size)
    #print('PATHS')
    #print(data)
    
    offset, size = toc['SPECS']
    file.seek(offset)
    data = file.read(size)
    #print('SPECS')
    #print(data)

