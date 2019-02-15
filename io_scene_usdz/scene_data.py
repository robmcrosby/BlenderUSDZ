import bpy

from io_scene_usdz.object_utils import *
from io_scene_usdz.material_utils import *
from io_scene_usdz.file_data import FileData, FileItem


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
            path = '<'+material.getPath()+'/'+self.name+'_map.outputs:rgb>'
            if self.type == 'float':
                path = '<'+material.getPath()+'/'+self.name+'_map.outputs:r>'
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
    def __init__(self, object, material):
        self.object = object
        self.material = material
        self.name = get_material_name(material)
        self.outputNode = get_output_node(material)
        self.shaderNode = get_shader_node(self.outputNode)
        self.inputs = {}
        self.bakeImageNode = None
        self.bakeUVMapNode = None
        self.activeNode = None
        self.bakeNodes = []
        self.createInputs()

    def createInputs(self):
        diffuse = get_diffuse_color(self.shaderNode)
        specular = get_specular_color(self.shaderNode)
        emissive = get_emissive_color(self.shaderNode)
        clearcoat = get_clearcoat_value(self.shaderNode)
        clearcoatRoughness = get_clearcoat_roughness_value(self.shaderNode)
        metallic = get_metallic_value(self.shaderNode)
        roughness = get_roughness_value(self.shaderNode)
        opacity = get_opacity_value(self.shaderNode)
        ior = get_ior_value(self.shaderNode)
        useSpecular = 0 if metallic > 0.0 else 1
        self.inputs = {
            'diffuseColor':ShaderInput('color3f', 'diffuseColor', diffuse),
            'specularColor':ShaderInput('color3f', 'specularColor', specular),
            'emissiveColor':ShaderInput('color3f', 'emissiveColor', emissive),
            'clearcoat':ShaderInput('float', 'clearcoat', clearcoat),
            'clearcoatRoughness':ShaderInput('float', 'clearcoatRoughness', clearcoatRoughness),
            'displacement':ShaderInput('float', 'displacement', 0),
            'ior':ShaderInput('float', 'ior', ior),
            'metallic':ShaderInput('float', 'metallic', metallic),
            'normal':ShaderInput('normal3f', 'normal', (0.0, 0.0, 1.0)),
            'occlusion':ShaderInput('float', 'occlusion', 0.0),
            'roughness':ShaderInput('float', 'roughness', roughness),
            'opacity':ShaderInput('float', 'opacity', opacity),
            'useSpecularWorkflow':ShaderInput('int', 'useSpecularWorkflow', useSpecular),
        }

    def setupBakeOutputNodes(self):
        nodes = self.material.node_tree.nodes
        self.activeNode = nodes.active
        if self.bakeImageNode == None:
            self.bakeImageNode = nodes.new('ShaderNodeTexImage')
            nodes.active = self.bakeImageNode
        if self.bakeUVMapNode == None:
            self.bakeUVMapNode = nodes.new('ShaderNodeUVMap')
            self.bakeUVMapNode.uv_map = self.object.bakeUVMap
        links = self.material.node_tree.links
        links.new(self.bakeImageNode.inputs[0], self.bakeUVMapNode.outputs[0])

    def cleanupBakeOutputNodes(self):
        self.cleanupBakeNodes()
        nodes = self.material.node_tree.nodes
        nodes.active = self.activeNode
        if self.bakeImageNode != None:
            nodes.remove(self.bakeImageNode)
            self.bakeImageNode = None
        if self.bakeUVMapNode != None:
            nodes.remove(self.bakeUVMapNode)
            self.bakeUVMapNode = None

    def setupBakeColorOutput(self, output):
        if output != None:
            nodes = self.material.node_tree.nodes
            links = self.material.node_tree.links
            emitNode = nodes.new('ShaderNodeEmission')
            links.new(emitNode.inputs[0], output)
            links.new(self.outputNode.inputs[0], emitNode.outputs[0])
            self.bakeNodes.append(emitNode)
            return True
        return False

    def setupBakeColorInput(self, input):
        if input != None and input.is_linked:
            return self.setupBakeColorOutput(input.links[0].from_socket)
        return False

    def setupBakeFloatOutput(self, output):
        if output != None:
            nodes = self.material.node_tree.nodes
            links = self.material.node_tree.links
            convertNode = nodes.new('ShaderNodeCombineRGB')
            links.new(convertNode.inputs[0], output)
            links.new(convertNode.inputs[1], output)
            links.new(convertNode.inputs[2], output)
            self.bakeNodes.append(convertNode)
            return self.setupBakeColorOutput(convertNode.outputs[0])
        return False

    def setupBakeFloatInput(self, input):
        if input != None and input.is_linked:
            return self.setupBakeFloatOutput(input.links[0].from_socket)
        return False

    def setupBakeDiffuse(self, asset):
        input = get_diffuse_input(self.shaderNode)
        if self.setupBakeColorInput(input):
            self.inputs['diffuseColor'].image = asset
            self.inputs['diffuseColor'].uvMap = self.object.bakeUVMap
            return True
        return False

    def setupBakeRoughness(self, asset):
        input = get_roughness_input(self.shaderNode)
        if self.setupBakeFloatInput(input):
            self.inputs['roughness'].image = asset
            self.inputs['roughness'].uvMap = self.object.bakeUVMap
            return True
        return False

    def setupBakeMetallic(self, asset):
        input = get_metallic_input(self.shaderNode)
        if self.setupBakeFloatInput(input):
            self.inputs['metallic'].image = assetw
            self.inputs['metallic'].uvMap = self.object.bakeUVMap
            self.inputs['useSpecularWorkflow'].value = 0
            return True
        return False

    def setupBakeNormals(self, asset):
        input = get_normal_input(self.shaderNode)
        if input != None and input.is_linked:
            self.inputs['normal'].image = asset
            self.inputs['normal'].uvMap = self.object.bakeUVMap
            return True
        return False

    def cleanupBakeNodes(self):
        if len(self.bakeNodes) > 0:
            nodes = self.material.node_tree.nodes
            for node in self.bakeNodes:
                nodes.remove(node)
            self.bakeNodes = []
            links = self.material.node_tree.links
            links.new(self.outputNode.inputs[0], self.shaderNode.outputs[0])

    def setBakeImage(self, image):
        if self.bakeImageNode != None:
            self.bakeImageNode.image = image

    def getUVMaps(self):
        uvMaps = set()
        for input in self.inputs.values():
            if input.uvMap != None:
                uvMaps.add(input.uvMap)
        return list(uvMaps)

    def getPath(self):
        return self.object.getPath()+'/'+self.name

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
            path = '<'+self.getPath()+'.inputs:frame:stPrimvar_'+map+'>'
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
            item.append(input.exportShaderInputItem(self))
        item.addItem('token', 'outputs:displacement')
        item.addItem('token', 'outputs:surface')
        return item

    def exportItem(self):
        item = FileItem('def Material', self.name)
        item.items += self.exportPrimvarTokens()
        item.addItem('token', 'outputs:displacement.connect', '<'+self.getPath()+'/pbr.outputs:displacement>')
        item.addItem('token', 'outputs:surface.connect', '<'+self.getPath()+'/pbr.outputs:surface>')
        item.append(self.exportPbrShaderItem())
        item.items += self.exportPrimvarItems()
        item.items += self.exportInputItems()
        return item




class Object:
    """Wraper for Blender Objects"""
    def __init__(self, object, scene, type = 'EMPTY'):
        self.name = object.name.replace('.', '_')
        self.object = object
        self.scene = scene
        self.type = type
        self.parent = None
        self.children = []
        self.meshes = []
        self.materials = []
        self.bakeUVMap = ''
        self.bakeWidth = 1024
        self.bakeHeight = 1024
        self.bakeImage = None
        self.hidden = object.hide_render

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        self.clearMeshes()
        self.materials = []
        self.object.hide_render = self.hidden

    def createMaterials(self):
        self.materials = []
        if self.scene.exportMaterials:
            for slot in self.object.material_slots:
                self.materials.append(Material(self, slot.material))

    def createMeshes(self):
        self.clearMeshes()
        mesh = duplicate_object(self.object)
        apply_object_modifers(mesh)
        add_to_collection(mesh, self.scene.collection)
        mesh.hide_render = False
        self.object.hide_render = True
        self.meshes.append(mesh)
        if self.uvMapNeeded(mesh):
            uv_smart_project(mesh)

    def clearMeshes(self):
        for mesh in self.meshes:
            delete_object(mesh)
        self.meshes = []

    def setAsMesh(self):
        if self.type != 'MESH' and self.object.type == 'MESH':
            print('Set As MESH!')
            self.type = 'MESH'
            self.createMaterials()
            self.createMeshes()

    def uvMapNeeded(self, mesh):
        if self.scene.bakeTextures or self.scene.bakeAO:
            return len(mesh.data.uv_layers) == 0
        return False

    def getPath(self):
        if self.parent == None:
            return '/'+self.name
        return self.parent.getPath()+'/'+self.name

    def setupBakeImage(self, file):
        self.cleanupBakeImage()
        images = bpy.data.images
        self.bakeImage = images.new('BakeImage', self.bakeWidth, self.bakeHeight)
        self.bakeImage.file_format = 'PNG'
        self.bakeImage.filepath = file
        for mat in self.materials:
            mat.setBakeImage(self.bakeImage)

    def cleanupBakeImage(self):
        if self.bakeImage != None:
            images = bpy.data.images
            images.remove(self.bakeImage)
            self.bakeImage = None
        for mat in self.materials:
            mat.setBakeImage(None)

    def setupBakeOutputNodes(self):
        self.bakeUVMap = get_active_uv_map(self.object)
        for mat in self.materials:
            mat.setupBakeOutputNodes()

    def cleanupBakeOutputNodes(self):
        for mat in self.materials:
            mat.cleanupBakeOutputNodes()

    def cleanupBakeNodes(self):
        for mat in self.materials:
            mat.cleanupBakeNodes()

    def bakeToFile(self, type, file):
        self.setupBakeImage(file)
        bpy.ops.object.bake(type=type, use_clear=True)
        self.bakeImage.save()
        self.cleanupBakeImage()

    def bakeDiffuseTexture(self):
        asset = self.name+'_diffuse.png'
        bake = False
        for mat in self.materials:
            bake = mat.setupBakeDiffuse(asset) or bake
        if bake:
            self.bakeToFile('EMIT', self.scene.exportPath+'/'+asset)
        self.cleanupBakeNodes()

    def bakeRoughnessTexture(self):
        asset = self.name+'_roughness.png'
        bake = False
        for mat in self.materials:
            bake = mat.setupBakeRoughness(asset) or bake
        if bake:
            self.bakeToFile('EMIT', self.scene.exportPath+'/'+asset)
        self.cleanupBakeNodes()

    def bakeMetallicTexture(self):
        asset = self.name+'_metallic.png'
        bake = False
        for mat in self.materials:
            bake = mat.setupBakeMetallic(asset) or bake
        if bake:
            self.bakeToFile('EMIT', self.scene.exportPath+'/'+asset)
        self.cleanupBakeNodes()

    def bakeNormalTexture(self):
        asset = self.name+'_normal.png'
        bake = False
        for mat in self.materials:
            bake = mat.setupBakeNormals(asset) or bake
        if bake:
            self.bakeToFile('NORMAL', self.scene.exportPath+'/'+asset)
        self.cleanupBakeNodes()

    def bakeOcclusionTexture(self):
        asset = self.name+'_occlusion.png'
        bake = False
        for mat in self.materials:
            mat.inputs['occlusion'].image = asset
            mat.inputs['occlusion'].uvMap = self.bakeUVMap
            bake = True
        if bake:
            self.bakeToFile('AO', self.scene.exportPath+'/'+asset)

    def bakeTextures(self):
        select_object(self.meshes[0])
        self.setupBakeOutputNodes()
        if self.scene.bakeTextures:
            self.bakeDiffuseTexture()
            self.bakeRoughnessTexture()
            self.bakeMetallicTexture()
            self.bakeNormalTexture()
        if self.scene.bakeAO:
            self.bakeOcclusionTexture()
        self.cleanupBakeOutputNodes()

    def getTransform(self):
        if self.parent == None:
            scale = self.scene.scale
            return root_matrix_data(self.object.matrix_world, scale)
        return matrix_data(self.object.matrix_local)

    def exportMeshUvItems(self, material):
        mesh = self.meshes[0].data
        items = []
        for layer in mesh.uv_layers:
            indices, uvs = export_mesh_uvs(mesh, layer, material)
            name = layer.name.replace('.', '_')
            items.append(FileItem('int[]', 'primvars:'+name+':indices', indices))
            items.append(FileItem('texCoord2f[]', 'primvars:'+name, uvs))
            items[-1].properties['interpolation'] = '"faceVarying"'
        return items

    def exportMeshItem(self, material = -1):
        mesh = self.meshes[0].data
        name = self.object.data.name.replace('.', '_')
        if material >= 0:
            name += '_' + self.materials[material].name
        item = FileItem('def Mesh', name)

        extent = object_extents(self.meshes[0])
        item.addItem('float3[]', 'extent', extent)

        vertexCounts = mesh_vertex_counts(mesh, material)
        item.addItem('int[]', 'faceVertexCounts', vertexCounts)

        indices, points = export_mesh_vertices(mesh, material)
        item.addItem('int[]', 'faceVertexIndices', indices)
        item.addItem('point3f[]', 'points', points)

        if material >= 0:
            path = self.materials[material].getPath()
            item.addItem('rel', 'material:binding', '<'+path+'>')

        indices, normals = export_mesh_normals(mesh, material)
        item.addItem('int[]', 'primvars:normals:indices', indices)
        item.addItem('normal3f[]', 'primvars:normals', normals)
        item.items[-1].properties['interpolation'] = '"faceVarying"'

        item.items += self.exportMeshUvItems(material)
        item.addItem('uniform token', 'subdivisionScheme', '"none"')
        return item

    def exportMeshItems(self):
        items = []
        if len(self.materials) > 0:
            for mat in range(0, len(self.materials)):
                items.append(self.exportMeshItem(mat))
        else:
            items.append(self.exportMeshItem())
        return items

    def exportMaterialItems(self):
        items = []
        for mat in self.materials:
            items.append(mat.exportItem())
        return items

    def exportItem(self):
        item = FileItem('def Xform', self.name)
        item.addItem('custom matrix4d', 'xformOp:transform', self.getTransform())
        item.addItem('uniform token[]', 'xformOpOrder', ['"xformOp:transform"'])

        # Add Meshes if Mesh Object
        if self.type == 'MESH':
            item.items += self.exportMeshItems()
            item.items += self.exportMaterialItems()

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
        self.bakeSeparate = False
        self.bakeSamples = 8
        self.scale = 1.0
        self.animated = False
        self.collection = None

    def cleanup(self):
        self.clearObjects()
        deselect_objects()
        select_objects(self.bpyObjects)
        set_active_object(self.bpyActive)
        delete_collection(self.collection)
        self.collection = None

    def clearObjects(self):
        for obj in self.objMap.values():
            obj.cleanup()
        self.objects = []
        self.objMap = {}

    def loadContext(self, context):
        self.context = context
        self.bpyObjects = context.selected_objects.copy()
        self.bpyActive = context.view_layer.objects.active
        self.loadObjects()

    def loadObjects(self):
        delete_collection(self.collection)
        self.collection = create_collection('TempCollection')
        for obj in self.bpyObjects:
            if (obj.type == 'MESH'):
                self.addBpyObject(obj, obj.type)

    def addBpyObject(self, object, type = 'EMPTY'):
        obj = Object(object, self)
        if obj.name in self.objMap:
            obj = self.objMap[obj.name]
        elif object.parent != None:
            obj.parent = self.addBpyObject(object.parent)
            obj.parent.children.append(obj)
            self.objMap[obj.name] = obj
        else:
            self.objects.append(obj)
            self.objMap[obj.name] = obj
        if type == 'MESH':
            obj.setAsMesh()
        return obj

    def bakeTextures(self):
        for obj in self.objMap.values():
            if obj.type:
                obj.bakeTextures()

    def exportObjectItems(self):
        items = []
        for obj in self.objects:
            items.append(obj.exportItem())
        return items

    def exportFileData(self):
        data = FileData()
        data.items = self.exportObjectItems()
        return data
