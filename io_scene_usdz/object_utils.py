import bpy
import mathutils

pi = 3.1415926

def deselect_objects():
    bpy.ops.object.select_all(action='DESELECT')

def select_object(object):
    deselect_objects()
    object.select_set(True)

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


def object_extents(object):
    low = object.bound_box[0][:]
    high = object.bound_box[0][:]
    for v in object.bound_box:
        low = min(low, v[:])
        high = max(high, v[:])
    return [low, high]

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
