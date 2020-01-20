import bpy
import os
import sys
import importlib

import io_scene_usdz

importlib.reload(io_scene_usdz)

import io_scene_usdz.compression_utils

importlib.reload(io_scene_usdz.compression_utils)


from io_scene_usdz.compression_utils import lz4Compress, lz4Decompress



bufferIn = b'test'
print('bufferIn:', bufferIn)

bufferCompressed = lz4Compress(bufferIn)
print('bufferCompressed:', bufferCompressed)

bufferOut = lz4Decompress(bufferCompressed)
print('bufferOut:', bufferOut)
