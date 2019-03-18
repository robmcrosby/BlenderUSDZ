import bpy
import mathutils

pi = 3.1415926
epslon = 0.000001

def deselect_objects():
    bpy.ops.object.select_all(action='DESELECT')

def select_object(object):
    deselect_objects()
    object.select_set(True)
    set_active_object(object)

def select_objects(objects):
    deselect_objects()
    for obj in objects:
        obj.select_set(True)

def active_object():
    return bpy.context.view_layer.objects.active

def set_active_object(object):
    bpy.context.view_layer.objects.active = object

def duplicate_object(object):
    select_object(object)
    bpy.ops.object.duplicate()
    return bpy.context.active_object

def duplicate_skinned_object(mesh, armature):
    select_objects([mesh, armature])
    set_active_object(armature)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.duplicate()
    for obj in bpy.context.selected_objects:
        if obj.type == 'ARMATURE':
            armature = obj
        else:
            mesh = obj
    return (mesh, armature)

def convert_to_fk(fkArmature, ikArmature, start, end):
    select_object(fkArmature)
    # Select all the pose bones
    for bone in fkArmature.pose.bones:
            bone.bone.select = True
    bpy.ops.object.mode_set(mode='POSE')
    # Remove all pose bone contraints
    for bone in fkArmature.pose.bones:
        for constraint in bone.constraints:
            bone.constraints.remove(constraint)
    bpy.ops.object.mode_set(mode='EDIT')
    # Remove all non-deforming bones
    for bone in bpy.data.armatures[fkArmature.data.name].edit_bones:
        if bone.use_deform == False:
            bpy.data.armatures[fkArmature.data.name].edit_bones.remove(bone)
    bpy.ops.object.mode_set(mode='POSE')
    # Create copy transform constraints to the ik rig
    for bone in bpy.context.selected_pose_bones:
        bone.rotation_mode = 'QUATERNION'
        copyTransforms = bone.constraints.new('COPY_TRANSFORMS')
        copyTransforms.target = ikArmature
        copyTransforms.subtarget = bone.name
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.nla.bake(frame_start=start, frame_end=end, only_selected=True, visual_keying=True, clear_constraints=True, use_current_action=True, bake_types={'POSE'})

def apply_object_modifers(object):
    if object != None:
        select_object(object)
        bpy.ops.object.make_single_user()
        bpy.ops.object.convert(target='MESH')

def delete_object(object):
    select_object(object)
    bpy.ops.object.delete()

def matrix_data(matrix):
    matrix = mathutils.Matrix.transposed(matrix)
    return (matrix[0][:], matrix[1][:], matrix[2][:], matrix[3][:])

def root_matrix_data(matrix, scale):
    scale = mathutils.Matrix.Scale(scale, 4)
    rotation = mathutils.Matrix.Rotation(-pi/2.0, 4, 'X')
    return matrix_data(rotation @ scale @ matrix)


def object_extents(object, scale = 1.0):
    low = object.bound_box[0][:]
    high = object.bound_box[0][:]
    for v in object.bound_box:
        low = min(low, v[:])
        high = max(high, v[:])
    low = tuple(i*scale for i in low)
    high = tuple(i*scale for i in high)
    return [low, high]

def uv_smart_project(mesh):
    select_object(mesh)
    bpy.ops.uv.smart_project()

def mesh_vertex_counts(mesh, material = -1):
    counts = []
    if material == -1:
        counts = [len(poly.vertices) for poly in mesh.polygons]
    else:
        for poly in mesh.polygons:
            if poly.material_index == material:
                counts.append(len(poly.vertices))
    return counts

def export_mesh_vertices(mesh, material = -1):
    indices = []
    points = []
    if material == -1:
        for poly in mesh.polygons:
            indices += [i for i in poly.vertices]
        points = [v.co[:] for v in mesh.vertices]
    else:
        map = {}
        for poly in mesh.polygons:
            if poly.material_index == material:
                for i in poly.vertices:
                    if not i in map:
                        map[i] = len(points)
                        points.append(mesh.vertices[i].co[:])
                    indices.append(map[i])
    return (indices, points)

def export_mesh_normals(mesh, material = -1):
    indices = []
    normals = []
    for poly in mesh.polygons:
        if material == -1 or poly.material_index == material:
            if poly.use_smooth:
                for i in poly.vertices:
                    normal = mesh.vertices[i].normal[:]
                    if normal in normals:
                        indices += [normals.index(normal)]
                    else:
                        indices += [len(normals)]
                        normals.append(normal)
            else:
                normal = poly.normal[:]
                if normal in normals:
                    indices += [normals.index(normal)] * len(poly.vertices)
                else:
                    indices += [len(normals)] * len(poly.vertices)
                    normals.append(normal)
    return (indices, normals)

def export_mesh_uvs(mesh, layer, material = -1):
    indices = []
    uvs = []
    index = 0
    for poly in mesh.polygons:
        if material == -1 or poly.material_index == material:
            for i in range(index, index + len(poly.vertices)):
                uv = layer.data[i].uv[:]
                if uv in uvs:
                    indices += [uvs.index(uv)]
                else:
                    indices += [len(uvs)]
                    uvs.append(uv)
        index += len(poly.vertices)
    return (indices, uvs)

def get_weights(index, groups):
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

def get_mesh_indices(obj, material = -1):
    if material == -1:
        return [i for i in range(0, len(obj.data.vertices))]
    indices = []
    for poly in obj.data.polygons:
        if poly.material_index == material:
            for i in poly.vertices:
                if not i in indices:
                    indices.append(i)
    return indices

def export_mesh_weights(obj, material = -1):
    groups = []
    weights = []
    size = 0
    indices = get_mesh_indices(obj, material)
    items = []
    for index in indices:
        item = get_weights(index, obj.vertex_groups)
        size = max(size, len(item[0]))
        items.append(item)
    for g, w in items:
        groups += g + (size-len(g))*[0]
        weights += w + (size-len(w))*[0.0]
    return (groups, weights, size)

def create_collection(name):
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection

def delete_collection(collection):
    if collection != None:
        bpy.data.collections.remove(collection)

def add_to_collection(object, collection):
    if object != None and collection != None:
        collection.objects.link(object)

def get_joint_token(bone):
    name = bone.name.replace('.', '_')
    if bone.parent != None:
        return get_joint_token(bone.parent) + '/' + name
    return name

def get_joint_tokens(armature):
    return ['"'+get_joint_token(bone)+'"' for bone in armature.data.bones]

def get_bind_transforms(armature):
    transforms = []
    for bone in armature.data.bones:
        matrix = bone.matrix_local
        transforms.append(matrix_data(matrix))
    return transforms

def get_rest_transforms(armature):
    transforms = []
    for bone in armature.data.bones:
        matrix = bone.matrix_local
        transforms.append(matrix_data(matrix))
    return transforms
