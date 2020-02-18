import bpy
import math
import mathutils

epslon = 0.000001


def deselectBpyObjects():
    bpy.ops.object.select_all(action='DESELECT')


def selectBpyObject(object):
    deselectBpyObjects()
    object.select_set(True)
    setBpyActiveObject(object)


def selectBpyObjects(objects):
    deselectBpyObjects()
    for obj in objects:
        obj.select_set(True)


def setBpyActiveObject(object):
    bpy.context.view_layer.objects.active = object


def duplicateBpyObject(object):
    selectBpyObject(object)
    bpy.ops.object.duplicate()
    return bpy.context.active_object


def parentToBpyArmature(obj, arm):
    deselectBpyObjects()
    obj.select_set(True)
    arm.select_set(True)
    bpy.ops.object.parent_set(type='ARMATURE_NAME')
    deselectBpyObjects()


def duplicateBpySkinnedObject(mesh, armature):
    selectBpyObjects([mesh, armature])
    setBpyActiveObject(armature)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.duplicate()
    for obj in bpy.context.selected_objects:
        if obj.type == 'ARMATURE':
            armature = obj
        else:
            mesh = obj
    return (mesh, armature)


def applyBpyArmatureAnimation(dstArmature, srcArmature, startFrame, endFrame):
    selectBpyObject(dstArmature)
    # Select all the pose bones
    for bone in dstArmature.pose.bones:
            bone.bone.select = True
    bpy.ops.object.mode_set(mode='POSE')
    # Remove all pose bone contraints
    for bone in dstArmature.pose.bones:
        for constraint in bone.constraints:
            bone.constraints.remove(constraint)
    bpy.ops.object.mode_set(mode='EDIT')
    # Remove all non-deforming bones
    for bone in bpy.data.armatures[dstArmature.data.name].edit_bones:
        if bone.use_deform == False:
            bpy.data.armatures[dstArmature.data.name].edit_bones.remove(bone)
    bpy.ops.object.mode_set(mode='POSE')
    # Create copy transform constraints to the ik rig
    for bone in bpy.context.selected_pose_bones:
        bone.rotation_mode = 'QUATERNION'
        copyTransforms = bone.constraints.new('COPY_TRANSFORMS')
        copyTransforms.target = srcArmature
        copyTransforms.subtarget = bone.name
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.nla.bake(
        frame_start = startFrame,
        frame_end = endFrame,
        only_selected = True,
        visual_keying = True,
        clear_constraints = True,
        use_current_action = True,
        bake_types = {'POSE'}
    )


def applyBpyObjectModifers(object):
    if object != None:
        selectBpyObject(object)
        bpy.ops.object.make_single_user()
        bpy.ops.object.convert(target='MESH')


def createBpyEmptyObject(emptyName):
    return bpy.data.objects.new(emptyName, None)


def createBpyMeshObject(meshName, objName):
    mesh = bpy.data.meshes.new(meshName)
    obj = bpy.data.objects.new(objName, mesh)
    return obj


def createBpyArmatureObject(armName, objName):
    arm = bpy.data.armatures.new(armName)
    obj = bpy.data.objects.new(objName, arm)
    return obj

def deleteBpyObject(object):
    selectBpyObject(object)
    bpy.ops.object.delete()


def convertBpyMatrix(matrix):
    matrix = mathutils.Matrix.transposed(matrix)
    return (matrix[0][:], matrix[1][:], matrix[2][:], matrix[3][:])


def convertBpyRootMatrix(matrix, scale):
    scale = mathutils.Matrix.Scale(scale, 4)
    rotation = mathutils.Matrix.Rotation(-math.pi/2.0, 4, 'X')
    return convertBpyMatrix(rotation @ scale @ matrix)


def exportBpyExtents(object, scale = 1.0):
    low = object.bound_box[0][:]
    high = object.bound_box[0][:]
    for v in object.bound_box:
        low = min(low, v[:])
        high = max(high, v[:])
    low = tuple(i*scale for i in low)
    high = tuple(i*scale for i in high)
    return [low, high]


def applyBpySmartProjection(mesh):
    selectBpyObject(mesh)
    bpy.ops.uv.smart_project()


def exportBpyMeshVertexCounts(mesh, material = -1):
    counts = []
    if material == -1:
        counts = [len(poly.vertices) for poly in mesh.polygons]
    else:
        for poly in mesh.polygons:
            if poly.material_index == material:
                counts.append(len(poly.vertices))
    return counts


def exportBpyFaceIndices(mesh, material = -1):
    indices = []
    for poly in mesh.polygons:
        if poly.material_index == material or material == -1:
            indices.append(poly.index)
    return indices


def exportBpyMeshVertices(mesh, material = -1):
    indices = []
    vertices = []
    if material == -1:
        for poly in mesh.polygons:
            indices += [i for i in poly.vertices]
        vertices = [v.co[:] for v in mesh.vertices]
    else:
        map = {}
        for poly in mesh.polygons:
            if poly.material_index == material:
                for i in poly.vertices:
                    if not i in map:
                        map[i] = len(vertices)
                        vertices.append(mesh.vertices[i].co[:])
                    indices.append(map[i])
    return (indices, vertices)


def addValueIndex(valueMap, values, indices, value, repeats = 1):
    if value in valueMap:
        indices += [valueMap[value]] * repeats
    else:
        index = len(values)
        indices += [index] * repeats
        values.append(value)
        valueMap[value] = index


def exportBpyMeshNormals(mesh, material = -1):
    indices = []
    normals = []
    normalMap = {}
    if mesh.has_custom_normals:
        # Calculate and Export Custom Normals
        mesh.calc_normals_split()
        for loop in mesh.loops:
            addValueIndex(normalMap, normals, indices, loop.normal[:])
        mesh.free_normals_split()
        return (indices, normals)
    for poly in mesh.polygons:
        if material == -1 or poly.material_index == material:
            if poly.use_smooth:
                for i in poly.vertices:
                    normal = mesh.vertices[i].normal[:]
                    addValueIndex(normalMap, normals, indices, normal)
            else:
                normal = poly.normal[:]
                vertices = len(poly.vertices)
                addValueIndex(normalMap, normals, indices, normal, vertices)
    return (indices, normals)


def exportBpyMeshUvs(mesh, layer, material = -1):
    indices = []
    uvs = []
    uvMap = {}
    index = 0
    for poly in mesh.polygons:
        if material == -1 or poly.material_index == material:
            for i in range(index, index + len(poly.vertices)):
                uv = layer.data[i].uv[:]
                addValueIndex(uvMap, uvs, indices, uv)
        index += len(poly.vertices)
    return (indices, uvs)


def exportBpyVertexWeights(index, groups):
    indices = []
    weights = []
    for group in groups:
        try:
            weight = group.weight(index)
            if weight > epslon:
                indices.append(group.index)
                weights.append(weight)
        except RuntimeError:
            pass
    return (indices, weights)


def exportBpyMeshIndices(obj, material = -1):
    if material == -1:
        return [i for i in range(0, len(obj.data.vertices))]
    indices = []
    indexSet = set()
    for poly in obj.data.polygons:
        if poly.material_index == material:
            for i in poly.vertices:
                if not i in indexSet:
                    indexSet.add(i)
                    indices.append(i)
    return indices


def exportBpyMeshWeights(obj, material = -1):
    groups = []
    weights = []
    size = 0
    indices = exportBpyMeshIndices(obj, material)
    items = []
    for index in indices:
        item = exportBpyVertexWeights(index, obj.vertex_groups)
        size = max(size, len(item[0]))
        items.append(item)
    for g, w in items:
        groups += g + (size-len(g))*[0]
        weights += w + (size-len(w))*[0.0]
    return (groups, weights, size)


def createBpyCollection(name):
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def deleteBpyCollection(collection):
    if collection != None:
        bpy.data.collections.remove(collection)


def addToBpyCollection(object, collection = None):
    if object != None and collection != None:
        if collection == None:
            collection = bpy.context.scene.collection
        collection.objects.link(object)


def getBpyOrderedCollections():
    def fn(c, out, addme):
        if addme:
            out.append(c)
        for c1 in c.children:
            out.append(c1)
        for c1 in c.children:
            fn(c1, out, False)
    collections = []
    fn(bpy.context.scene.collection, collections, True)
    return collections


def getBpyAreaFromContext(context, areaType):
    area = None
    for a in context['screen'].areas:
        if a.type == areaType:
            area = a
            break
    return area


def setBpyCollectionVisibility(collection, visible):
    if collection != None:
        collections = getBpyOrderedCollections()
        if collection in collections:
            index = collections.index(collection)
            hidden = not visible
            try:
                bpy.ops.object.hide_collection(bpy.context, collection_index=index, toggle=hidden)
            except:
                context = bpy.context.copy()
                context['area'] = getBpyAreaFromContext(context, 'VIEW_3D')
                bpy.ops.object.hide_collection(context, collection_index=index, toggle=hidden)


def exportBpyBoneJoint(bone):
    name = bone.name.replace('.', '_')
    if bone.parent != None:
        return exportBpyBoneJoint(bone.parent) + '/' + name
    return name


def exportBpyJoints(armature):
    return [exportBpyBoneJoint(bone) for bone in armature.data.bones]


def exportBpyBindTransforms(armature):
    transforms = []
    for bone in armature.data.bones:
        matrix = bone.matrix_local
        transforms.append(convertBpyMatrix(matrix))
    return transforms


def exportBpyRestTransforms(armature):
    transforms = []
    for bone in armature.data.bones:
        matrix = bone.matrix_local
        transforms.append(convertBpyMatrix(matrix))
    return transforms
