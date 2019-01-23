import bpy
import os
import subprocess

#from . import file_data
#from . import scene_data
import file_data
import scene_data

#from .file_data import *
#from .scene_data import *
from file_data import *
from scene_data import *

def export_usdz(context, filepath = '', materials = True, keepUSDA = False,
                bakeAO = False, samples = 8, scale = 1.0, animated = False):
    filePath, fileName = os.path.split(filepath)
    fileName, fileType = fileName.split('.')

    usdaFile = filePath+'/'+fileName+'.usda'
    usdzFile = filePath+'/'+fileName+'.usdz'

    scene = Scene()
    scene.loadContext(context)
    scene.exportMaterials = materials
    scene.exportPath = filePath
    scene.bakeAO = bakeAO
    scene.bakeSamples = samples
    scene.scale = scale
    scene.animated = animated

    # Export images and write the text USDA file
    data = scene.exportFileData()
    data.writeUsda(usdaFile)

    # Run the USDZ Converter Tool
    args = ['xcrun', 'usdz_converter', usdaFile, usdzFile]
    args += ['-v']
    args += scene.getUsdzConverterArgs()
    subprocess.run(args)

    scene.cleanup()
    return {'FINISHED'}
