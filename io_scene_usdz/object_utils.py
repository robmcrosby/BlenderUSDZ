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

def get_max_weights(obj, material = -1):
    size = 0
    for poly in obj.data.polygons:
        if material == -1 or poly.material_index == material:
            for index in poly.vertices:
                count = 0
                for group in obj.vertex_groups:
                    try:
                        weight = group.weight(index)
                        if weight > epslon:
                            count += 1
                    except RuntimeError:
                        pass
                size = max(size, count)
    return size

def get_vertex_weights(index, groups, size):
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
    indices = indices[:size]
    weights = weights[:size]
    while len(indices) < size:
        indices.append(0)
        weights.append(0.0)
    return (indices, weights)

def get_poly_weights(poly, groups, size):
    indices = []
    weights = []
    for index in poly.vertices:
        i, w = get_vertex_weights(index, groups, size)
        indices += i
        weights += w
    return (indices, weights)

def export_mesh_weights(obj, material = -1):
    indices = []
    weights = []
    size = 0
    if len(obj.vertex_groups) > 0:
        size = get_max_weights(obj, material)
        for poly in obj.data.polygons:
            if material == -1 or poly.material_index == material:
                i, w = get_poly_weights(poly, obj.vertex_groups, size)
                indices += i
                weights += w
    return (indices, weights, size)

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
