import bpy
import os
import subprocess
import tempfile
import shutil
import zipfile

from io_scene_usdz.file_data import *
from io_scene_usdz.scene_data import *
from io_scene_usdz.object_utils import *

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
        with zipfile.ZipFile(filepath, 'r') as zf:
            # Create a temp directory to extract to
            tempPath = tempfile.mkdtemp()
            zf.extractall(tempPath)
            zf.close()

            # Find the usdc file
            usdcFile = find_usdz(tempPath)
            if usdcFile != '':
                data = FileData()
                data.readUsdc(usdcFile)
                import_data(context, data)
            else:
                print('No usdc file found')

            # Cleanup Temp Files
            if tempPath != None:
                shutil.rmtree(tempPath)

    return {'FINISHED'}

def import_data(context, data):
    meshes = data.getItemsOfType('Mesh')
    for mesh in meshes:
        add_mesh(context, mesh)

def add_mesh(context, data):
    # Get Geometry From Data
    counts = data.getItemOfName('faceVertexCounts').data
    indices = data.getItemOfName('faceVertexIndices').data
    verts = data.getItemOfName('points').data

    # Compile Faces
    faces = []
    index = 0
    for count in counts:
        faces.append(tuple([indices[index+i] for i in range(count)]))
        index += count

    # Create Object and Mesh
    obj = create_mesh_object(data.name, data.name)
    add_to_collection(obj, context.scene.collection)

    # Add Geometry to Mesh
    obj.data.from_pydata(verts, [], faces)
    obj.data.update()
