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
                #print(usdData)
                tempDir = usdcFile[:usdcFile.rfind('/')+1]
                importData(context, usdData, tempDir, materials)
            else:
                print('No usdc file found')

            # Cleanup Temp Files
            if tempPath != None:
                shutil.rmtree(tempPath)

    return {'FINISHED'}


def importData(context, usdData, tempDir, materials):
    materials = importMaterials(usdData, tempDir) if materials else {}
    objects = getObjects(usdData)
    for object in objects:
        addObject(context, object, materials)


def addObject(context, data, materials = {}, parent = None):
    meshes = getMeshes(data)
    if len(meshes) > 0:
        # Create A Mesh Object
        obj = create_mesh_object(meshes[0].name, data.name)
        add_to_collection(obj, context.scene.collection)

        # Create any UV maps
        uvs = meshes[0].getAttributesOfTypeStr('texCoord2f[]')
        uvs += meshes[0].getAttributesOfTypeStr('float2[]')
        uvs = [uv.name[9:] for uv in uvs]
        for uv in uvs:
            obj.data.uv_layers.new(name = uv)

        # Add the Geometry
        for mesh in meshes:
            addMesh(obj, mesh, uvs, materials)
        obj.data.update()

        # Set the Parent
        if parent != None:
            obj.parent = parent

        # Apply any Transforms
        matrix = mathutils.Matrix()
        if 'xformOpOrder' in data:
            for opName in data['xformOpOrder'].value:
                if opName == 'xformOp:transform':
                    m = mathutils.Matrix(data[opName].value)
                    m.transpose()
                    matrix = matrix @ m
        if parent == None:
            matrix = matrix @ mathutils.Matrix.Rotation(pi/2.0, 4, 'X')
        obj.matrix_local = matrix

        # Add the Children
        children = getObjects(data)
        for child in children:
            addObject(context, child, materials, obj)


def addMesh(obj, data, uvs, materials):
    #print(data)
    # Get Geometry From Data
    counts = data['faceVertexCounts'].value
    indices = data['faceVertexIndices'].value
    verts = data['points'].value
    normals = None
    if 'primvars:normals:indices' in data:
        normals = data['primvars:normals:indices'].value
    uvMaps = {}
    for uv in uvs:
        uvCoords = data['primvars:'+uv].value
        uvIndices = data['primvars:'+uv+':indices'].value
        uvMaps[uv] = [uvCoords[i] for i in uvIndices]
    # Compile Faces
    faces = []
    smooth = []
    index = 0
    for count in counts:
        faces.append(tuple([indices[index + i] for i in range(count)]))
        if normals != None:
            smooth.append(len(set(normals[index + i] for i in range(count))) > 1)
        else:
            smooth.append(True)
        index += count
    # Assign the Material
    matIndex = 0

    matRel = None
    if 'material:binding' in data:
        matRel = data['material:binding']
    """
    matRel = data.getItemOfName('material:binding')
    if matRel == None:
        geomSubsets = data.getItemsOfType('GeomSubset')
        if len(geomSubsets) > 0:
            matRel = geomSubsets[0].getItemOfName('material:binding')
    """

    if matRel != None and matRel.value != None:
        if matRel.value.name in materials:
            matIndex = len(obj.data.materials)
            obj.data.materials.append(materials[matRel.value.name])

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
        f = bm.faces.new((bm.verts[i + base] for i in face))
        f.smooth = smooth[i]
        f.material_index = matIndex

    # Add the UVs
    for uvName, uvs in uvMaps.items():
        uvIndex = bm.loops.layers.uv[uvName]
        index = 0
        for f in bm.faces[-len(faces):]:
            for i, l in enumerate(f.loops):
                if index+i < len(uvs):
                    l[uvIndex].uv = uvs[index + i]
                else:
                    l[uvIndex].uv = (0.0, 0.0)
            index += len(f.loops)

    # Apply BMesh back to Mesh Object
    bm.to_mesh(obj.data)
    bm.free()


def getObjects(data):
    objects = []
    for child in data.children:
        if child.classType == ClassType.Scope:
            objects += getObjects(child)
        elif child.classType == ClassType.Xform:
            objects.append(child)
    return objects


def getMeshes(data):
    meshes = []
    for child in data.children:
        if child.classType == ClassType.Scope:
            meshes += getObjects(child)
        elif child.classType == ClassType.Mesh:
            meshes.append(child)
    return meshes

def importMaterials(data, tempDir):
    materialMap = {}
    #print(data.printUsda(reduced = True))
    materials = data.getAllMaterials()
    for matData in materials:
        mat = createMaterial(matData, tempDir)
        materialMap[matData.name] = mat
    return materialMap

def createMaterial(data, tempDir):
    mat = bpy.data.materials.new(data.name)
    mat.use_nodes = True

    setMaterialInput(data, mat, tempDir, 'diffuseColor', 'Base Color')
    setMaterialInput(data, mat, tempDir, 'clearcoat', 'Clearcoat')
    setMaterialInput(data, mat, tempDir, 'clearcoatRoughness', 'Clearcoat Roughness')
    #setMaterialInput(data, mat, tempDir, 'emissiveColor', 'Emissive')
    setMaterialInput(data, mat, tempDir, 'ior', 'IOR')
    setMaterialInput(data, mat, tempDir, 'metallic', 'Metallic')
    setMaterialInput(data, mat, tempDir, 'normal', 'Normal')
    #setMaterialInput(data, mat, tempDir, 'occlusion', 'Occlusion')
    setMaterialInput(data, mat, tempDir, 'roughness', 'Roughness')
    setMaterialInput(data, mat, tempDir, 'specularColor', 'Specular')
    return mat

def getSurfaceShaderData(materialData):
    return materialData['outputs:surface'].value.parent

def setMaterialInput(matData, mat, tempDir, valName, inputName):
    shaderData = getSurfaceShaderData(matData)
    inputData = shaderData['inputs:' + valName]
    if inputData != None:
        if inputData.isConnection():
            setShaderInputTexture(inputData, mat, inputName, matData, tempDir)
        else:
            setShaderInputValue(inputData, mat, inputName)

def setShaderInputValue(data, mat, inputName):
    outputNode = get_output_node(mat)
    shaderNode = get_shader_node(outputNode)
    input = get_node_input(shaderNode, inputName)
    if input == None:
        print('Input', inputName, 'Not found')
    else:
        valueType = data.valueTypeToString()
        if valueType == 'float':
            input.default_value = data.value
        elif valueType == 'color3f':
            if type(input.default_value) == float:
                input.default_value = data.value[0]
            else:
                input.default_value = data.value + (1,)
        elif valueType == 'normal3f':
            input.default_value = (0.0, 0.0, 1.0)
        else:
            print('Value Not Set:', data.printUsda())

def setShaderInputTexture(data, mat, inputName, matData, tempDir):
    outputNode = get_output_node(mat)
    shaderNode = get_shader_node(outputNode)
    input = get_node_input(shaderNode, inputName)
    if input == None:
        print('Input', inputName, 'Not found')
    else:
        # Get the Image File Path
        texData = data.value.parent
        filePath = tempDir + texData['inputs:file'].value
        # Add an Image Texture Node
        texNode = mat.node_tree.nodes.new('ShaderNodeTexImage')
        texNode.image = bpy.data.images.load(filePath)
        texNode.image.pack()
        valueType = data.valueTypeToString()
        if valueType == 'color3f':
            # Connect to the Color Input
            mat.node_tree.links.new(input, texNode.outputs[0])
        elif valueType == 'float':
            # Add and link a Seperate Color Node
            texNode.image.colorspace_settings.name = 'Non-Color'
            sepNode = mat.node_tree.nodes.new('ShaderNodeSeparateRGB')
            mat.node_tree.links.new(sepNode.inputs[0], texNode.outputs[0])
            mat.node_tree.links.new(input, sepNode.outputs[0])
        elif valueType == 'normal3f':
            # Add and link a Normal Map Node
            texNode.image.colorspace_settings.name = 'Non-Color'
            mapNode = mat.node_tree.nodes.new('ShaderNodeNormalMap')
            mat.node_tree.links.new(mapNode.inputs[1], texNode.outputs[0])
            mat.node_tree.links.new(input, mapNode.outputs[0])
