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
            try:
                zf.extractall(tempPath)
            except Exception as e:
                print(e)
            zf.close()

            # Find the usdc file
            usdcFile = find_usdz(tempPath)
            if usdcFile != '':
                file = open(usdcFile, 'rb')
                crate = CrateFile(file)
                usdData = crate.readUsd()
                file.close()

                print(usdData)
                #data = FileData()
                #data.readUsdc(usdcFile)
                #tempDir = usdcFile[:usdcFile.rfind('/')+1]
                #import_data(context, data, materials, tempDir)
            else:
                print('No usdc file found')

            # Cleanup Temp Files
            if tempPath != None:
                shutil.rmtree(tempPath)

    return {'FINISHED'}


def import_data(context, data, materials, tempDir):
    materials = get_materials(data, tempDir) if materials else {}
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
                if opItem != None and opItem.name == 'xformOp:transform':
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
    if matRel == None:
        geomSubsets = data.getItemsOfType('GeomSubset')
        if len(geomSubsets) > 0:
            matRel = geomSubsets[0].getItemOfName('material:binding')
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
                if index+i < len(uvs):
                    l[uvIndex].uv = uvs[index+i]
                else:
                    l[uvIndex].uv = (0.0, 0.0)
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

def get_materials(data, tempDir):
    materialMap = {}
    #print(data.printUsda(reduced = True))
    materials = data.getItemsOfType('Material')
    for matData in materials:
        #print(matData.printUsda())
        mat = create_material(matData, tempDir)
        materialMap[matData.name] = mat
    return materialMap

def create_material(data, tempDir):
    shader = get_shader_data(data)
    #print('Shader:', shader.printUsda())

    mat = bpy.data.materials.new(data.name)
    mat.use_nodes = True

    set_material_values(data, mat, tempDir, 'diffuseColor', 'Base Color')
    set_material_values(data, mat, tempDir, 'clearcoat', 'Clearcoat')
    set_material_values(data, mat, tempDir, 'clearcoatRoughness', 'Clearcoat Roughness')
    set_material_values(data, mat, tempDir, 'emissiveColor', 'Emissive')
    set_material_values(data, mat, tempDir, 'ior', 'IOR')
    set_material_values(data, mat, tempDir, 'metallic', 'Metallic')
    set_material_values(data, mat, tempDir, 'normal', 'Normal')
    #set_material_values(data, mat, tempDir, 'occlusion', 'Occlusion')
    set_material_values(data, mat, tempDir, 'roughness', 'Roughness')
    set_material_values(data, mat, tempDir, 'specularColor', 'Specular')

    return mat

def get_shader_data(materialData):
    name = materialData.getItemOfName('outputs:surface.connect')
    if name != None and name.data != None:
        name = name.data[name.data.rfind('/')+1:name.data.find('.outputs')]
        return materialData.getItemOfName(name)
    return None


def set_material_values(matData, mat, tempDir, valName, inputName):
    shaderData = get_shader_data(matData)
    valData = shaderData.getItemOfName('inputs:'+valName)
    if valData != None:
        set_shader_input_value(valData, mat, inputName)
    else:
        valData = shaderData.getItemOfName('inputs:'+valName+'.connect')
        if valData != None:
            set_shader_input_texture(valData, mat, inputName, matData, tempDir)


def set_shader_input_value(data, mat, inputName):
    outputNode = get_output_node(mat)
    shaderNode = get_shader_node(outputNode)
    input = get_node_input(shaderNode, inputName)
    if input == None:
        print('Input', inputName, 'Not found')
    else:
        if data.type == 'float':
            input.default_value = data.data
        elif data.type == 'color3f':
            if type(input.default_value) == float:
                input.default_value = data.data[0]
            else:
                input.default_value = data.data + (1,)
        elif data.type == 'normal3f':
            input.default_value = (0.0, 0.0, 1.0)
        else:
            print('Value Not Set:', data.printUsda())


def set_shader_input_texture(data, mat, inputName, matData, tempDir):
    outputNode = get_output_node(mat)
    shaderNode = get_shader_node(outputNode)
    input = get_node_input(shaderNode, inputName)
    if input == None:
        print('Input', inputName, 'Not found')
    else:
        texName = data.data[data.data.rfind('/')+1:data.data.find('.outputs')]
        texData = matData.getItemOfName(texName)
        if texData != None:
            # Compile the File Path
            filePath = texData.getItemOfName('inputs:file').data.replace('@', '')
            filePath = tempDir + filePath
            # Add an Image Texture Node
            texNode = mat.node_tree.nodes.new('ShaderNodeTexImage')
            texNode.image = bpy.data.images.load(filePath)
            texNode.image.pack()
            if data.type == 'color3f':
                # Connect to the Color Input
                mat.node_tree.links.new(input, texNode.outputs[0])
            elif data.type == 'float':
                # Add and link a Seperate Color Node
                texNode.image.colorspace_settings.name = 'Non-Color'
                sepNode = mat.node_tree.nodes.new('ShaderNodeSeparateRGB')
                mat.node_tree.links.new(sepNode.inputs[0], texNode.outputs[0])
                mat.node_tree.links.new(input, sepNode.outputs[0])
            elif data.type == 'normal3f':
                # Add and link a Normal Map Node
                texNode.image.colorspace_settings.name = 'Non-Color'
                mapNode = mat.node_tree.nodes.new('ShaderNodeNormalMap')
                mat.node_tree.links.new(mapNode.inputs[1], texNode.outputs[0])
                mat.node_tree.links.new(input, mapNode.outputs[0])
            #else:
            #    print('UnHandled Type:', node.type)


def get_uv_map_names(mesh):
    uvs = []
    for item in mesh.items:
        if item.type == 'texCoord2f[]' or item.type == 'float2[]':
            uvs.append(item.name[9:])
    return uvs
