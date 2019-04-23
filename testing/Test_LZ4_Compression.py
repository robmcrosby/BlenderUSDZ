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


from io_scene_usdz.compression_utils import lz4Decompress


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
    #print('%d tokens found' % numTokens)
    #print('data size %d' % dataSize)
    #print('comrpessed size %d' % compressedSize)
    
    data = file.read(compressedSize)
    data = lz4Decompress(data)
    
    print(data)
    
    


"""

buffer = b'\x0C\x00\x00\x00\x00\x00\x00\x00\x00\xA0\x75\x70\x41\x78\x69\x73\x00\x59\x00\x00'
buffer = lz4Decompress(buffer)
print(buffer)
"""
