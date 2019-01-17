import bpy
import os

def export_usdz(context, filepath = '', exportMaterials = True, keepUSDA = False, bakeAO = False, samples = 8, scale = 1.0, animated = False):
    filePath, fileName = os.path.split(filepath)
    fileName, fileType = fileName.split('.')

    print(filepath)

    return {'FINISHED'}
