import bpy
import os

import file_data
import scene_data

from file_data import *
from scene_data import *

def export_usdz(context, filepath = '', materials = True, keepUSDA = False,
                bakeAO = False, samples = 8, scale = 1.0, animated = False):
    filePath, fileName = os.path.split(filepath)
    fileName, fileType = fileName.split('.')

    usdaFile = filePath+'/'+fileName+'.usda'

    scene = Scene()
    scene.loadContext(context)
    scene.exportMaterials = materials
    scene.bakeAO = bakeAO
    scene.bakeSamples = samples
    scene.scale = scale
    scene.animated = animated

    data = scene.exportFileData()
    data.writeUsda(usdaFile)

    return {'FINISHED'}
