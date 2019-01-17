import bpy
import os
import sys
import importlib

scriptPath = bpy.path.abspath("//") + '//..//io_scene_usdz'
if not scriptPath in sys.path:
    sys.path.append(scriptPath)

import export_usdz
importlib.reload(export_usdz)

# Create an Exports Directory
exportsDir = bpy.path.abspath("//") + 'exports/'
if not os.path.exists(exportsDir):
    os.makedirs(exportsDir)

# Call the Export Function
export_usdz.export_usdz(
    context = bpy.context, 
    filepath = exportsDir + 'test.usdz',
    materials = True,
    bakeAO = False,
    samples = 8,
    scale = 1.0,
    )
