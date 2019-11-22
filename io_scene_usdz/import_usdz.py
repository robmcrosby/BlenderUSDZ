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
    return {'FINISHED'}


def findUsdz(dirpath):
    files = os.listdir(dirpath)
    for file in files:
        parts = file.split('.')
        if len(parts) > 0 and parts[-1] == 'usdc':
            return dirpath + '/' + file
    return ''


def importData(context, usdData, tempDir, materials, animated):
    if animated:
        if 'startTimeCode' in usdData.properties:
            context.scene.frame_start = usdData['startTimeCode']
        if 'endTimeCode' in usdData.properties:
            context.scene.frame_end = usdData['endTimeCode']
        if 'timeCodesPerSecond' in usdData.properties:
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
    index = 0
    for i, face in enumerate(faces):
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
    return meshes


def importMaterials(data, tempDir):
    materialMap = {}
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
    outputNode = getBpyOutputNode(mat)
    shaderNode = getBpyShaderNode(outputNode)
    input = getBpyNodeInput(shaderNode, inputName)
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
    outputNode = getBpyOutputNode(mat)
    shaderNode = getBpyShaderNode(outputNode)
    input = getBpyNodeInput(shaderNode, inputName)
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
        if input.type == 'RGBA':
            # Connect to the Color Input
            mat.node_tree.links.new(input, texNode.outputs['Color'])
        elif input.type == 'VALUE':
            # Add and link a Seperate Color Node
            texNode.image.colorspace_settings.name = 'Non-Color'
            sepNode = mat.node_tree.nodes.new('ShaderNodeSeparateRGB')
            mat.node_tree.links.new(sepNode.inputs[0], texNode.outputs[0])
            mat.node_tree.links.new(input, sepNode.outputs[0])
        elif input.type == 'VECTOR':
            # Add and link a Normal Map Node
            texNode.image.colorspace_settings.name = 'Non-Color'
            mapNode = mat.node_tree.nodes.new('ShaderNodeNormalMap')
            mat.node_tree.links.new(mapNode.inputs[1], texNode.outputs[0])
            mat.node_tree.links.new(input, mapNode.outputs[0])
