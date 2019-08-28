import bpy
import os
import subprocess
import tempfile
import shutil
import zipfile
import bmesh
import mathutils

from io_scene_usdz.file_data import *
from io_scene_usdz.scene_data import *
from io_scene_usdz.object_utils import *
from io_scene_usdz.material_utils import *

def find_usdz(dirpath):
    files = os.listdir(dirpath)
    for file in files:
        parts = file.split('.')
        if len(parts) > 0 and parts[-1] == 'usdc':
            return dirpath + '/' + file
    return ''


def import_usdz(context, filepath = '', materials = True):
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
                import_data(context, data, materials)
            else:
                print('No usdc file found')

            # Cleanup Temp Files
            if tempPath != None:
                shutil.rmtree(tempPath)

    return {'FINISHED'}


def import_data(context, data, materials):
    materials = get_materials(data) if materials else {}
    objects = get_objects(data)
    #print(materials)
    for objData in objects:
        add_object(context, objData, materials)


def add_object(context, data, materials = {}, parent = None):
    meshes = get_meshes(data)
    if len(meshes) > 0:
        #print(meshes[0].printUsda())
        # Create A Mesh Object
        obj = create_mesh_object(meshes[0].name, data.name)
        add_to_collection(obj, context.scene.collection)

        # Create any UV maps
        uvs = get_uv_map_names(meshes[0])
        for uv in uvs:
            obj.data.uv_layers.new(name=uv)

        # Add the Geometry
        for mesh in meshes:
            add_mesh(obj, mesh, uvs, materials)
        obj.data.update()

        if parent != None:
            obj.parent = parent

        # Apply any Transforms
        matrix = mathutils.Matrix()
        opOrder = data.getItemOfName('xformOpOrder')
        if opOrder != None and opOrder.data != None:
            for op in opOrder.data:
                opItem = data.getItemOfName(op)
                if opItem.name == 'xformOp:transform':
                    m = mathutils.Matrix(opItem.data)
                    m.transpose()
                    matrix = matrix @ m
        if parent == None:
            matrix = matrix @ mathutils.Matrix.Rotation(pi/2.0, 4, 'X')
        obj.matrix_local = matrix

        # Add the Children
        children = get_objects(data)
        for child in children:
            add_object(context, child, materials, obj)


def add_mesh(obj, data, uvs, materials):
    # Get Geometry From Data
    counts = data.getItemOfName('faceVertexCounts').data
    indices = data.getItemOfName('faceVertexIndices').data
    verts = data.getItemOfName('points').data
    normals = data.getItemOfName('primvars:normals:indices')
    normals = None if normals == None else normals.data
    uvMaps = {}
    for uv in uvs:
        uvCoords = data.getItemOfName('primvars:'+uv).data
        uvIndices = data.getItemOfName('primvars:'+uv+':indices').data
        uvMaps[uv] = [uvCoords[i] for i in uvIndices]

    # Compile Faces
    faces = []
    smooth = []
    index = 0
    for count in counts:
        faces.append(tuple([indices[index+i] for i in range(count)]))
        if normals != None:
            smooth.append(len(set(normals[index+i] for i in range(count))) > 1)
        else:
            smooth.append(True)
        index += count

    # Assign the Material
    matIndex = 0
    matRel = data.getItemOfName('material:binding')
    if matRel != None:
        matName = matRel.data.strip('<>')
        matName = matName[matName.rfind('/')+1:]
        if matName in materials:
            matIndex = len(obj.data.materials)
            obj.data.materials.append(materials[matName])

    # Create BMesh from Mesh Object
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    # Add the Vertices
    base = len(bm.verts)
    for vert in verts:
        bm.verts.new(vert)
    bm.verts.ensure_lookup_table()

    # Add the Faces
    index = 0
    for i, face in enumerate(faces):
        f = bm.faces.new((bm.verts[i+base] for i in face))
        f.smooth = smooth[i]
        f.material_index = matIndex

    # Add the UVs
    for uvName, uvs in uvMaps.items():
        uvIndex = bm.loops.layers.uv[uvName]
        index = 0
        for f in bm.faces[-len(faces):]:
            for i, l in enumerate(f.loops):
                l[uvIndex].uv = uvs[index+i]
            index += len(f.loops)

    # Apply BMesh back to Mesh Object
    bm.to_mesh(obj.data)
    bm.free()


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

def get_materials(data):
    materialMap = {}
    #print(data.printUsda())
    materials = data.getItemsOfType('Material')
    for matData in materials:
        print(matData.printUsda())
        mat = create_material(matData.name)
        materialMap[matData.name] = mat
    return materialMap

def get_uv_map_names(mesh):
    uvs = []
    for item in mesh.items:
        if item.type == 'texCoord2f[]' or item.type == 'float2[]':
            uvs.append(item.name[9:])
    return uvs
