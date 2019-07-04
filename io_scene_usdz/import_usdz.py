import bpy
import os
import subprocess
import tempfile
import shutil
import zipfile

from io_scene_usdz.file_data import *
from io_scene_usdz.scene_data import *

def find_usdz(dirpath):
    files = os.listdir(dirpath)
    for file in files:
        parts = file.split('.')
        if len(parts) > 0 and parts[-1] == 'usdc':
            return dirpath + '/' + file
    return ''


def import_usdz(context, filepath = ''):
    filePath, fileName = os.path.split(filepath)
    fileName, fileType = fileName.split('.')

    if fileType == 'usdz':
        print('filepath', filepath)
        with zipfile.ZipFile(filepath, 'r') as zf:
            # Create a temp directory to extract to
            tempPath = tempfile.mkdtemp()
            zf.extractall(tempPath)
            zf.close()

            # Find the usdc file
            usdcFile = find_usdz(tempPath)
            if usdcFile != '':
                print('usdc file:', usdcFile)
            else:
                print('No usdc file found')

            # Cleanup Temp Files
            if tempPath != None:
                shutil.rmtree(tempPath)

    return {'FINISHED'}
