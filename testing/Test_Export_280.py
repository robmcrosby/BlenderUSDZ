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

import io_scene_usdz.object_utils
import io_scene_usdz.material_utils
import io_scene_usdz.file_data
import io_scene_usdz.scene_data
import io_scene_usdz.export_usdz

importlib.reload(io_scene_usdz.object_utils)
importlib.reload(io_scene_usdz.material_utils)
importlib.reload(io_scene_usdz.file_data)
importlib.reload(io_scene_usdz.scene_data)
importlib.reload(io_scene_usdz.export_usdz)


from io_scene_usdz.export_usdz import export_usdz


# Create an Exports Directory
exportsDir = bpy.path.abspath("//") + 'exports/'
if not os.path.exists(exportsDir):
    os.makedirs(exportsDir)

# Call the Export Function
export_usdz(
    context = bpy.context, 
    filepath = exportsDir + 'test.usdz',
    materials = True,
    keepUSDA = True,
    bakeTextures = False,
    bakeAO = False,
    bakeSeparate = False,
    samples = 8,
    scale = 10.0,
    animated = True,
    )
