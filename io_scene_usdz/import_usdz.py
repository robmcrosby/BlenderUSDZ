import bpy
import os
import subprocess
import tempfile
import shutil
import zipfile
import bmesh
import mathutils
import math

from io_scene_usdz.scene_data import *
from io_scene_usdz.object_utils import *
from io_scene_usdz.material_utils import *
from io_scene_usdz.crate_file import *


def import_usdz(context, filepath = '', materials = True, animations = True):
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
            usdcFile = findUsdz(tempPath)
            if usdcFile != '':
                file = open(usdcFile, 'rb')
                crate = CrateFile(file)
                usdData = crate.readUsd()
                file.close()
                print(usdData.toString(debug = True))
                tempDir = usdcFile[:usdcFile.rfind('/')+1]
                importData(context, usdData, tempDir, materials, animations)
            else:
                print('No usdc file found')
            # Cleanup Temp Files
            if tempPath != None:
                shutil.rmtree(tempPath)
    elif fileType == 'usdc':
        usdcFile = filepath
        file = open(usdcFile, 'rb')
        crate = CrateFile(file)
        usdData = crate.readUsd()
        file.close()
        print(usdData.toString(debug = True))
        tempDir = usdcFile[:usdcFile.rfind('/')+1]
        importData(context, usdData, tempDir, materials, animations)
    return {'FINISHED'}


def findUsdz(dirpath):
    files = os.listdir(dirpath)
    dirs = []
    for file in files:
        parts = file.split('.')
        filepath = dirpath + '/' + file
        if os.path.isdir(filepath):
            dirs.append(filepath)
        elif len(parts) > 0 and parts[-1] == 'usdc':
            return filepath
    for dir in dirs:
        file = findUsdz(dir)
        if file != '':
            return file
    return ''


def importData(context, usdData, tempDir, materials, animated):
    if animated:
        if 'startTimeCode' in usdData.metadata:
            context.scene.frame_start = usdData['startTimeCode']
        if 'endTimeCode' in usdData.metadata:
            context.scene.frame_end = usdData['endTimeCode']
        if 'timeCodesPerSecond' in usdData.metadata:
            context.scene.render.fps = usdData['timeCodesPerSecond']
    materials = importMaterials(usdData, tempDir) if materials else {}
    objects = getObjects(usdData)
    for object in objects:
        addObject(context, object, materials, animated = animated)


def getOpMatrix(data, opName):
    invert = '!invert!' in opName
    opName = opName.replace('!invert!', '')
    data = data[opName]
    matrix = mathutils.Matrix()
    if data != None:
        value = data.value if data.value != None else data.frames[0][1]
        #print(opName, value)
        if opName in ('xformOp:transform', 'xformOp:transform:transforms'):
            matrix = mathutils.Matrix(value)
            matrix.transpose()
        elif opName == 'xformOp:rotateXYZ':
            rotX = mathutils.Matrix.Rotation(math.radians(value[0]), 4, 'X')
            rotY = mathutils.Matrix.Rotation(math.radians(value[1]), 4, 'Y')
            rotZ = mathutils.Matrix.Rotation(math.radians(value[2]), 4, 'Z')
            matrix = rotZ @ rotY @ rotX
        elif opName in ('xformOp:translate', 'xformOp:translate:pivot'):
            matrix = mathutils.Matrix.Translation(value)
        elif opName == 'xformOp:scale':
            mathutils.Matrix.Diagonal(value + (1.0,))
        else:
            print('Unused Op:', opName)
    if invert:
        print('Invert')
        matrix.invert()
    return matrix


def getFrameMatrix(opName, values, frame):
    invert = '!invert!' in opName
    opName = opName.replace('!invert!', '')
    matrix = mathutils.Matrix()
    if opName in ('xformOp:transform', 'xformOp:transform:transforms'):
        if type(values) is dict:
            if frame in values:
                matrix = mathutils.Matrix(values[frame])
                matrix.transpose()
        else:
            matrix = mathutils.Matrix(values)
            matrix.transpose()
    return matrix


def applyRidgidTransforms(data, obj):
    matrix = mathutils.Matrix()
    if 'xformOpOrder' in data:
        for opName in reversed(data['xformOpOrder'].value):
            matrix = getOpMatrix(data, opName) @ matrix
    if obj.parent == None:
        matrix = matrix @ mathutils.Matrix.Rotation(math.pi/2.0, 4, 'X')
    obj.matrix_local = matrix


def applyRidgidAnimation(context, data, obj):
    keyFrames = set()
    keyValues = []
    if 'xformOpOrder' in data:
        for opName in reversed(data['xformOpOrder'].value):
            keyData = data[opName]
            if keyData != None:
                if keyData.frames != None:
                    values = {}
                    for frame, value in keyData.frames:
                        keyFrames.add(frame)
                        values[frame] = value
                    keyValues.append((opName, values))
                elif keyData.value != None:
                    keyValues.append((opName, keyData.value))
    if len(keyFrames) > 0:
        selectBpyObject(obj)
        for frame in keyFrames:
            context.scene.frame_set(frame)
            matrix = mathutils.Matrix()
            for opName, values in keyValues:
                matrix = getFrameMatrix(opName, values, frame) @ matrix
            if obj.parent == None:
                matrix = matrix @ mathutils.Matrix.Rotation(math.pi/2.0, 4, 'X')
            obj.matrix_local = matrix
            bpy.ops.anim.keyframe_insert_menu(type='LocRotScale')
        deselectBpyObjects()
    else:
        applyRidgidTransforms(data, obj)
    """
    selectBpyObject(obj)
    for frame in range(context.scene.frame_start, context.scene.frame_end+1):
        context.scene.frame_set(frame)
        matrix = mathutils.Matrix()
        if 'xformOpOrder' in data:
            for opName in reversed(data['xformOpOrder'].value):
                matrix = getOpMatrixFrame(data, opName, frame) @ matrix
        if obj.parent == None:
            matrix = matrix @ mathutils.Matrix.Rotation(math.pi/2.0, 4, 'X')
        obj.matrix_local = matrix
        bpy.ops.anim.keyframe_insert_menu(type='LocRotScale')
    deselectBpyObjects()
    """

    """
    transforms = data['xformOp:transform:transforms']
    if transforms != None:
        selectBpyObject(obj)
        for frame, matrix in transforms.frames:
            context.scene.frame_set(frame)
            matrix = mathutils.Matrix(matrix)
            matrix.transpose()
            if obj.parent == None:
                matrix = matrix @ mathutils.Matrix.Rotation(math.pi/2.0, 4, 'X')
            obj.matrix_local = matrix
            bpy.ops.anim.keyframe_insert_menu(type='LocRotScale')
        context.scene.frame_set(context.scene.frame_start)
        deselectBpyObjects()
    else:
        applyRidgidTransforms(data, obj)
    """


def addBone(arm, joint, pose):
    stack = joint.split('/')
    bone = arm.data.edit_bones.new(stack[-1])
    bone.head = (0.0, 0.0, 0.0)
    bone.tail = (0.0, 1.0, 0.0)
    matrix = mathutils.Matrix(pose)
    matrix.transpose()
    bone.transform(matrix)
    if len(stack) > 1:
        bone.parent = arm.data.edit_bones[stack[-2]]


def addBones(arm, skeleton):
    joints = skeleton['joints'].value
    restPose = skeleton['restTransforms'].value
    selectBpyObject(arm)
    bpy.ops.object.mode_set(mode='EDIT',toggle=True)
    for joint, pose in zip(joints, restPose):
        addBone(arm, joint, pose)
    bpy.ops.object.mode_set(mode='OBJECT',toggle=True)
    deselectBpyObjects()


def addArmatureAnimation(arm, animation):
    joints = animation['joints'].value
    locations = animation['translations'].frames
    rotations = animation['rotations'].frames
    scales = animation['scales'].frames
    selectBpyObject(arm)
    bpy.ops.object.mode_set(mode='POSE',toggle=True)
    for i, joint in enumerate(joints):
        joint = joint.split('/')[-1]
        bone = arm.pose.bones[joint]
        head = arm.data.bones[joint].head
        for frame, location in locations:
            #bone.location = mathutils.Vector(location[i]) - head
            bone.keyframe_insert(data_path = 'location', frame = frame, group = animation.name)
        for frame, rotation in rotations:
            bone.rotation_quaternion = rotation[i][3:] + rotation[i][:3]
            bone.keyframe_insert(data_path = 'rotation_quaternion', frame = frame, group = animation.name)
        for frame, scale in scales:
            bone.scale = scale[i]
            bone.keyframe_insert(data_path = 'scale', frame = frame, group = animation.name)
    bpy.ops.object.mode_set(mode='OBJECT',toggle=True)
    deselectBpyObjects()


def addArmature(context, obj, data):
    skeleton = data.getChildOfType(ClassType.Skeleton)
    if skeleton != None:
        arm = createBpyArmatureObject(skeleton.name, skeleton.name)
        addToBpyCollection(arm, context.scene.collection)
        addBones(arm, skeleton)
        parentToBpyArmature(obj, arm)
        return arm
    return None


def addObject(context, data, materials = {}, parent = None, animated = False):
    obj = None
    arm = None
    meshes = getMeshes(data)
    if len(meshes) == 0:
        # Create An Empty Object
        obj = createBpyEmptyObject(data.name)
        # Add to the Default Collection
        addToBpyCollection(obj, context.scene.collection)
    else:
        # Create A Mesh Object
        obj = createBpyMeshObject(meshes[0].name, data.name)
        # Add to the Default Collection
        addToBpyCollection(obj, context.scene.collection)
        # Create the Armature if in data
        arm = addArmature(context, obj, data)
        # Create any UV maps
        uvs = meshes[0].getAttributesOfTypeStr('texCoord2f[]')
        uvs += meshes[0].getAttributesOfTypeStr('float2[]')
        uvs = [uv.name[9:] for uv in uvs]
        for uv in uvs:
            obj.data.uv_layers.new(name = uv)
        # Add the Geometry
        for mesh in meshes:
            addMesh(obj, mesh, uvs, materials)
            applyBoneWeights(obj, mesh)
        obj.data.update()
    # Set the Parent
    if parent != None:
        obj.parent = parent
    if arm == None:
        # Apply Object Transforms
        if animated:
            applyRidgidAnimation(context, data, obj)
        else:
            applyRidgidTransforms(data, obj)
    elif animated:
        # Apply Armature Animation
        animation = data.getChildOfType(ClassType.SkelAnimation)
        if animation != None:
            addArmatureAnimation(arm, animation)
    # Add the Children
    children = getObjects(data)
    for child in children:
        addObject(context, child, materials, obj, animated)


def addMaterial(obj, rel, materials):
    matName = rel.value.name
    if matName in materials:
        mat = materials[matName]
        if not mat.name in obj.data.materials:
            obj.data.materials.append(mat)
        return obj.data.materials.find(mat.name)
    return 0


def addMesh(obj, data, uvs, materials):
    # Get Geometry From Data
    counts = data['faceVertexCounts'].value
    indices = data['faceVertexIndices'].value
    verts = data['points'].value
    normals = None
    if 'primvars:normals:indices' in data:
        normals = data['primvars:normals:indices'].value
    uvMaps = {}
    for uv in uvs:
        uvPrim = 'primvars:'+uv
        if uvPrim in data and uvPrim+':indices' in data:
            uvCoords = data[uvPrim].value
            uvIndices = data[uvPrim+':indices'].value
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
    if 'material:binding' in data:
        matIndex = addMaterial(obj, data['material:binding'], materials)
    # Get Material Sub Sets
    matSubsets = []
    for geomSubset in data.getChildrenOfType(ClassType.GeomSubset):
        type = geomSubset['familyName']
        if type != None and type.value == 'materialBind':
            rel = geomSubset['material:binding']
            indices = geomSubset['indices']
            if rel != None and indices != None:
                index = addMaterial(obj, rel, materials)
                matSubsets.append((index, indices.value))
    # Create BMesh from Mesh Object
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    # Add the Vertices
    vBase = len(bm.verts)
    fBase = len(bm.faces)
    for vert in verts:
        bm.verts.new(vert)
    bm.verts.ensure_lookup_table()
    # Add the Faces
    ordered = set()
    for i, face in enumerate(faces):
        o = tuple(sorted(face))
        if not o in ordered:
            ordered.add(o)
            f = bm.faces.new((bm.verts[i + vBase] for i in face))
            f.smooth = smooth[i]
            f.material_index = matIndex
    # Assign Aditional Materials
    bm.faces.ensure_lookup_table()
    for matIndex, indices in matSubsets:
        for i in indices:
            fIndex = i + fBase
            if fIndex < len(bm.faces):
                bm.faces[fIndex].material_index = matIndex
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


def applyBoneWeights(obj, data):
    indices = data['primvars:skel:jointIndices']
    weights = data['primvars:skel:jointWeights']
    if indices != None and weights != None:
        elementSize = weights['elementSize']
        base = len(obj.data.vertices) - int(len(indices.value)/elementSize)
        for i, weight in enumerate(zip(indices.value, weights.value)):
            bone, weight = weight
            if weight > 0.0:
                index = base + i//elementSize
                obj.vertex_groups[bone].add([index], weight, 'REPLACE')


def getObjects(data):
    objects = []
    for child in data.children:
        if child.classType == ClassType.Scope:
            objects += getObjects(child)
        elif child.classType in (ClassType.Xform, ClassType.SkelRoot):
            objects.append(child)
        elif child.classType == ClassType.Mesh and 'xformOpOrder' in child:
            objects.append(child)
    return objects


def getMeshes(data):
    if data.classType == ClassType.Mesh:
        return [data]
    meshes = []
    for child in data.children:
        if child.classType == ClassType.Mesh and not 'xformOpOrder' in child:
            meshes.append(child)
        elif child.classType == ClassType.Scope:
            meshes += getMeshes(child)
    return meshes


def importMaterials(data, tempDir):
    materialMap = {}
    materials = data.getAllMaterials()
    for matData in materials:
        mat = createMaterial(matData, tempDir)
        materialMap[matData.name] = mat
    return materialMap


def createMaterial(usdMat, tempDir):
    mat = bpy.data.materials.new(usdMat.name)
    mat.use_nodes = True
    data = {'usdMat':usdMat, 'tempDir':tempDir, 'material':mat}
    data['textureNodes'] = {}
    data['uvMapNodes'] = {}
    data['outputNode'] = getBpyOutputNode(mat)
    data['shaderNode'] = getBpyShaderNode(data['outputNode'])
    setMaterialInput(data, 'diffuseColor', 'Base Color')
    setMaterialInput(data, 'metallic', 'Metallic')
    setMaterialInput(data, 'specularColor', 'Specular')
    setMaterialInput(data, 'roughness', 'Roughness')
    setMaterialInput(data, 'clearcoat', 'Clearcoat')
    setMaterialInput(data, 'clearcoatRoughness', 'Clearcoat Roughness')
    setMaterialInput(data, 'emissiveColor', 'Emission')
    setMaterialInput(data, 'ior', 'IOR')
    setMaterialInput(data, 'opacity', 'Alpha')
    setMaterialInput(data, 'normal', 'Normal')
    #setMaterialInput(data, 'occlusion', 'Occlusion')
    # Setup Transparent Materials
    if 'Alpha' in data['shaderNode'].inputs:
        input = data['shaderNode'].inputs['Alpha']
        if input.is_linked or input.default_value < 1.0:
             mat.blend_method = 'CLIP'
             usdShader = getUsdSurfaceShader(usdMat)
             if 'inputs:opacityThreshold' in usdShader:
                 alphaThreshold = usdShader['inputs:opacityThreshold'].value
                 mat.alpha_threshold = alphaThreshold
    return mat


def getUsdSurfaceShader(usdMat):
    if not 'outputs:surface' in usdMat:
        print('outputs:surface not found in shader', usdMat.name)
        return None
    return usdMat['outputs:surface'].value.parent


def getInputData(usdMat, inputName):
    usdShader = getUsdSurfaceShader(usdMat)
    inputName = 'inputs:' + inputName
    if inputName in usdShader:
        return usdShader[inputName]
    return None


def setMaterialInput(data, valName, inputName):
    inputData = getInputData(data['usdMat'], valName)
    if inputData != None:
        if inputData.isConnection():
            setShaderInputTexture(data, inputData, inputName)
        else:
            setShaderInputValue(data, inputData, inputName)


def setShaderInputValue(data, inputData, inputName):
    input = getBpyNodeInput(data['shaderNode'], inputName)
    if input != None:
        valueType = inputData.valueTypeToString()
        if valueType == 'float':
            input.default_value = inputData.value
        elif valueType == 'color3f':
            if type(input.default_value) == float:
                input.default_value = inputData.value[0]
            else:
                input.default_value = inputData.value + (1,)
        elif valueType == 'normal3f':
            input.default_value = (0.0, 0.0, 1.0)
        else:
            print('Value Not Set:', inputData)


def getTextureMappingNode(data, usdTexture):
    stData = usdTexture['inputs:st'].value.parent
    uvMap = stData['inputs:varname'].value
    if not type(uvMap) is str:
        uvMap = uvMap.value
    if uvMap in data['uvMapNodes']:
        return data['uvMapNodes'][uvMap]
    posY = data['shaderNode'].location.y - len(data['uvMapNodes']) * 200.0
    mapNode = data['material'].node_tree.nodes.new('ShaderNodeUVMap')
    mapNode.location.x = -850.0
    mapNode.location.y = posY
    mapNode.uv_map = uvMap
    data['uvMapNodes'][uvMap] = mapNode
    return mapNode


def getImageTextureNode(data, usdTexture):
    if usdTexture.name in data['textureNodes']:
        return data['textureNodes'][usdTexture.name]
    # Get the Image File Path
    filePath = data['tempDir'] + usdTexture['inputs:file'].value
    posY = data['shaderNode'].location.y - len(data['textureNodes']) * 300.0
    # Add an Image Texture Node
    texNode = data['material'].node_tree.nodes.new('ShaderNodeTexImage')
    texNode.location.x = -600.0
    texNode.location.y = posY
    texNode.image = bpy.data.images.load(filePath)
    texNode.image.pack()
    mapNode = getTextureMappingNode(data, usdTexture)
    data['material'].node_tree.links.new(texNode.inputs[0], mapNode.outputs[0])
    data['textureNodes'][usdTexture.name] = texNode
    return texNode


def connectTextureToValueInput(data, texNode, input):
    texNode.image.colorspace_settings.name = 'Non-Color'
    # Add a Seperate Color Node
    sepNode = data['material'].node_tree.nodes.new('ShaderNodeSeparateRGB')
    sepNode.location.y = texNode.location.y
    sepNode.location.x = -250.0
    # Link in new Node
    data['material'].node_tree.links.new(sepNode.inputs[0], texNode.outputs[0])
    data['material'].node_tree.links.new(input, sepNode.outputs[0])


def connectTextureToNormalInput(data, texNode, input):
    texNode.image.colorspace_settings.name = 'Non-Color'
    # Add a Normal Map Node
    mapNode = data['material'].node_tree.nodes.new('ShaderNodeNormalMap')
    mapNode.location.y = texNode.location.y
    mapNode.location.x = -250.0
    # Link in new Node
    data['material'].node_tree.links.new(mapNode.inputs[1], texNode.outputs[0])
    data['material'].node_tree.links.new(input, mapNode.outputs[0])


def setShaderInputTexture(data, inputData, inputName):
    input = getBpyNodeInput(data['shaderNode'], inputName)
    if input != None:
        texNode = getImageTextureNode(data, inputData.value.parent)
        mat = data['material']
        if input.type == 'RGBA':
            # Connect to the Color Input
            mat.node_tree.links.new(input, texNode.outputs['Color'])
        elif input.type == 'VALUE':
            connectTextureToValueInput(data, texNode, input)
        elif input.type == 'VECTOR':
            connectTextureToNormalInput(data, texNode, input)
