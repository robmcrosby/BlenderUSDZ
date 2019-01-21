import bpy
#from . import object_utils
#from . import material_utils
#from . import file_data
import object_utils
import material_utils
import file_data

#from .object_utils import *
#from .material_utils import *
#from .file_data import FileData, FileItem
from object_utils import *
from material_utils import *
from file_data import FileData, FileItem


class ShaderInput:
    """Shader Input Information"""
    def __init__(self, type, name, default):
        self.type = type
        self.name = name
        self.value = default

    def exportShaderItem(self):
        return FileItem(self.type, self.name, self.value)


class Material:
    """Wraper for Blender Material"""
    def __init__(self, object, index):
        self.object = object
        self.index = index
        self.material = object.mesh.material_slots[index].material
        self.name = self.material.name.replace('.', '_')
        self.outputNode = get_output_node(self.material)
        self.shaderNode = get_shader_node(self.outputNode)
        self.inputs = {
            'diffuseColor':ShaderInput('color3f', 'inputs:diffuseColor', (0.18, 0.18, 0.18)),
            'emissiveColor':ShaderInput('color3f', 'inputs:emissiveColor', (0.0, 0.0, 0.0)),
            'clearcoat':ShaderInput('float', 'inputs:clearcoat', 0.0),
            'clearcoatRoughness':ShaderInput('float', 'inputs:clearcoatRoughness', 0.0),
            'displacement':ShaderInput('float', 'inputs:displacement', 0),
            'ior':ShaderInput('float', 'inputs:ior', 1.5),
            'metallic':ShaderInput('float', 'inputs:metallic', 0.0),
            'normal':ShaderInput('normal3f', 'inputs:normal', (0.0, 0.0, 1.0)),
            'occlusion':ShaderInput('float', 'inputs:occlusion', 0.0),
            'roughness':ShaderInput('float', 'inputs:roughness', 0.0),
            'opacity':ShaderInput('float', 'inputs:opacity', 1.0),
            'specularColor':ShaderInput('color3f', 'inputs:specularColor', (1.0, 1.0, 1.0)),
            'useSpecularWorkflow':ShaderInput('int', 'inputs:useSpecularWorkflow', 0),
        }

    def bakeColorTexture(self):
        input = get_color_input(self.shaderNode)
        if input != None:
            self.inputs['diffuseColor'].value = input.default_value[:3]

    def bakeRoughnessTexture(self):
        input = get_roughness_input(self.shaderNode)
        if input != None:
            self.inputs['roughness'].value = input.default_value

    def bakeMetallicTexture(self):
        input = get_metallic_input(self.shaderNode)
        if input != None:
            value = input.default_value
            self.inputs['metallic'].value = value
            self.inputs['useSpecularWorkflow'].value = 0 if value > 0.0 else 1

    def bakeTextures(self):
        self.bakeColorTexture()
        self.bakeRoughnessTexture()
        self.bakeMetallicTexture()


    def exportPbrShaderItem(self):
        item = FileItem('def Shader', 'pbr')
        item.addItem('uniform token', 'info:id', '"UsdPreviewSurface"')
        for input in self.inputs.values():
            item.append(input.exportShaderItem())
        item.addItem('token', 'outputs:displacement')
        item.addItem('token', 'outputs:surface')
        return item

    def exportMaterialItem(self):
        item = FileItem('def Material', self.name)
        item.addItem('token', 'outputs:displacement.connect', '</Materials/'+self.name+'/pbr.outputs:displacement>')
        item.addItem('token', 'outputs:surface.connect', '</Materials/'+self.name+'/pbr.outputs:surface>')
        item.append(self.exportPbrShaderItem())
        return item


class Object:
    """Wraper for Blender Objects"""
    def __init__(self, object, type = 'EMPTY'):
        self.object = object
        self.mesh = None
        self.materials = []
        self.parent = None
        self.children = []
        self.type = type
        self.name = object.name.replace('.', '_')

    def cleanup(self):
        if self.mesh != None:
            delete_object(self.mesh)
            self.mesh = None

    def createMesh(self):
        if self.mesh == None:
            self.mesh = duplicate_object(self.object)
            apply_object_modifers(self.mesh)

    def getTransform(self, scale):
        if self.parent == None:
            return root_matrix_data(self.object.matrix_world, scale)
        return matrix_data(self.object.matrix_local)

    def getMaterialName(self, material):
        if material < 0 or material >= len(self.materials):
            return ''
        return self.materials[material].name

    def exportMeshUvItems(self, material):
        mesh = self.mesh.data
        items = []
        for layer in mesh.uv_layers:
            indices, uvs = export_mesh_uvs(mesh, layer, material)
            name = layer.name.replace('.', '_')
            items.append(FileItem('int[]', 'primvars:'+name+':indices', indices))
            items.append(FileItem('texCoord2f[]', 'primvars:'+name, uvs))
            items[-1].properties['interpolation'] = '"faceVarying"'
        return items

    def exportMeshItem(self, material = -1):
        mesh = self.mesh.data
        name = self.object.data.name.replace('.', '_')
        if material >= 0:
            name += '_' + self.getMaterialName(material)
        item = FileItem('def Mesh', name)

        extent = object_extents(self.mesh)
        item.addItem('float3[]', 'extent', extent)

        vertexCounts = mesh_vertex_counts(mesh, material)
        item.addItem('int[]', 'faceVertexCounts', vertexCounts)

        indices, points = export_mesh_vertices(mesh, material)
        item.addItem('int[]', 'faceVertexIndices', indices)
        item.addItem('point3f[]', 'points', points)

        indices, normals = export_mesh_normals(mesh, material)
        item.addItem('int[]', 'primvars:normals:indices', indices)
        item.addItem('normal3f[]', 'primvars:normals', normals)
        item.items[-1].properties['interpolation'] = '"faceVarying"'

        item.items += self.exportMeshUvItems(material)
        if material >= 0:
            name = self.getMaterialName(material)
            item.addItem('rel', 'material:binding', '</Materials/'+name+'>')
        item.addItem('uniform token', 'subdivisionScheme', '"none"')
        return item

    def exportMeshItems(self, exportMaterials):
        items = []
        if exportMaterials and len(self.mesh.material_slots) > 0:
            self.materials = []
            for mat in range(0, len(self.mesh.material_slots)):
                self.materials.append(Material(self, mat))
                self.materials[-1].bakeTextures()
                items.append(self.exportMeshItem(mat))
        else:
            items.append(self.exportMeshItem())
        return items

    def exportItem(self, scale, exportMaterials):
        item = FileItem('def Xform', self.name)
        item.addItem('custom matrix4d', 'xformOp:transform', self.getTransform(scale))
        item.addItem('uniform token[]', 'xformOpOrder', ['"xformOp:transform"'])

        # Add Meshes if Mesh Object
        if self.type == 'MESH':
            self.createMesh()
            item.items += self.exportMeshItems(exportMaterials)

        # Add Any Children
        for child in self.children:
            item.append(child.exportItem(scale, exportMaterials))
        return item



class Scene:
    """Container for Objects"""
    def __init__(self):
        self.context = None
        self.objects = []
        self.objMap = {}
        self.bpyObjects = []
        self.bpyActive = None
        self.exportMaterials = False
        self.bakeAO = False
        self.bakeSamples = 8
        self.scale = 1.0
        self.animated = False

    def cleanup(self):
        for obj in self.objects:
            obj.cleanup()
        deselect_objects()
        select_objects(self.bpyObjects)
        set_active_object(self.bpyActive)


    def loadContext(self, context):
        self.context = context
        self.loadObjects(context.selected_objects)

    def loadObjects(self, objects):
        self.bpyObjects = objects
        self.bpyActive = active_object()
        for obj in objects:
            if (obj.type == 'MESH'):
                self.addBpyObject(obj, obj.type)

    def addBpyObject(self, object, type = 'EMPTY'):
        obj = Object(object, type)
        if obj.name in self.objMap:
            obj = self.objMap[obj.name]
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

    def getMaterials(self):
        materials = {}
        for obj in self.objects:
            for mat in obj.materials:
                materials[mat.name] = mat
        return list(materials.values())

    def exportFileData(self):
        data = FileData()
        data.items += self.exportObjectItems()
        if self.exportMaterials:
            data.append(self.exportMaterialsItem())
        return data

    def exportObjectItems(self):
        items = []
        for obj in self.objects:
            items.append(obj.exportItem(self.scale, self.exportMaterials))
        return items

    def exportMaterialsItem(self):
        item = FileItem('def', 'Materials')
        for mat in self.getMaterials():
            item.append(mat.exportMaterialItem())
        return item
