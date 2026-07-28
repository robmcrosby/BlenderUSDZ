import bpy
import mathutils

from io_scene_usdz.object_utils import *
from io_scene_usdz.material_utils import *
from io_scene_usdz.value_types import *


class ShaderInput:
    """Shader Input Information"""

    def __init__(self, type, name, default):
        self.type = type
        self.name = name
        self.value = default
        self.image = None
        self.uvMap = None
        self.usdAtt = None

    def exportShaderInput(self, material, usdShader):
        if self.usdAtt != None:
            usdShader['inputs:'+self.name] = self.usdAtt
        else:
            usdShader['inputs:'+self.name] = self.value
            if usdShader['inputs:'+self.name].valueType.name != self.type:
                usdShader['inputs:'+self.name].valueTypeStr = self.type

    def exportShader(self, material, usdMaterial):
        if self.image != None and self.uvMap != None:
            v = self.value
            default = (v, v, v, 1.0) if self.type == 'float' else v+(1.0,)
            usdShader = usdMaterial.createChild(self.name+'_map', ClassType.Shader)
            usdShader['info:id'] = 'UsdUVTexture'
            usdShader['info:id'].addQualifier('uniform')
            usdShader['inputs:fallback'] = default
            usdShader['inputs:file'] = self.image
            usdShader['inputs:file'].valueType = ValueType.asset
            primUsdShader = usdMaterial.getChild('primvar_'+self.uvMap)
            if primUsdShader != None:
                usdShader['inputs:st'] = primUsdShader['outputs:result']
            usdShader['inputs:wrapS'] = 'repeat'
            usdShader['inputs:wrapT'] = 'repeat'
            if self.type == 'float':
                usdShader['outputs:r'] = ValueType.float
                if usdShader['outputs:r'].valueType.name != self.type:
                    usdShader['outputs:r'].valueTypeStr = self.type
                self.usdAtt = usdShader['outputs:r']
            else:
                usdShader['outputs:rgb'] = ValueType.vec3f
                if usdShader['outputs:rgb'].valueType.name != self.type:
                    usdShader['outputs:rgb'].valueTypeStr = self.type
                self.usdAtt = usdShader['outputs:rgb']


class ShaderNode:
    def __init__(self, node, tree):
        self.tree = tree
        self.node = node
        self.metallicValue = node.inputs['Metallic'].default_value
        self.metallicSocket = node.inputs['Metallic'].links[0].from_socket if len(node.inputs['Metallic'].links) > 0 else None
        self.roughnessValue = node.inputs['Roughness'].default_value
        self.roughnessSocket = node.inputs['Roughness'].links[0].from_socket if len(node.inputs['Roughness'].links) > 0 else None
        self.alphaValue = node.inputs['Alpha'].default_value
        self.alphaSocket = node.inputs['Alpha'].links[0].from_socket if len(node.inputs['Alpha'].links) > 0 else None
    
    def setForDiffuse(self):
        # Set Metallic to Zero
        if len(self.node.inputs['Metallic'].links) > 0:
            link = self.node.inputs['Metallic'].links[0]
            self.tree.links.remove(link)
        self.node.inputs['Metallic'].default_value = 0.0
        # Set Alpha to Opaque
        if len(self.node.inputs['Alpha'].links) > 0:
            link = self.node.inputs['Alpha'].links[0]
            self.tree.links.remove(link)
        self.node.inputs['Alpha'].default_value = 1.0
    
    def setForRoughness(self):
        # Set Roughness Socket
        self.node.inputs['Roughness'].default_value = self.roughnessValue
        if len(self.node.inputs['Roughness'].links) > 0:
            link = self.node.inputs['Roughness'].links[0]
            self.tree.links.remove(link)
        if self.roughnessSocket != None:
            self.tree.links.new(self.roughnessSocket, self.node.inputs['Roughness'])
    
    def setForMetallic(self):
        # Set Metallic to Roughness Input Socket
        self.node.inputs['Roughness'].default_value = self.metallicValue
        if len(self.node.inputs['Roughness'].links) > 0:
            link = self.node.inputs['Roughness'].links[0]
            self.tree.links.remove(link)
        if self.metallicSocket != None:
            self.tree.links.new(self.metallicSocket, self.node.inputs['Roughness'])
    
    def setForAlpha(self):
        # Set Alpha to Roughness Input Socket
        self.node.inputs['Roughness'].default_value = self.alphaValue
        if len(self.node.inputs['Roughness'].links) > 0:
            link = self.node.inputs['Roughness'].links[0]
            self.tree.links.remove(link)
        if self.alphaSocket != None:
            self.tree.links.new(self.alphaSocket, self.node.inputs['Roughness'])
    
    def restore(self):
        # Restore Roughness
        self.node.inputs['Roughness'].default_value = self.roughnessValue
        if len(self.node.inputs['Roughness'].links) > 0:
            link = self.node.inputs['Roughness'].links[0]
            self.tree.links.remove(link)
        if self.roughnessSocket != None:
            self.tree.links.new(self.roughnessSocket, self.node.inputs['Roughness'])
        # Restore Metallic
        self.node.inputs['Metallic'].default_value = self.metallicValue
        if len(self.node.inputs['Metallic'].links) > 0:
            link = self.node.inputs['Metallic'].links[0]
            self.tree.links.remove(link)
        if self.metallicSocket != None:
            self.tree.links.new(self.metallicSocket, self.node.inputs['Metallic'])
        # Restore Alpha
        self.node.inputs['Alpha'].default_value = self.alphaValue
        if len(self.node.inputs['Alpha'].links) > 0:
            link = self.node.inputs['Alpha'].links[0]
            self.tree.links.remove(link)
        if self.alphaSocket != None:
            self.tree.links.new(self.alphaSocket, self.node.inputs['Alpha'])


def getBpyShaderNodes(tree):
    groups = [n for n in tree.nodes if n.bl_idname == 'ShaderNodeGroup']
    trees = [tree] + [g.node_tree for g in groups]
    nodes = [[ShaderNode(n, t) for n in t.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'] for t in trees]
    return [n for s in nodes for n in s]


class Material:
    """Wraper for Blender Material"""
    def __init__(self, material):
        self.material = material
        self.usdMaterial = None
        self.name = getBpyMaterialName(material)
        self.outputNode = getBpyOutputNode(material)
        self.shaderNode = getBpyShaderNode(self.outputNode)
        self.shaderNodes = getBpyShaderNodes(material.node_tree)
        self.bakeImage = None
        self.inputs = {}
        self.bakeImageNode = None
        self.bakeUVMapNode = None
        self.activeNode = None
        self.bakeNodes = []
        self.createInputs()

    def createInputs(self):
        defDiffuseColor = self.material.diffuse_color[:3]
        defRoughness = self.material.roughness
        diffuse = getBpyDiffuseColor(self.shaderNode, defDiffuseColor)
        specular = getBpySpecularColor(self.shaderNode)
        emissive = getBpyEmissiveColor(self.shaderNode)
        clearcoat = getBpyClearcoatValue(self.shaderNode)
        clearcoatRoughness = getBpyClearcoatRoughnessValue(self.shaderNode)
        metallic = getBpyMetallicValue(self.shaderNode)
        roughness = getBpyRoughnessValue(self.shaderNode, defRoughness)
        opacity = getBpyAlphaValue(self.shaderNode)
        opacityThreshold = self.material.alpha_threshold
        ior = getBpyIorValue(self.shaderNode)
        useSpecular = 0 if metallic > 0.0 else 1
        self.inputs = {
            'clearcoat':ShaderInput('float', 'clearcoat', clearcoat),
            'clearcoatRoughness':ShaderInput('float', 'clearcoatRoughness', clearcoatRoughness),
            'diffuseColor':ShaderInput('color3f', 'diffuseColor', diffuse),
            'displacement':ShaderInput('float', 'displacement', 0),
            'emissiveColor':ShaderInput('color3f', 'emissiveColor', emissive),
            'ior':ShaderInput('float', 'ior', ior),
            'metallic':ShaderInput('float', 'metallic', metallic),
            'normal':ShaderInput('normal3f', 'normal', (0.0, 0.0, 1.0)),
            'occlusion':ShaderInput('float', 'occlusion', 0.0),
            'opacity':ShaderInput('float', 'opacity', opacity),
            'opacityThreshold':ShaderInput('float', 'opacityThreshold', opacityThreshold),
            'roughness':ShaderInput('float', 'roughness', roughness),
            'specularColor':ShaderInput('color3f', 'specularColor', specular),
            'useSpecularWorkflow':ShaderInput('int', 'useSpecularWorkflow', useSpecular),
        }

    def setupBakeOutputNodes(self, object):
        nodes = self.material.node_tree.nodes
        self.activeNode = nodes.active
        if self.bakeImageNode == None:
            self.bakeImageNode = nodes.new('ShaderNodeTexImage')
            nodes.active = self.bakeImageNode
        if self.bakeUVMapNode == None:
            self.bakeUVMapNode = nodes.new('ShaderNodeUVMap')
            self.bakeUVMapNode.uv_map = object.bakeUVMap
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

    def setForDiffuseBake(self):
        for node in self.shaderNodes:
            node.setForDiffuse()
    
    def setForRoughnessBake(self):
        for node in self.shaderNodes:
            node.setForRoughness()
    
    def setForMetallicBake(self):
        for node in self.shaderNodes:
            node.setForMetallic()
    
    def setForAlphaBake(self):
        for node in self.shaderNodes:
            node.setForAlpha()
    
    def restoreShaderNodes(self):
        for node in self.shaderNodes:
            node.restore()

    def setupBakeFloatInput(self, input):
        if input != None and input.is_linked:
            return self.setupBakeFloatOutput(input.links[0].from_socket)
        return False
    
    def clearBakeImage(self):
        self.setBakeImage(None)
        if self.bakeImage != None:
            bpy.data.images.remove(self.bakeImage)
            self.bakeImage = None
    
    def setDiffuseImage(self, image, uvMap):
        self.setForDiffuseBake()
        self.bakeImage = image
        self.setBakeImage(image)
        self.inputs['diffuseColor'].image = image.name
        self.inputs['diffuseColor'].uvMap = uvMap
    
    def setEmissionImage(self, image, uvMap):
        self.setForDiffuseBake()
        self.bakeImage = image
        self.setBakeImage(image)
        self.inputs['emissiveColor'].image = image.name
        self.inputs['emissiveColor'].uvMap = uvMap
    
    def setRoughnessImage(self, image, uvMap):
        self.setForRoughnessBake()
        self.bakeImage = image
        self.setBakeImage(image)
        self.inputs['roughness'].image = image.name
        self.inputs['roughness'].uvMap = uvMap
    
    def setMetallicImage(self, image, uvMap):
        self.setForMetallicBake()
        self.bakeImage = image
        self.setBakeImage(image)
        self.inputs['metallic'].image = image.name
        self.inputs['metallic'].uvMap = uvMap
        self.inputs['useSpecularWorkflow'].value = 0
    
    def setOpacityImage(self, image, uvMap):
        self.setForAlphaBake()
        self.bakeImage = image
        self.setBakeImage(image)
        self.inputs['opacity'].image = image.name
        self.inputs['opacity'].uvMap = uvMap
    
    def setNormalImage(self, image, uvMap):
        self.setForDiffuseBake()
        self.bakeImage = image
        self.setBakeImage(image)
        self.inputs['normal'].image = image.name
        self.inputs['normal'].uvMap = uvMap
    
    def setOcclusionImage(self, image, uvMap):
        self.setForDiffuseBake()
        self.bakeImage = image
        self.setBakeImage(image)
        self.inputs['occlusion'].image = image.name
        self.inputs['occlusion'].uvMap = uvMap

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

    def exportPrimvar(self, usdMaterial):
        uvMaps = self.getUVMaps()
        for map in uvMaps:
            usdMaterial['inputs:frame:stPrimvar_' + map] = map
            usdShader = usdMaterial.createChild('primvar_'+map, ClassType.Shader)
            usdShader['info:id'] = 'UsdPrimvarReader_float2'
            usdShader['info:id'].addQualifier('uniform')
            usdShader['inputs:fallback'] = (0.0, 0.0)
            usdShader['inputs:varname'] = usdMaterial['inputs:frame:stPrimvar_' + map]
            usdShader['outputs:result'] = ValueType.vec2f

    def exportInputs(self, usdMaterial):
        for input in self.inputs.values():
            input.exportShader(self, usdMaterial)

    def exportPbrShader(self, usdMaterial):
        usdShader = usdMaterial.createChild('pbr', ClassType.Shader)
        usdShader['info:id'] = 'UsdPreviewSurface'
        for input in self.inputs.values():
            input.exportShaderInput(self, usdShader)
        usdShader['outputs:displacement'] = ValueType.token
        usdShader['outputs:surface'] = ValueType.token
        return usdShader

    def exportUsd(self, parent):
        self.usdMaterial = parent.createChild(self.name, ClassType.Material)
        self.exportPrimvar(self.usdMaterial)
        self.exportInputs(self.usdMaterial)
        pbrShader = self.exportPbrShader(self.usdMaterial)
        self.usdMaterial['outputs:displacement'] = pbrShader['outputs:displacement']
        self.usdMaterial['outputs:surface'] = pbrShader['outputs:surface']


class Mesh:
    """Wraper for Blender Mesh Data"""
    def __init__(self, object, scene):
        self.name = object.data.name.replace('.', '_').replace(' ', '_')
        self.object = object
        self.scene = scene
        self.objectCopy = None
        self.armatueCopy = None
        self.shared = False
        self.usdMesh = None
        self.createCopies()

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        self.clearCopies()

    def createCopies(self):
        self.clearCopies()
        self.armature = self.getArmature()
        if self.armature != None and self.scene.animated:
            obj, arm = duplicateBpySkinnedObject(self.object, self.armature)
            self.objectCopy = obj
            applyBpyArmatureAnimation(
                dstArmature = arm,
                srcArmature = self.armature,
                startFrame = self.scene.startFrame,
                endFrame = self.scene.endFrame
            )
            self.armatueCopy = arm
            self.armatueCopy.data.pose_position = 'REST'
            addToBpyCollection(self.armatueCopy, self.scene.collection)
            addToBpyCollection(self.objectCopy, self.scene.collection)
        else:
            self.objectCopy = duplicateBpyObject(self.object)
            addToBpyCollection(self.objectCopy, self.scene.collection)
        applyBpyObjectModifers(self.objectCopy)
        self.objectCopy.hide_render = False
        if self.uvMapNeeded(self.objectCopy):
            applyBpySmartProjection(self.objectCopy)

    def clearCopies(self):
        if self.objectCopy != None:
            deleteBpyObject(self.objectCopy)
            self.objectCopy = None
        if self.armatueCopy != None:
            deleteBpyObject(self.armatueCopy)
            self.armatueCopy = None

    def getArmature(self):
        parent = self.object.parent
        if parent != None and parent.type == 'ARMATURE':
            return parent
        return None

    def exportMeshUvs(self, usdMesh):
        mesh = self.objectCopy.data
        for layer in mesh.uv_layers:
            uvs, indices = exportBpyMeshUvs(mesh, layer)
            name = layer.name.replace('.', '_').replace(' ', '_')
            usdMesh.addUVMap(name, uvs, indices)

    def exportJoints(self, usdMesh):
        mesh = self.objectCopy.data
        if self.armatueCopy != None and self.scene.animated:
            indices, weights, size = exportBpyMeshWeights(self.objectCopy)
            usdMesh['primvars:skel:jointIndices'] = indices
            usdMesh['primvars:skel:jointIndices']['elementSize'] = size
            usdMesh['primvars:skel:jointIndices']['interpolation'] = 'vertex'
            usdMesh['primvars:skel:jointWeights'] = weights
            usdMesh['primvars:skel:jointWeights']['elementSize'] = size
            usdMesh['primvars:skel:jointWeights']['interpolation'] = 'vertex'

    def exportSkeleton(self, usdObj):
        usdSkeleton = None
        if self.armatueCopy != None and self.scene.animated:
            joints = exportBpyJoints(self.armatueCopy)
            bind = exportBpyBindTransforms(self.armatueCopy)
            rest = exportBpyRestTransforms(self.armatueCopy)
            name = self.armature.name.replace('.', '_').replace(' ', '_')
            usdSkeleton = usdObj.createChild(name, ClassType.Skeleton)
            usdSkeleton['joints'] = joints
            usdSkeleton['joints'].addQualifier('uniform')
            usdSkeleton['bindTransforms'] = bind
            usdSkeleton['bindTransforms'].addQualifier('uniform')
            usdSkeleton['restTransforms'] = rest
            usdSkeleton['restTransforms'].addQualifier('uniform')
        return usdSkeleton

    def exportShared(self, usdMeshes):
        self.usdMesh = self.exportToObject(usdMeshes, ClassType.Mesh)
        self.usdMesh.specifierType = SpecifierType.Class
        return self.usdMesh

    def exportToObject(self, usdObj, classType = ClassType.Mesh):
        mesh = self.objectCopy.data
        name = self.object.data.name.replace('.', '_').replace(' ', '_')
        usdMesh = usdObj.createChild(name, classType)
        
        # Gather Mesh Components
        extent = exportBpyExtents(self.objectCopy, self.scene.scale)
        counts = exportBpyMeshVertexCounts(mesh)
        points, indices = exportBpyMeshVertices(mesh)
        usdMesh.setMesh(extent, points, indices, counts)
        
        self.exportMeshUvs(usdMesh)
        
        # Export Normals
        normals, indices = exportBpyMeshNormals(mesh)
        usdMesh.setNormals(normals, indices)
        
        # Set Subdivision Scheme
        usdMesh['subdivisionScheme'] = 'none'
        usdMesh['subdivisionScheme'].addQualifier('uniform')
        return usdMesh

    def uvMapNeeded(self, mesh):
        if self.scene.bakeTextures or self.scene.bakeAO:
            return len(mesh.data.uv_layers) == 0
        return False


class Object:
    """Wraper for Blender Objects"""
    def __init__(self, object, scene, type = 'EMPTY'):
        self.name = object.name.replace('.', '_').replace(' ', '_')
        self.object = object
        self.scene = scene
        self.type = type
        self.mesh = None
        self.parent = None
        self.children = []
        self.materials = []
        self.bakeUVMap = ''
        self.bakeWidth = scene.bakeSize
        self.bakeHeight = scene.bakeSize
        self.bakeImage = None
        self.hidden = object.hide_render
        self.collection = None

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        if  self.object != None:
            self.object.hide_render = self.hidden
        if self.mesh != None:
            self.mesh.cleanup()
            self.mesn = None
        self.materials = []

    def hasParent(self):
        parent = self.object.parent if self.object != None else None
        return parent != None and parent.type != 'ARMATURE'

    def createMaterials(self):
        self.materials = []
        if self.scene.exportMaterials:
            for i, slot in enumerate(self.object.material_slots):
                if slot.material != None:
                    if slot.material.name in self.scene.materials:
                        self.materials.append((i, self.scene.materials[slot.material.name]))
                    else:
                        material = Material(slot.material)
                        self.scene.materials[slot.material.name] = material
                        self.materials.append((i, material))

    def createMesh(self):
        if self.mesh == None:
            if self.object.data.name in self.scene.meshObjs:
                self.mesh = self.scene.meshObjs[self.object.data.name].mesh
                self.mesh.shared = True
            else:
                self.mesh = Mesh(self.object, self.scene)
                self.scene.meshObjs[self.object.data.name] = self

    def setAsMesh(self):
        if self.type != 'MESH' and self.object.type == 'MESH':
            self.type = 'MESH'
            if not self.object.visible_get():
                collection = self.object.users_collection[0]
                setBpyCollectionVisibility(collection, True)
                self.scene.hiddenCollections.add(collection)
            self.createMaterials()
            self.createMesh()
            self.object.hide_render = True

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
        for _, mat in self.materials:
            mat.setBakeImage(self.bakeImage)

    def cleanupBakeImage(self):
        if self.bakeImage != None:
            images = bpy.data.images
            images.remove(self.bakeImage)
            self.bakeImage = None
        for _, mat in self.materials:
            mat.setBakeImage(None)

    def setupBakeOutputNodes(self):
        self.bakeUVMap = getBpyActiveUvMap(self.object)
        for _, mat in self.materials:
            mat.setupBakeOutputNodes(self)

    def cleanupBakeOutputNodes(self):
        for _, mat in self.materials:
            mat.cleanupBakeOutputNodes()
            mat.restoreShaderNodes()

    def cleanupBakeNodes(self):
        for _, mat in self.materials:
            mat.cleanupBakeNodes()

    def createBakeImage(self, file):
        image = bpy.data.images.new(file, self.bakeWidth, self.bakeHeight)
        image.file_format = 'PNG'
        image.filepath = self.scene.exportPath+'/'+file
        self.scene.textureFilePaths.append(image.filepath)
        return image

    def bakeDiffuseTextures(self):
        for _, mat in self.materials:
            image = self.createBakeImage(self.name+'-'+mat.name+'-diffuse.png')
            mat.setDiffuseImage(image, self.bakeUVMap)
        self.scene.context.scene.cycles.samples = 4
        print(f'Select: {self.mesh.objectCopy}')
        bpy.ops.object.bake(type='DIFFUSE', use_clear=True)
        for _, mat in self.materials:
            mat.bakeImage.save()
            mat.clearBakeImage()

    def bakeEmissionTextures(self):
        for _, mat in self.materials:
            image = self.createBakeImage(self.name+'-'+mat.name+'-emission.png')
            mat.setEmissionImage(image, self.bakeUVMap)
        self.scene.context.scene.cycles.samples = 4
        bpy.ops.object.bake(type='EMIT', use_clear=True)
        for _, mat in self.materials:
            mat.bakeImage.save()
            mat.clearBakeImage()

    def bakeRoughnessTextures(self):
        for _, mat in self.materials:
            image = self.createBakeImage(self.name+'-'+mat.name+'-roughness.png')
            mat.setRoughnessImage(image, self.bakeUVMap)
        self.scene.context.scene.cycles.samples = 4
        bpy.ops.object.bake(type='ROUGHNESS', use_clear=True)
        for _, mat in self.materials:
            mat.bakeImage.save()
            mat.clearBakeImage()

    def bakeMetallicTextures(self):
        for _, mat in self.materials:
            image = self.createBakeImage(self.name+'-'+mat.name+'-metallic.png')
            mat.setMetallicImage(image, self.bakeUVMap)
        self.scene.context.scene.cycles.samples = 4
        bpy.ops.object.bake(type='ROUGHNESS', use_clear=True)
        for _, mat in self.materials:
            mat.bakeImage.save()
            mat.clearBakeImage()

    def bakeOpacityTextures(self):
        for _, mat in self.materials:
            image = self.createBakeImage(self.name+'-'+mat.name+'-opacity.png')
            mat.setOpacityImage(image, self.bakeUVMap)
        self.scene.context.scene.cycles.samples = 4
        bpy.ops.object.bake(type='ROUGHNESS', use_clear=True)
        for _, mat in self.materials:
            mat.bakeImage.save()
            mat.clearBakeImage()

    def bakeNormalTextures(self):
        for _, mat in self.materials:
            image = self.createBakeImage(self.name+'-'+mat.name+'-normal.png')
            mat.setNormalImage(image, self.bakeUVMap)
        self.scene.context.scene.cycles.samples = 4
        bpy.ops.object.bake(type='NORMAL', use_clear=True)
        for _, mat in self.materials:
            mat.bakeImage.save()
            mat.clearBakeImage()

    def bakeOcclusionTextures(self):
        for _, mat in self.materials:
            image = self.createBakeImage(self.name+'-'+mat.name+'-occlusion.png')
            mat.setOcclusionImage(image, self.bakeUVMap)
        self.scene.context.scene.cycles.samples = self.scene.bakeSamples
        bpy.ops.object.bake(type='AO', use_clear=True)
        for _, mat in self.materials:
            mat.bakeImage.save()
            mat.clearBakeImage()

    def bakeTextures(self):
        selectBpyObject(self.mesh.objectCopy)
        self.setupBakeOutputNodes()
        if self.scene.bakeDiffuse:
            self.bakeDiffuseTextures()
        if self.scene.bakeRoughness:
            self.bakeRoughnessTextures()
        if self.scene.bakeEmission:
            self.bakeEmissionTextures()
        if self.scene.bakeMetallic:
            self.bakeMetallicTextures()
        if self.scene.bakeOpacity:
            self.bakeOpacityTextures()
        if self.scene.bakeNormals:
            self.bakeNormalTextures()
        if self.scene.bakeAO:
            self.bakeOcclusionTextures()
        self.cleanupBakeOutputNodes()

    def getTransform(self):
        if self.parent == None:
            scale = self.scene.scale
            return convertBpyRootMatrix(self.object.matrix_world, scale)
        return convertBpyMatrix(self.object.matrix_local)

    def exportMaterialSubsets(self, usdMesh):
        if len(self.materials) == 1:
            usdMesh['material:binding'] = self.materials[0][1].usdMaterial
        elif len(self.materials) > 1:
            for i, mat in self.materials:
                mesh = self.mesh.objectCopy.data
                subset = usdMesh.createChild(mat.name, ClassType.GeomSubset)
                subset['elementType'] = 'face'
                subset['elementType'].addQualifier('uniform')
                subset['familyName'] = 'materialBind'
                subset['familyName'].addQualifier('uniform')
                subset['indices'] = exportBpyFaceIndices(mesh, i)
                subset['material:binding'] = mat.usdMaterial
                #subset['material:binding'].addQualifier('uniform')

    def exportMesh(self, usdObj):
        if self.mesh != None:
            if self.mesh.usdMesh != None:
                usdMesh = usdObj.createChild(self.mesh.name, ClassType.Mesh)
                usdMesh.metadata['inherits'] = self.mesh.usdMesh
                usdMesh.metadata['instanceable'] = True
                #usdMesh.metadata['specifier'] = ValueType.Specifier
                #self.exportMaterialSubsets(usdMesh)
            else:
                usdMesh = self.mesh.exportToObject(usdObj)
                self.exportMaterialSubsets(usdMesh)
                usdSkeleton = self.mesh.exportSkeleton(usdObj)
                usdAnimation = self.exportAnimation(usdObj)
                if usdSkeleton != None and usdAnimation != None:
                    self.mesh.exportJoints(usdMesh)
                    usdMesh['skel:animationSource'] = usdAnimation
                    usdMesh['skel:animationSource'].addQualifier('prepend')
                    usdMesh['skel:skeleton'] = usdSkeleton
                    usdMesh['skel:skeleton'].addQualifier('prepend')

    def exportArmatureAnimation(self, armature, usdAnimation):
        usdAnimation['rotations'] = ValueType.quatf
        usdRotations = usdAnimation['rotations']
        usdAnimation['scales'] = ValueType.vec3f
        usdScales = usdAnimation['scales']
        usdAnimation['translations'] = ValueType.vec3f
        usdTranslations = usdAnimation['translations']
        start = self.scene.startFrame
        end = self.scene.endFrame
        selectBpyObject(armature)
        armature.data.pose_position = 'POSE'
        for frame in range(start, end+1):
            self.scene.context.scene.frame_set(frame)
            rotations = []
            scales = []
            locations = []
            for bone in armature.data.bones:
                bone = armature.pose.bones[bone.name]
                scale = bone.scale.copy()
                location = bone.location.copy()
                rotation = bone.bone.matrix.to_quaternion() @ bone.rotation_quaternion
                if bone.parent != None:
                    if bone.bone.use_connect:
                        location = mathutils.Vector((0, bone.parent.length, 0))
                    else:
                        location += mathutils.Vector((0, bone.parent.length, 0))
                else:
                    scale *= self.scene.scale
                    location *= self.scene.scale
                    rotation = bone.rotation_quaternion
                rotations.append(rotation[:])
                scales.append(scale[:])
                locations.append(location[:])
            usdRotations.addTimeSample(frame, rotations)
            usdScales.addTimeSample(frame, scales)
            usdTranslations.addTimeSample(frame, locations)
        self.scene.context.scene.frame_set(self.scene.curFrame)
        bpy.ops.object.mode_set(mode='OBJECT')

    def exportAnimation(self, usdObj):
        usdAnimation = None
        if self.mesh.armatueCopy != None and self.scene.animated:
            self.mesh.armatueCopy.data.pose_position = 'POSE'
            usdAnimation = usdObj.createChild('Animation', ClassType.SkelAnimation)
            usdAnimation['joints'] = exportBpyJoints(self.mesh.armatueCopy)
            usdAnimation['joints'].addQualifier('uniform')
            self.exportArmatureAnimation(self.mesh.armatueCopy, usdAnimation)
        return usdAnimation

    def exportTimeSamples(self, item):
        item['xformOp:transform:transforms'] = ValueType.matrix4d
        item = item['xformOp:transform:transforms']
        start = self.scene.startFrame
        end = self.scene.endFrame
        for frame in range(start, end+1):
            self.scene.context.scene.frame_set(frame)
            item.addTimeSample(frame, self.getTransform())
        self.scene.context.scene.frame_set(self.scene.curFrame)

    def exportUsd(self, parent):
        usdObj = None
        if self.mesh != None and self.mesh.armatueCopy != None and self.scene.animated:
            # Export Skinned Object
            usdObj = parent.createChild(self.name, ClassType.SkelRoot)
        else:
            # Export Ridgid Object
            usdObj = parent.createChild(self.name, ClassType.Xform)
            if self.scene.animated and self.object.animation_data != None:
                self.exportTimeSamples(usdObj)
                usdObj['xformOpOrder'] = ['xformOp:transform:transforms']
                usdObj['xformOpOrder'].addQualifier('uniform')
            else:
                usdObj['xformOp:transform'] = self.getTransform()
                usdObj['xformOp:transform'].addQualifier('custom')
                usdObj['xformOpOrder'] = ['xformOp:transform']
                usdObj['xformOpOrder'].addQualifier('uniform')
        # Add Meshes if Mesh Object
        if self.type == 'MESH':
            self.exportMesh(usdObj)
        # Add Children
        for child in self.children:
            child.exportUsd(usdObj)
        if self.collection != None and self.collection in self.scene.usdCollections:
            usdObj.metadata['inherits'] = self.scene.usdCollections[self.collection]
            usdObj.metadata['instanceable'] = True

    def exportInstanced(self, parent):
        usdObj = None
        if self.mesh != None and self.mesh.armatueCopy != None and self.scene.animated:
            # Export Skinned Object
            usdObj = parent.createChild(self.name, ClassType.SkelRoot)
        else:
            # Export Ridgid Object
            usdObj = parent.createChild(self.name, ClassType.Xform)
            usdObj['xformOp:transform'] = convertBpyMatrix(self.object.matrix_local)
            usdObj['xformOp:transform'].addQualifier('custom')
            usdObj['xformOpOrder'] = ['xformOp:transform']
            usdObj['xformOpOrder'].addQualifier('uniform')
        # Add Meshes if Mesh Object
        if self.type == 'MESH':
            self.exportMesh(usdObj)
        # Add Children
        for child in self.children:
            child.exportInstanced(usdObj)


def getCollectionObjects(collection):
    objects = set(collection.objects)
    for child in collection.children:
        objects = objects.union(getCollectionObjects(child))
    return objects


class Scene:
    """Container for Objects"""

    def __init__(self):
        self.context = None
        self.objects = []
        self.objMap = {}
        self.meshObjs = {}
        self.collections = {}
        self.hiddenCollections = set()
        self.usdCollections = {}
        self.bpyObjects = []
        self.bpyActive = None
        self.bpySelected = []
        self.exportMaterials = False
        self.materials = {}
        self.exportPath = ''
        self.bakeDiffuse = True
        self.bakeRoughness = True
        self.bakeMetallic = True
        self.bakeOpacity = False
        self.bakeEmission = False
        self.bakeNormals = False
        self.bakeAO = False
        self.bakeTextures = False
        self.textureFilePaths = []
        self.bakeSamples = 8
        self.bakeSize = 1024
        self.sharedMeshes = True
        self.scale = 1.0
        self.animated = False
        self.startFrame = 0
        self.endFrame = 0
        self.curFrame = 0
        self.fps = 30
        self.device = 'GPU'
        self.customLayerData = {'creator':'Blender USDZ Plugin'}
        self.collection = None

    def cleanup(self):
        self.clearObjects()
        deselectBpyObjects()
        selectBpyObjects(self.bpySelected)
        setBpyActiveObject(self.bpyActive)
        for collection in self.hiddenCollections:
            setBpyCollectionVisibility(collection, False)
        deleteBpyCollection(self.collection)
        self.collection = None

    def clearObjects(self):
        for obj in self.objMap.values():
            obj.cleanup()
        self.objects = []
        self.objMap = {}

    def loadContext(self, context, collection):
        if context == None:
            context = bpy.context
        bpy.ops.object.mode_set(mode='OBJECT')
        self.context = context
        
        local_collection = None
        if collection:
          local_collection = bpy.data.collections.get((collection, None))
        
        if local_collection:
            self.bpyObjects = list(getCollectionObjects(local_collection))
        else:
            if len(context.selected_objects) > 0:
                self.bpyObjects = list(context.selected_objects)
            else:
                self.bpyObjects = list(context.visible_objects)
        
        self.bpyActive = context.view_layer.objects.active
        self.bpySelected = list(bpy.context.view_layer.objects.selected)
        self.startFrame = context.scene.frame_start
        self.endFrame = context.scene.frame_end
        self.curFrame = context.scene.frame_current
        self.fps = context.scene.render.fps
        self.renderEngine = context.scene.render.engine
        self.scale *= self.getUnitScale()
        self.loadObjects()

    def loadObjects(self):
        deleteBpyCollection(self.collection)
        self.collection = createBpyCollection('TempCollection')
        for obj in self.bpyObjects:
            if (obj.type == 'MESH'):
                self.addBpyObject(obj, obj.type)
            elif (obj.type == 'EMPTY' and obj.instance_type == 'COLLECTION'):
                self.addBpyCollection(obj)

    def getUnitScale(self):
        settings = self.context.scene.unit_settings
        if settings.system == 'NONE':
            return 10.0
        return 100.0 * settings.scale_length

    def getSceneScale(self):
        settings = self.context.scene.unit_settings
        scale = 1.0
        if settings.system == 'METRIC':
            if settings.length_unit == 'KILOMETERS':
                scale = 100000.0
            elif settings.length_unit == 'METERS':
                scale = 100.0
            elif settings.length_unit == 'CENTIMETERS':
                scale = 1.0
            elif settings.length_unit == 'MILLIMETERS':
                scale = 0.1
            elif settings.length_unit == 'MILLIMETERS':
                scale = 0.0001
        elif settings.system == 'IMPERIAL':
            scale = 2.54
            if settings.length_unit == 'MILES':
                scale = 160934.0
            elif settings.length_unit == 'FEET':
                scale = 30.48
            elif settings.length_unit == 'INCHES':
                scale = 2.54
            elif settings.length_unit == 'THOU':
                scale = 0.00254
        else:
            scale = 10.0
        return scale * settings.scale_length

    def addBpyObject(self, object, type = 'EMPTY'):
        obj = Object(object, self)
        if obj.name in self.objMap:
            obj = self.objMap[obj.name]
        elif obj.hasParent():
            obj.parent = self.addBpyObject(object.parent)
            obj.parent.children.append(obj)
            self.objMap[obj.name] = obj
        else:
            self.objects.append(obj)
            self.objMap[obj.name] = obj
        if type == 'MESH':
            obj.setAsMesh()
        return obj

    def addBpyCollection(self, collection):
        name = collection.instance_collection.name.replace('.', '_').replace(' ', '_')
        obj = Object(collection, self)
        obj.collection = name
        if obj.name in self.objMap:
            obj = self.objMap[obj.name]
        elif obj.hasParent():
            obj.parent = self.addBpyObject(collection.parent)
            obj.parent.children.append(obj)
            self.objMap[obj.name] = obj
        else:
            self.objects.append(obj)
            self.objMap[obj.name] = obj
        if not name in self.collections:
            bpyObjs = list(collection.instance_collection.objects)
            objs = []
            for obj in bpyObjs:
                type = obj.type
                obj = Object(obj, self)
                if obj.name in self.objMap:
                    obj = self.objMap[obj.name]
                else:
                    self.objMap[obj.name] = obj
                objs.append(obj)
                if type == 'MESH':
                    obj.setAsMesh()
            self.collections[name] = objs

    def exportBakedTextures(self):
        # Set the Render Engine to Cycles and set Samples
        renderEngine = self.context.scene.render.engine
        renderDevice = self.context.scene.cycles.device
        self.context.scene.render.engine = 'CYCLES'
        self.context.scene.cycles.device = self.device
        self.context.scene.render.bake.target = 'IMAGE_TEXTURES'
        self.context.scene.render.bake.use_selected_to_active = False
        self.context.scene.render.bake.use_pass_direct = False
        self.context.scene.render.bake.use_pass_indirect = False
        self.context.scene.render.bake.use_pass_color = True
        self.context.scene.render.bake.margin = 4
        samples = self.context.scene.cycles.samples
        self.context.scene.cycles.samples = self.bakeSamples
        # Bake textures for each Object
        for obj in self.objMap.values():
            if obj.type == 'MESH':
                obj.bakeTextures()
        # Restore the previous Render Engine and Samples
        self.context.scene.cycles.samples = samples
        self.context.scene.cycles.device = renderDevice
        self.context.scene.render.engine = renderEngine

    def exportSharedMaterials(self, data):
        if len(self.materials) > 0:
            looks = data.createChild('Looks', ClassType.Scope)
            for mat in self.materials.values():
                mat.exportUsd(looks)

    def exportSharedMeshes(self, data):
        objs = []
        for meshObj in self.meshObjs.values():
            if meshObj.mesh.shared:
                objs.append(meshObj)
        if len(objs) > 0:
            meshes = data.createChild('Meshes', ClassType.Scope)
            for meshObj in objs:
                usdMesh = meshObj.mesh.exportShared(meshes)
                meshObj.exportMaterialSubsets(usdMesh)

    def exportCollections(self, data):
        if len(self.collections) > 0:
            collections = data.createChild('Collections', ClassType.Scope)
            for name, objs in self.collections.items():
                collection = collections.createChild(name, ClassType.Xform)
                collection.specifierType = SpecifierType.Class
                for obj in objs:
                    obj.exportInstanced(collection)
                self.usdCollections[name] = collection

    def exportUsd(self):
        data = UsdData()
        data['upAxis'] = 'Y'
        if self.animated:
            data['startTimeCode'] = float(self.startFrame)
            data['endTimeCode'] = float(self.endFrame)
            data['timeCodesPerSecond'] = float(self.fps)
        data['customLayerData'] = self.customLayerData
        if self.exportMaterials:
            self.exportSharedMaterials(data)
        if self.sharedMeshes:
            self.exportSharedMeshes(data)
        self.exportCollections(data)
        for obj in self.objects:
            obj.exportUsd(data)
        return data
