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
        self.image = None
        self.uvMap = None

    def exportShaderInputItem(self, material):
        if self.image != None and self.uvMap != None:
            path = '</Materials/'+material+'/'+self.name+'_map.outputs:rgb>'
            if self.type == 'float':
                path = '</Materials/'+material+'/'+self.name+'_map.outputs:r>'
            return FileItem(self.type, 'inputs:'+self.name+'.connect', path)
        return FileItem(self.type, 'inputs:'+self.name, self.value)

    def exportShaderItem(self, material):
        if self.image != None and self.uvMap != None:
            v = self.value
            default = (v, v, v, 1.0) if self.type == 'float' else v+(1.0,)
            path = '</Materials/'+material+'/primvar_'+self.uvMap+'.outputs:result>'
            item = FileItem('def Shader', self.name+'_map')
            item.addItem('uniform token', 'info:id', '"UsdUVTexture"')
            item.addItem('float4', 'inputs:default', default)
            item.addItem('asset', 'inputs:file', '@'+self.image+'@')
            item.addItem('float2', 'inputs:st.connect', path)
            item.addItem('token', 'inputs:wrapS', '"repeat"')
            item.addItem('token', 'inputs:wrapT', '"repeat"')
            item.addItem('float3', 'outputs:rgb')
            return item
        return None


class Material:
    """Wraper for Blender Material"""
    def __init__(self, material, exportPath):
        self.material = material
        self.exportPath = exportPath
        self.name = get_material_name(material)
        self.outputNode = get_output_node(material)
        self.shaderNode = get_shader_node(self.outputNode)
        self.inputs = {
            'diffuseColor':ShaderInput('color3f', 'diffuseColor', (0.18, 0.18, 0.18)),
            'emissiveColor':ShaderInput('color3f', 'emissiveColor', (0.0, 0.0, 0.0)),
            'clearcoat':ShaderInput('float', 'clearcoat', 0.0),
            'clearcoatRoughness':ShaderInput('float', 'clearcoatRoughness', 0.0),
            'displacement':ShaderInput('float', 'displacement', 0),
            'ior':ShaderInput('float', 'ior', 1.5),
            'metallic':ShaderInput('float', 'metallic', 0.0),
            'normal':ShaderInput('normal3f', 'normal', (0.0, 0.0, 1.0)),
            'occlusion':ShaderInput('float', 'occlusion', 0.0),
            'roughness':ShaderInput('float', 'roughness', 0.0),
            'opacity':ShaderInput('float', 'opacity', 1.0),
            'specularColor':ShaderInput('color3f', 'specularColor', (1.0, 1.0, 1.0)),
            'useSpecularWorkflow':ShaderInput('int', 'useSpecularWorkflow', 0),
        }
        self.bakeUVMap = ''
        self.bakeImageNode = None
        self.bakeUVMapNode = None
        self.bakeWidth = 1024
        self.bakeHeight = 1024
        self.activeNode = None

    def setupBakeNodes(self, mesh):
        nodes = self.material.node_tree.nodes
        self.activeNode = nodes.active
        input = get_color_input(self.shaderNode)
        self.bakeUVMap = get_input_uv_map(input, mesh)
        if self.bakeImageNode == None:
            self.bakeImageNode = nodes.new('ShaderNodeTexImage')
            nodes.active = self.bakeImageNode
        if self.bakeUVMapNode == None:
            self.bakeUVMapNode = nodes.new('ShaderNodeUVMap')
            self.bakeUVMapNode.uv_map = self.bakeUVMap
        links = self.material.node_tree.links
        links.new(self.bakeImageNode.inputs[0], self.bakeUVMapNode.outputs[0])

    def cleanupBakeNodes(self):
        nodes = self.material.node_tree.nodes
        nodes.active = self.activeNode
        if self.bakeImageNode != None:
            nodes.remove(self.bakeImageNode)
            self.bakeImageNode = None
        if self.bakeUVMapNode != None:
            nodes.remove(self.bakeUVMapNode)
            self.bakeUVMapNode = None

    def bakeToFile(self, type, file):
        images = bpy.data.images
        bakeImage = images.new('BakeImage', self.bakeWidth, self.bakeHeight)
        bakeImage.file_format = 'PNG'
        bakeImage.filepath = file
        self.bakeImageNode.image = bakeImage
        bpy.ops.object.bake(type=type, use_clear=True)
        bakeImage.save()
        self.bakeImageNode.image = None
        images.remove(bakeImage)

    def bakeColorOutput(self, output, file):
        # Setup an Emission Shader
        nodes = self.material.node_tree.nodes
        links = self.material.node_tree.links
        emitNode = nodes.new('ShaderNodeEmission')
        links.new(emitNode.inputs[0], output)
        links.new(self.outputNode.inputs[0], emitNode.outputs[0])
        # Bake Emission
        self.bakeToFile('EMIT', file)
        # Remove the Emission Shader and restore Links
        nodes.remove(emitNode)
        links.new(self.outputNode.inputs[0], self.shaderNode.outputs[0])

    def bakeColorInput(self, input, file):
        node = input.links[0].from_node
        if node.type == 'TEX_IMAGE' and node.image != None:
            # Skip baking and copy the image
            save_image_to_file(node.image, file)
        else:
            self.bakeColorOutput(input.links[0].from_socket, file)

    def bakeFloatInput(self, input, file):
        nodes = self.material.node_tree.nodes
        links = self.material.node_tree.links
        output = input.links[0].from_socket
        convertNode = nodes.new('ShaderNodeCombineRGB')
        links.new(convertNode.inputs[0], output)
        links.new(convertNode.inputs[1], output)
        links.new(convertNode.inputs[2], output)
        self.bakeColorOutput(convertNode.outputs[0], file)
        nodes.remove(convertNode)

    def bakeColorTexture(self):
        input = get_color_input(self.shaderNode)
        if input != None:
            self.inputs['diffuseColor'].value = input.default_value[:3]
            if input.is_linked:
                asset = self.name+'_color.png'
                file = self.exportPath+'/'+asset
                self.bakeColorInput(input, file)
                self.inputs['diffuseColor'].image = asset
                self.inputs['diffuseColor'].uvMap = self.bakeUVMap

    def bakeRoughnessTexture(self):
        input = get_roughness_input(self.shaderNode)
        if input != None:
            self.inputs['roughness'].value = input.default_value
            if input.is_linked:
                asset = self.name+'_roughness.png'
                file = self.exportPath+'/'+asset
                self.bakeFloatInput(input, file)
                self.inputs['roughness'].image = asset
                self.inputs['roughness'].uvMap = self.bakeUVMap

    def bakeMetallicTexture(self):
        input = get_metallic_input(self.shaderNode)
        if input != None:
            value = input.default_value
            self.inputs['metallic'].value = value
            if input.is_linked:
                asset = self.name+'_metallic.png'
                file = self.exportPath+'/'+asset
                self.bakeFloatInput(input, file)
                self.inputs['metallic'].image = asset
                self.inputs['metallic'].uvMap = self.bakeUVMap
                self.inputs['useSpecularWorkflow'].value = 0
            else:
                self.inputs['useSpecularWorkflow'].value = 0 if value > 0.0 else 1

    def bakeOcclusionTexture(self):
        asset = self.name+'_occlusion.png'
        file = self.exportPath+'/'+asset
        self.bakeToFile('AO', file)
        self.inputs['occlusion'].image = asset
        self.inputs['occlusion'].uvMap = self.bakeUVMap

    def bakeTextures(self, mesh, bakeAO):
        self.setupBakeNodes(mesh)
        self.bakeColorTexture()
        self.bakeRoughnessTexture()
        self.bakeMetallicTexture()
        if bakeAO:
            self.bakeOcclusionTexture()
        self.cleanupBakeNodes()

    def getUVMaps(self):
        uvMaps = set()
        for input in self.inputs.values():
            if input.uvMap != None:
                uvMaps.add(input.uvMap)
        return list(uvMaps)

    def exportPrimvarTokens(self):
        items = []
        uvMaps = self.getUVMaps()
        for map in uvMaps:
            items.append(FileItem('token', 'inputs:frame:stPrimvar_'+map, '"'+map+'"'))
        return items

    def exportPrimvarItems(self):
        items = []
        uvMaps = self.getUVMaps()
        for map in uvMaps:
            path = '</Materials/'+self.name+'.inputs:frame:stPrimvar_'+map+'>'
            item = FileItem('def Shader', 'primvar_'+map)
            item.addItem('uniform token', 'info:id', '"UsdPrimvarReader_float2"')
            item.addItem('float2', 'inputs:default', (0.0, 0.0))
            item.addItem('token', 'inputs:varname.connect', path)
            item.addItem('float2', 'outputs:result')
            items.append(item)
        return items

    def exportInputItems(self):
        items = []
        for input in self.inputs.values():
            item = input.exportShaderItem(self.name)
            if item != None:
                items.append(item)
        return items

    def exportPbrShaderItem(self):
        item = FileItem('def Shader', 'pbr')
        item.addItem('uniform token', 'info:id', '"UsdPreviewSurface"')
        for input in self.inputs.values():
            item.append(input.exportShaderInputItem(self.name))
        item.addItem('token', 'outputs:displacement')
        item.addItem('token', 'outputs:surface')
        return item

    def exportMaterialItem(self):
        item = FileItem('def Material', self.name)
        item.items += self.exportPrimvarTokens()
        item.addItem('token', 'outputs:displacement.connect', '</Materials/'+self.name+'/pbr.outputs:displacement>')
        item.addItem('token', 'outputs:surface.connect', '</Materials/'+self.name+'/pbr.outputs:surface>')
        item.append(self.exportPbrShaderItem())
        item.items += self.exportPrimvarItems()
        item.items += self.exportInputItems()
        return item


class Object:
    """Wraper for Blender Objects"""
    def __init__(self, object, scene, type = 'EMPTY'):
        self.object = object
        self.scene = scene
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

    def getTransform(self):
        if self.parent == None:
            scale = self.scene.scale
            return root_matrix_data(self.object.matrix_world, scale)
        return matrix_data(self.object.matrix_local)

    def getMaterialName(self, index):
        if index < 0 or index >= len(self.object.material_slots):
            return ''
        return get_material_name(self.object.material_slots[index].material)

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

        if material >= 0:
            name = self.getMaterialName(material)
            item.addItem('rel', 'material:binding', '</Materials/'+name+'>')

        indices, normals = export_mesh_normals(mesh, material)
        item.addItem('int[]', 'primvars:normals:indices', indices)
        item.addItem('normal3f[]', 'primvars:normals', normals)
        item.items[-1].properties['interpolation'] = '"faceVarying"'

        item.items += self.exportMeshUvItems(material)
        item.addItem('uniform token', 'subdivisionScheme', '"none"')
        return item

    def exportMeshItems(self):
        items = []
        if self.scene.exportMaterials and len(self.mesh.material_slots) > 0:
            self.materials = []
            for mat in range(0, len(self.mesh.material_slots)):
                exportPath = self.scene.exportPath
                material = self.object.material_slots[mat].material
                self.materials.append(Material(material, exportPath))
                self.materials[-1].bakeTextures(self.mesh, self.scene.bakeAO)
                items.append(self.exportMeshItem(mat))
        else:
            items.append(self.exportMeshItem())
        return items

    def exportItem(self):
        item = FileItem('def Xform', self.name)
        item.addItem('custom matrix4d', 'xformOp:transform', self.getTransform())
        item.addItem('uniform token[]', 'xformOpOrder', ['"xformOp:transform"'])

        # Add Meshes if Mesh Object
        if self.type == 'MESH':
            self.createMesh()
            item.items += self.exportMeshItems()

        # Add Any Children
        for child in self.children:
            item.append(child.exportItem())
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
        self.exportPath = ''
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
        obj = Object(object, self, type)
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
        engine = self.context.scene.render.engine
        if self.exportMaterials:
            self.context.scene.render.engine = 'CYCLES'
        for obj in self.objects:
            items.append(obj.exportItem())
        self.context.scene.render.engine = engine
        return items

    def exportMaterialsItem(self):
        item = FileItem('def', 'Materials')
        for mat in self.getMaterials():
            item.append(mat.exportMaterialItem())
        return item

    def getUsdzConverterArgs(self):
        args = []
        return args
