import bpy
import mathutils
import file_data
from file_data import FileData, FileItem

pi = 3.1415926


def matrix_data(matrix):
    matrix = mathutils.Matrix.transposed(matrix)
    return (matrix[0][:], matrix[1][:], matrix[2][:], matrix[3][:])

def root_matrix_data(matrix, scale):
    scale = mathutils.Matrix.Scale(scale, 4)
    rotation = mathutils.Matrix.Rotation(-pi/2.0, 4, 'X')
    return matrix_data(rotation @ scale @ matrix)



class Object:
    """Wraper for Blender Objects"""
    def __init__(self, object, type = 'EMPTY'):
        self.object = object
        self.parent = None
        self.children = []
        self.type = type
        self.name = object.name.replace('.', '_')

    def getTransform(self, scale):
        if self.parent == None:
            return root_matrix_data(self.object.matrix_world, scale)
        return matrix_data(self.object.matrix_local)

    def exportMeshItems(self, scale):
        item = FileItem('def Xform', self.name)
        item.addItem('custom matrix4d', 'xformOp:transform', self.getTransform(scale))
        item.addItem('uniform token[]', 'xformOpOrder', ['"xformOp:transform"'])

        # Add Meshes if Mesh Object


        # Add Any Children
        for child in self.children:
            item.items += child.exportMeshItems(scale)
        return [item]



class Scene:
    """Container for Objects"""
    def __init__(self):
        self.context = None
        self.objects = []
        self.objMap = {}
        self.exportMaterials = False
        self.bakeAO = False
        self.bakeSamples = 8
        self.scale = 1.0
        self.animated = False

    def loadContext(self, context):
        self.context = context
        self.loadObjects(context.selected_objects)

    def loadObjects(self, objects):
        for obj in objects:
            if (obj.type == 'MESH'):
                self.addBpyObject(obj, obj.type)

    def addBpyObject(self, object, type = 'EMPTY'):
        obj = Object(object, type)
        if obj.name in self.objMap:
            obj = self.map[obj.name]
            if type != 'EMPTY':
                obj.type = type
        elif object.parent != None:
            obj.parent = self.addBpyObject(object.parent)
            obj.parent.children.append(obj)
            self.objMap[obj.name] = obj
        else:
            self.objects.append(obj)
            self.objMap[obj.name] = obj
        return obj

    def exportFileData(self):
        data = FileData()
        data.items += self.exportObjectItems()
        return data

    def exportObjectItems(self):
        items = []
        for obj in self.objects:
            items += obj.exportMeshItems(self.scale)
        return items
