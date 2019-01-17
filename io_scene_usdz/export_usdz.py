import bpy
import os

def export_usdz(context,filepath = '', materials = True, keepUSDA = False, bakeAO = False, samples = 8, scale = 1.0, animated = False):
    filePath, fileName = os.path.split(filepath)
    fileName, fileType = fileName.split('.')

    #print('Run Export USDZ')
    print(filepath)
    return {'FINISHED'}
