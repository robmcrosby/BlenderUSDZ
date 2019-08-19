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
    objects = get_objects(data)
    for obj in objects:
        add_object(context, obj)


def add_object(context, data, parent = None):
    meshes = get_meshes(data)
    if len(meshes) > 0:
        # Create A Mesh Object
        obj = create_mesh_object(meshes[0].name, data.name)
        add_to_collection(obj, context.scene.collection)

        # Add the Geometry
        for mesh in meshes:
            add_mesh(obj, mesh)
        obj.data.update()


def add_mesh(obj, data):
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

    # Add Geometry to the Object
    obj.data.from_pydata(verts, [], faces)


def get_objects(data):
    objects = []
    for item in data.items:
        if item.type == 'def Scope':
            objects += get_objects(item)
        elif item.type == 'def Xform':
            objects.append(item)
    return objects


def get_meshes(data):
    meshes = []
    for item in data.items:
        if item.type == 'def Scope':
            meshes += get_meshes(item)
        elif item.type == 'def Mesh':
            meshes.append(item)
    return meshes
