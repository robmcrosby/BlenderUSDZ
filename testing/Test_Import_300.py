import bpy
import os
import sys
import importlib

#scriptPath = bpy.path.abspath("//") + '//..//io_scene_usdz'
scriptPath = bpy.path.abspath("//") + '//..'
if not scriptPath in sys.path:
    sys.path.append(scriptPath)

import io_scene_usdz
#from io_scene_usdz.object_utils import *

importlib.reload(io_scene_usdz)

import io_scene_usdz.compression_utils
import io_scene_usdz.value_types
import io_scene_usdz.crate_file
import io_scene_usdz.object_utils
import io_scene_usdz.material_utils
import io_scene_usdz.scene_data
import io_scene_usdz.import_usdz

importlib.reload(io_scene_usdz.compression_utils)
importlib.reload(io_scene_usdz.value_types)
importlib.reload(io_scene_usdz.crate_file)
importlib.reload(io_scene_usdz.object_utils)
importlib.reload(io_scene_usdz.material_utils)
importlib.reload(io_scene_usdz.scene_data)
importlib.reload(io_scene_usdz.import_usdz)


from io_scene_usdz.import_usdz import import_usdz


# Create an Exports Directory
exportsDir = bpy.path.abspath("//") + 'exports/'
if not os.path.exists(exportsDir):
    os.makedirs(exportsDir)

#filepath = exportsDir + 'teapot.usdz'
#filepath = exportsDir + 'testCopy.usdz'
filepath = exportsDir + 'test.usdz'

# Call the Import Function
import_usdz(
    context = bpy.context, 
    filepath = filepath,
    materials = True,
    animations = True,
    )
