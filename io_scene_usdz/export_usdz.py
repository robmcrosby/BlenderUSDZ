import bpy
import os

import file_data

def export_usdz(context,filepath = '', materials = True, keepUSDA = False, bakeAO = False, samples = 8, scale = 1.0, animated = False):
    filePath, fileName = os.path.split(filepath)
    fileName, fileType = fileName.split('.')

    #print('Run Export USDZ')
    #print(filepath)
    file_data.test_file()
    return {'FINISHED'}
