import bpy
import os
import mathutils
import subprocess
import tempfile
import shutil


# Defines
tab = '    '
pi = 3.1415926
defaultMaterialName = 'DefaultMaterial'



################################################################################
##                             Helper Methods                                 ##
################################################################################

# Returns Tuple as comma seprated string
def printTuple(t):
    return ', '.join('%.6g' % round(f, 6) for f in t)

def printIndices(indices):
    return ', '.join(format(i, 'd') for i in indices)

def printVectors(vectors):
    return ', '.join('(' + printTuple(v) + ')' for v in vectors)



################################################################################
##                          Object Helper Methods                             ##
################################################################################

def organizeObjects(active, objs):
    objs.remove(active)
    return [active] + objs


def copyObject(obj):
    selectObject(obj)
    bpy.ops.object.duplicate()
    return bpy.context.active_object


def copyObjects(objs):
    return [copyObject(obj) for obj in objs]


def selectObject(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select = True
    bpy.context.scene.objects.active = obj


def selectObjects(objs):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objs:
        obj.select = True
    bpy.context.scene.objects.active = objs[0]


def deleteObject(obj):
    selectObject(obj)
    bpy.ops.object.delete()


def deleteObjects(objs):
    for obj in objs:
        deleteObject(obj)


def getObjectMaterial(obj):
    if obj.type == 'MESH' and len(obj.data.materials) > 0:
        return obj.data.materials[0]
    return None


def getObjectMaterialName(obj):
    mat = getObjectMaterial(obj)
    if mat != None:
        return mat.name.replace('.', '_')
    return defaultMaterialName


def saveImage(img, filePath):
    # Store current render settings
    settings = bpy.context.scene.render.image_settings
    format = settings.file_format
    mode = settings.color_mode
    depth = settings.color_depth
    
    # Change render settings to our target format
    settings.file_format = 'PNG'
    settings.color_mode = 'RGBA'
    settings.color_depth = '8'
    
    # Save the image
    img.save_render(filePath)
    
    # Restore previous render settings
    settings.file_format = format
    settings.color_mode = mode
    settings.color_depth = depth


def createImage(name, width, height, file):
    bpy.ops.image.new(name=name, width=width, height=height)
    image = bpy.data.images[name]
    image.use_alpha = True
    image.alpha_mode = 'STRAIGHT'
    image.filepath_raw = file
    image.file_format = 'PNG'
    return image

################################################################################
##                           Export Mesh Methods                              ##
################################################################################


def getObjectExtents(obj):
    low = obj.bound_box[0][:]
    high = obj.bound_box[0][:]
    for v in obj.bound_box:
        low = min(low, v[:])
        high = max(high, v[:])
    return [low, high]


def getFaceVertexCounts(mesh):
    return [len(p.vertices) for p in mesh.polygons]


def getFaceVertexIndices(mesh):
    indices = []
    for poly in mesh.polygons:
        indices += [i for i in poly.vertices]
    return indices


def getVertexPoints(mesh):
    return [v.co[:] for v in mesh.vertices]


def getIndexedNormals(mesh):
    indices = []
    normals = []
    for poly in mesh.polygons:
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


def getIndexedUVs(mesh):
    indices = []
    uvs = []
    map = mesh.uv_layers.active
    for point in map.data:
        uv = point.uv[:]
        if uv in uvs:
            indices += [uvs.index(uv)]
        else:
            indices += [len(uvs)]
            uvs.append(uv)
    return (indices, uvs)


def exportMeshes(obj, options):
    objCopy = copyObject(obj)
    
    # Create UV Map if not avalible
    if len(objCopy.data.uv_layers) == 0:
        bpy.ops.uv.smart_project()
    
    # Rotate to USD Coorinate Space
    #objCopy.rotation_mode = 'XYZ'
    #objCopy.rotation_euler = (-pi/2.0, 0.0, 0.0)
    #bpy.ops.object.transform_apply(location = True, scale = True, rotation = True)
    
    name = obj.data.name.replace('.', '_')
    multiMat = len(obj.material_slots) > 1
    
    # Seperate the Mesh by Material
    objs = [objCopy]
    if multiMat:
        bpy.ops.mesh.separate(type='MATERIAL')
        objs = bpy.context.selected_objects
    
    meshes = []
    for obj in objs:
        indexedNormals = getIndexedNormals(obj.data)
        indexedUVs = getIndexedUVs(obj.data)
    
        mesh = {}
        mesh['name'] = name
        mesh['material'] = getObjectMaterialName(obj)
        mesh['extent'] = getObjectExtents(obj)
        mesh['faceVertexCounts'] = getFaceVertexCounts(obj.data)
        mesh['faceVertexIndices'] = getFaceVertexIndices(obj.data)
        mesh['points'] = getVertexPoints(obj.data)
        mesh['normalIndices'] = indexedNormals[0]
        mesh['normals'] = indexedNormals[1]
        mesh['uvIndices'] = indexedUVs[0]
        mesh['uvs'] = indexedUVs[1]
        
        if multiMat:
            mesh['name'] += '_' + mesh['material']
        deleteObject(obj)
        meshes.append(mesh)
    return meshes

def exportMatrix(matrix):
    matrix = mathutils.Matrix.transposed(matrix)
    return [col[:] for col in matrix[:]]

def exportRootMatrix(matrix, options):
    scale = mathutils.Matrix.Scale(options['scale'], 4)
    rotation = mathutils.Matrix.Rotation(-pi/2.0, 4, 'X')
    return exportMatrix(rotation * scale * matrix)

def exportObject(obj, options):
    object = {}
    object['name'] = obj.name.replace('.', '_')
    object['type'] = 'static'
    object['meshes'] = exportMeshes(obj, options)
    object['matrix'] = exportRootMatrix(obj.matrix_world, options)
    return object

def exportObjects(objs, options):
    objects = []
    for obj in objs:
        if obj.type == 'MESH':
            objects.append(exportObject(obj, options))
    selectObjects(objs)
    return objects


################################################################################
##                         Export Material Methods                            ##
################################################################################

def getDefaultMaterial():
    mat = {}
    mat['name'] = defaultMaterialName
    mat['clearcoat'] = 0.0
    mat['clearcoatRoughness'] = 0.0
    mat['color'] = (0.0, 0.0, 0.0, 1.0)
    mat['colorMap'] = None
    mat['displacement'] = 0.0
    mat['emissive'] = (0.0, 0.0, 0.0, 1.0)
    mat['emissiveMap'] = None
    mat['ior'] = 1.5
    mat['metallic'] = 0.0
    mat['metallicMap'] = None
    mat['normalMap'] = None
    mat['occlusionMap'] = None
    mat['opacity'] = 1.0
    mat['roughness'] = 0.0
    mat['roughnessMap'] = None
    mat['specular'] = (1.0, 1.0, 1.0)
    mat['specularWorkflow'] = False
    return mat


def getOutputMaterialNode(mat):
    for node in mat.node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL':
            return node
    return None

def getSurfaceShaderNode(mat):
    node = getOutputMaterialNode(mat)
    if node != None and 'Surface' in node.inputs.keys() and node.inputs['Surface'].is_linked:
        return node.inputs['Surface'].links[0].from_node
    return None

def exportInputImage(input, fileName, options):
    if input.is_linked and len(input.links) > 0:
        for link in input.links:
            node = link.from_node
            if node.type == 'TEX_IMAGE' and node.image != None:
                filePath = options['tempPath'] + fileName
                saveImage(node.image, filePath)
                return fileName
    return None

def exportPrincipledBSDF(node, name, options):
    mat = getDefaultMaterial()
    mat['name'] = name
    mat['clearcoat'] = node.inputs['Clearcoat'].default_value
    mat['clearcoatRoughness'] = node.inputs['Clearcoat Roughness'].default_value
    mat['color'] = node.inputs['Base Color'].default_value[:]
    mat['colorMap'] = exportInputImage(node.inputs['Base Color'], name+'_color.png', options)
    mat['metallic'] = node.inputs['Metallic'].default_value
    mat['metallicMap'] = exportInputImage(node.inputs['Metallic'], name+'_metallic.png', options)
    mat['ior'] = node.inputs['IOR'].default_value
    mat['roughness'] = node.inputs['Roughness'].default_value
    mat['roughnessMap'] = exportInputImage(node.inputs['Roughness'], name+'_roughness.png', options)
    mat['normalMap'] = exportInputImage(node.inputs['Normal'], name+'_normal.png', options)
    return mat

def exportDiffuseBSDF(node, name, options):
    mat = getDefaultMaterial()
    mat['name'] = name
    mat['color'] = node.inputs['Color'].default_value[:]
    mat['colorMap'] = exportInputImage(node.inputs['Color'], name+'_color.png', options)
    mat['roughness'] = node.inputs['Roughness'].default_value
    mat['roughnessMap'] = exportInputImage(node.inputs['Roughness'], name+'_roughness.png', options)
    mat['normalMap'] = exportInputImage(node.inputs['Normal'], name+'_normal.png', options)
    return mat

def exportCyclesMaterial(material, options):
    mat = getDefaultMaterial()
    node = getSurfaceShaderNode(material)
    if node != None:
        if node.type == 'BSDF_PRINCIPLED':
            mat = exportPrincipledBSDF(node, material.name, options)
        elif node.type == 'BSDF_DIFFUSE':
            mat = exportDiffuseBSDF(node, material.name, options)
    mat['name'] = material.name
    return mat


def extractInternalColorMap(mat, options):
    for slot in mat.texture_slots:
        if slot != None and slot.use_map_color_diffuse and slot.texture.type == 'IMAGE' and slot.texture.image != None:
            fileName = mat.name.replace('.', '_') + '_color.png'
            filePath = options['tempPath'] + fileName
            saveImage(slot.texture.image, filePath)
            return fileName
    return None


def extractInternalNormalMap(mat, options):
    for slot in mat.texture_slots:
        if slot != None and slot.use_map_normal and slot.texture.type == 'IMAGE' and slot.texture.image != None:
            fileName = mat.name.replace('.', '_') + '_normal.png'
            filePath = options['tempPath'] + fileName
            saveImage(slot.texture.image, filePath)
            return fileName
    return None


def exportInternalMaterial(mat, options):
    material = getDefaultMaterial()
    material['name'] = mat.name.replace('.', '_')
    material['color'] = mat.diffuse_color[:] + (1.0,)
    material['colorMap'] = extractInternalColorMap(mat, options)
    material['emissive'] = tuple([mat.emit*s for s in mat.diffuse_color[:]]) + (1.0,)
    material['normalMap'] = extractInternalNormalMap(mat, options)
    material['specular'] = mat.specular_color[:]
    return material


def bakeAO(obj, file, options):
    if len(obj.data.uv_textures) > 0:
        # Create an image
        img = createImage('export_ao', 1024, 1024, options['tempPath'] + file)
        selectObject(obj)
    
        # Set the UV coordinates
        obj.data.uv_textures[0].active = True
        for d in obj.data.uv_textures[0].data:
            d.image = img
    
        bpy.data.scenes["Scene"].render.bake_margin = 4
        bpy.data.scenes["Scene"].render.bake_type = "AO"
        bpy.data.worlds["World"].light_settings.use_ambient_occlusion = True
        bpy.data.worlds["World"].light_settings.samples = options['samples']
        bpy.ops.object.bake_image()
        img.save()
        
        # Cleanup
        for d in obj.data.uv_textures[0].data:
            d.image = None
        bpy.data.images.remove(img)
        
        return file
    return None


def exportMaterial(mat, options):
    if mat != None:
        if mat.use_nodes:
            return exportCyclesMaterial(mat, options)
        return exportInternalMaterial(mat, options)
    return getDefaultMaterial()


def exportMaterials(objs, options):
    materialNames = set()
    materials = []
    
    for obj in objs:
        if obj.type == 'MESH' and len(obj.data.materials) > 0:
            aoMap = None
            if options['bakeAO']:
                aoFile = obj.data.materials[0].name.replace('.', '_') + '_ao.png'
                aoMap = bakeAO(obj, aoFile, options)
            
            for mat in obj.data.materials:
                if mat != None:
                    name = mat.name.replace('.', '_')
                    if not name in materialNames:
                        materialNames.add(name)
                        materials.append(exportMaterial(mat, options))
                        materials[-1]['occlusionMap'] = aoMap
    if len(materials) == 0:
        materials.append(getDefaultMaterial())
    return materials



################################################################################
##                          USDA Export Methods                               ##
################################################################################

def printMesh(mesh, options):
    src = tab + 'def Mesh "' + mesh['name'] + '"\n'
    src += tab + '{\n'
    src += 2*tab + 'float3[] extent = [' + printVectors(mesh['extent']) + ']\n'
    src += 2*tab + 'int[] faceVertexCounts = [' + printIndices(mesh['faceVertexCounts']) + ']\n'
    src += 2*tab + 'int[] faceVertexIndices = [' + printIndices(mesh['faceVertexIndices']) + ']\n'
    if options['exportMaterials']:
        src += 2*tab + 'rel material:binding = </Materials/' + mesh['material'] + '>\n'
    src += 2*tab + 'point3f[] points = [' + printVectors(mesh['points']) + ']\n'
    src += 2*tab + 'normal3f[] primvars:normals = [' + printVectors(mesh['normals']) + '] (\n'
    src += 2*tab + tab + 'interpolation = "vertex"\n' + tab + ')\n'
    src += 2*tab + 'int[] primvars:normals:indices = [' + printIndices(mesh['normalIndices']) + ']\n'
    src += 2*tab + 'texCoord2f[] primvars:Texture_uv = [' + printVectors(mesh['uvs']) + '] (\n'
    src += 2*tab + tab + 'interpolation = "faceVarying"\n' + tab + ')\n'
    src += 2*tab + 'int[] primvars:Texture_uv:indices = [' + printIndices(mesh['uvIndices']) + ']\n'
    src += 2*tab + 'uniform token subdivisionScheme = "none"\n'
    src += tab + '}\n'
    src += tab + '\n'
    return src

def printMeshes(meshes, options):
    src = ''
    for mesh in meshes:
        src += printMesh(mesh, options)
    return src

def printMatrix(mtx):
    return 'custom matrix4d xformOp:transform = (' + printVectors(mtx) + ')'

def printObject(obj, options):
    src = 'def Xform "' + obj['name'] + '"\n'
    src += '{\n'
    src += tab + printMatrix(obj['matrix']) + '\n'
    src += tab + 'uniform token[] xformOpOrder = ["xformOp:transform"]\n'
    src += tab + '\n'
    src += printMeshes(obj['meshes'], options)
    src += '}\n\n'
    return src

def printObjects(objs, options):
    src = ''
    for obj in objs:
        src += printObject(obj, options)
    return src


def printPbrShader(mat):
    src = 2*tab + 'def Shader "pbr"\n'
    src += 2*tab + '{\n'
    src += 3*tab + 'uniform token info:id = "UsdPreviewSurface"\n'
    src += 3*tab + 'float inputs:clearcoat = %.6g\n' % mat['clearcoat']
    src += 3*tab + 'float inputs:clearcoatRoughness = %.6g\n' % mat['clearcoatRoughness']
    
    if mat['colorMap'] == None:
        src += 3*tab + 'color3f inputs:diffuseColor = (' + printTuple(mat['color'][:3]) + ')\n'
    else:
        src += 3*tab + 'color3f inputs:diffuseColor.connect = </Materials/' + mat['name'] + '/color_map.outputs:rgb>\n'
    
    if mat['emissiveMap'] == None:
        src += 3*tab + 'color3f inputs:emissiveColor = (' + printTuple(mat['emissive'][:3]) + ')\n'
    else:
        src += 3*tab + 'color3f inputs:emissiveColor.connect = </Materials/' + mat['name'] + '/emissive_map.outputs:rgb>\n'
    
    src += 3*tab + 'float inputs:displacement = %.6g\n' % mat['displacement']
    src += 3*tab + 'float inputs:ior = %.6g\n' % mat['ior']
    
    if mat['metallicMap'] == None:
        src += 3*tab + 'float inputs:metallic = %.6g\n' % mat['metallic']
    else:
        src += 3*tab + 'float inputs:metallic.connect = </Materials/' + mat['name'] + '/metallic_map.outputs:r>\n'
    
    if mat['normalMap'] == None:
        src += 3*tab + 'normal3f inputs:normal = (0, 0, 1)\n'
    else:
        src += 3*tab + 'normal3f inputs:normal.connect = </Materials/' + mat['name'] + '/normal_map.outputs:rgb>\n'
    
    if mat['occlusionMap'] == None:
        src += 3*tab + 'float inputs:occlusion = 0\n'
    else:
        src += 3*tab + 'float inputs:occlusion.connect = </Materials/' + mat['name'] + '/ao_map.outputs:r>\n'
    
    if mat['roughnessMap'] == None:
        src += 3*tab + 'float inputs:roughness = %.6g\n' % mat['roughness']
    else:
        src += 3*tab + 'float inputs:roughness.connect = </Materials/' + mat['name'] + '/roughness_map.outputs:r>\n'
    
    src += 3*tab + 'float inputs:opacity = %.6g\n' % mat['opacity']
    src += 3*tab + 'color3f inputs:specularColor = (' + printTuple(mat['specular']) + ')\n'
    src += 3*tab + 'int inputs:useSpecularWorkflow = %i\n' % int(mat['specularWorkflow'])
    src += 3*tab + 'token outputs:displacement\n'
    src += 3*tab + 'token outputs:surface\n'
    src += 2*tab + '}\n'
    src += 2*tab + '\n'
    return src

def printShaderPrimvar(name):
    src = 2*tab + 'def Shader "Primvar"\n'
    src += 2*tab + '{\n'
    src += 3*tab + 'uniform token info:id = "UsdPrimvarReader_float2"\n'
    src += 3*tab + 'float2 inputs:default = (0, 0)\n'
    src += 3*tab + 'token inputs:varname.connect = </Materials/' + name + '.inputs:frame:stPrimvarName>\n'
    src += 3*tab + 'float2 outputs:result\n'
    src += 2*tab + '}\n'
    src += 2*tab + '\n'
    return src

def printShaderTexture(compName, matName, default, comps, file):
    src = 2*tab + 'def Shader "' + compName + '"\n' 
    src += 2*tab + '{\n'
    src += 3*tab + 'uniform token info:id = "UsdUVTexture"\n'
    src += 3*tab + 'float4 inputs:default = (' + printTuple(default) + ')\n'
    if file != None:
        src += 3*tab + 'asset inputs:file = @' + file + '@\n'
    src += 3*tab + 'float2 inputs:st.connect = </Materials/' + matName + '/Primvar.outputs:result>\n'
    src += 3*tab + 'token inputs:wrapS = "repeat"\n'
    src += 3*tab + 'token inputs:wrapT = "repeat"\n'
    if comps == 3:
        src += 3*tab + 'float3 outputs:rgb\n'
    else:
        src += 3*tab + 'float outputs:r\n'
    src += 2*tab + '}\n'
    return src

def printMaterial(mat, options):
    name = mat['name']
    
    src = tab + 'def Material "' + name + '"\n' + tab + '{\n'
    
    src += 2*tab + 'token inputs:frame:stPrimvarName = "Texture_uv"\n'
    src += 2*tab + 'token outputs:displacement.connect = </Materials/' + name + '/pbr.outputs:displacement>\n'
    src += 2*tab + 'token outputs:surface.connect = </Materials/' + name + '/pbr.outputs:surface>\n'
    src += 2*tab + '\n'
    
    src += printPbrShader(mat)
    src += printShaderPrimvar(name)
    
    if mat['colorMap'] != None:
        src += printShaderTexture('color_map', name, mat['color'], 3, mat['colorMap']) + '\n'
    if mat['normalMap'] != None:
        src += printShaderTexture('normal_map', name, (0, 0, 1, 1), 3, mat['normalMap']) + '\n'
    if mat['occlusionMap'] != None:
        src += printShaderTexture('ao_map', name, (0, 0, 0, 1), 1, mat['occlusionMap']) + '\n'
    if mat['emissiveMap'] != None:
        src += printShaderTexture('emissive_map', name, mat['emissive'], 3, mat['emissiveMap']) + '\n'
    if mat['metallicMap'] != None:
        src += printShaderTexture('metallic_map', name, (mat['metallic'], mat['metallic'], mat['metallic'], 1.0), 1, mat['metallicMap']) + '\n'
    if mat['roughnessMap'] != None:
        src += printShaderTexture('roughness_map', name, (mat['roughness'], mat['roughness'], mat['roughness'], 1.0), 1, mat['roughnessMap'])
    
    src += tab + '}\n' + tab + '\n'
    return src

def printMaterials(materials, options):
    src = ''
    if options['exportMaterials'] and len(materials) > 0:
        src += 'def "Materials"\n{\n'
        for material in materials:
            src += printMaterial(material, options)
        src += '}\n\n'
    return src

def writeUSDA(objs, materials, options):
    usdaFile = options['tempPath'] + options['fileName'] + '.usda'
    src = '#usda 1.0\n'
    
    #Add the Objects
    src += printObjects(objs, options)
    
    # Add the Materials
    src += printMaterials(materials, options)
    
    # Write to file
    f = open(usdaFile, 'w')
    f.write(src)
    f.close()



################################################################################
##                          USDZ Export Methods                               ##
################################################################################

def writeUSDZ(materials, options):
    usdaFile = options['tempPath'] + options['fileName'] + '.usda'
    usdzFile = options['basePath'] + options['fileName'] + '.usdz'
    
    args = ['xcrun', 'usdz_converter', usdaFile, usdzFile]
    args += ['-v']
    
    if options['exportMaterials']:
        for mat in materials:
            mArgs = []
            if mat['colorMap'] != None:
                mArgs += ['-color_map', mat['colorMap']]
            if mat['normalMap'] != None:
                mArgs += ['-normal_map', mat['normalMap']]
            if mat['occlusionMap'] != None:
                mArgs += ['-ao_map', mat['occlusionMap']]
            # Add Material Arguments if any
            if len(mArgs) > 0:
                args += ['-m', '/Materials/' + mat['name']] + mArgs 
    subprocess.run(args)



################################################################################
##                           USD Export Methods                               ##
################################################################################

def exportUSD(objs, options):
    
    # Create Temp Directory
    tempDir = tempfile.mkdtemp()
    options['tempPath'] = options['basePath']
    if options['fileType'] == 'usdz' and not options['keepUSDA']:
        options['tempPath'] = tempDir + '/'
    
    #meshes = exportMeshes(objs, options)
    objects = exportObjects(objs, options)
    materials = exportMaterials(objs, options)
    
    #writeUSDA(meshes, materials, options)
    writeUSDA(objects, materials, options)
    writeUSDZ(materials, options)
    
    # Cleanup Temp Directory
    shutil.rmtree(tempDir)



################################################################################
##                         Export Interface Function                          ##
################################################################################

def export_usdz(context, filepath = '', exportMaterials = True, keepUSDA = False, bakeAO = False, samples = 8, scale = 1.0):
    filePath, fileName = os.path.split(filepath)
    fileName, fileType = fileName.split('.')
    
    if len(context.selected_objects) > 0 and context.active_object != None:
        options = {}
        options['basePath'] = filePath + '/'
        options['fileName'] = fileName
        options['fileType'] = 'usdz'
        options['exportMaterials'] = exportMaterials
        options['keepUSDA'] = keepUSDA
        options['bakeAO'] = bakeAO
        options['samples'] = samples
        options['scale'] = scale
        
        objects = organizeObjects(bpy.context.active_object, bpy.context.selected_objects)
        exportUSD(objects, options)
    return {'FINISHED'}
