import bpy
import os
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


def exportMesh(obj, options):
    objCopy = copyObject(obj)

    # Create UV Map if not avalible
    if len(objCopy.data.uv_layers) == 0:
        bpy.ops.uv.smart_project()

    # Rotate to USD Coorinate Space
    objCopy.rotation_mode = 'XYZ'
    objCopy.rotation_euler = (-pi/2.0, 0.0, 0.0)
    bpy.ops.object.transform_apply(location = True, scale = True, rotation = True)

    indexedNormals = getIndexedNormals(objCopy.data)
    indexedUVs = getIndexedUVs(objCopy.data)

    mesh = {}
    mesh['name'] = obj.data.name.replace('.', '_')
    mesh['material'] = getObjectMaterialName(obj)
    mesh['extent'] = getObjectExtents(objCopy)
    mesh['faceVertexCounts'] = getFaceVertexCounts(objCopy.data)
    mesh['faceVertexIndices'] = getFaceVertexIndices(objCopy.data)
    mesh['points'] = getVertexPoints(objCopy.data)
    mesh['normalIndices'] = indexedNormals[0]
    mesh['normals'] = indexedNormals[1]
    mesh['uvIndices'] = indexedUVs[0]
    mesh['uvs'] = indexedUVs[1]

    deleteObject(objCopy)
    return mesh

def exportMeshes(objs, options):
    meshes = []
    for obj in objs:
        if obj.type == 'MESH':
            meshes.append(exportMesh(obj, options))
    selectObjects(objs)
    return meshes



################################################################################
##                         Export Material Methods                            ##
################################################################################

def getDefaultMaterial():
    mat = {}
    mat['name'] = defaultMaterialName
    mat['clearcoat'] = 0.0
    mat['clearcoatRoughness'] = 0.0
    mat['color'] = (0.0, 0.0, 0.0)
    mat['colorMap'] = None
    mat['displacement'] = 0.0
    mat['emissive'] = (0.0, 0.0, 0.0)
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
    mat['color'] = node.inputs['Base Color'].default_value[:3]
    mat['colorMap'] = exportInputImage(node.inputs['Base Color'], name+'_color.png', options)
    mat['metallic'] = node.inputs['Metallic'].default_value
    mat['metallicMap'] = exportInputImage(node.inputs['Metallic'], name+'_metallic.png', options)
    mat['roughness'] = node.inputs['Roughness'].default_value
    mat['roughnessMap'] = exportInputImage(node.inputs['Roughness'], name+'_roughness.png', options)
    mat['normalMap'] = exportInputImage(node.inputs['Normal'], name+'_normal.png', options)
    return mat

def exportDiffuseBSDF(node, name, options):
    mat = getDefaultMaterial()
    mat['color'] = node.inputs['Color'].default_value[:3]
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
    material['color'] = mat.diffuse_color[:]
    material['colorMap'] = extractInternalColorMap(mat, options)
    material['emissive'] = tuple([mat.emit*s for s in mat.diffuse_color[:]])
    material['normalMap'] = extractInternalNormalMap(mat, options)
    material['specular'] = mat.specular_color[:]
    return material


def exportMaterial(obj, options):
    mat = getObjectMaterial(obj)
    if mat != None:
        if mat.use_nodes:
            return exportCyclesMaterial(mat, options)
        return exportInternalMaterial(mat, options)
    return getDefaultMaterial()


def exportMaterials(objs, options):
    materialNames = set()
    materials = []
    for obj in objs:
        name = getObjectMaterialName(obj)
        if name not in materialNames:
            materialNames.add(name)
            materials.append(exportMaterial(obj, options))
    return materials



################################################################################
##                          USDA Export Methods                               ##
################################################################################

def printMesh(mesh, options):
    src = 'def Mesh "' + mesh['name'] + '"\n'
    src += '{\n'
    src += tab + 'float3[] extent = [' + printVectors(mesh['extent']) + ']\n'
    src += tab + 'int[] faceVertexCounts = [' + printIndices(mesh['faceVertexCounts']) + ']\n'
    src += tab + 'int[] faceVertexIndices = [' + printIndices(mesh['faceVertexIndices']) + ']\n'
    if options['exportMaterials']:
        src += tab + 'rel material:binding = </Materials/' + mesh['material'] + '>\n'
    src += tab + 'point3f[] points = [' + printVectors(mesh['points']) + ']\n'
    src += tab + 'normal3f[] primvars:normals = [' + printVectors(mesh['normals']) + '] (\n'
    src += tab + tab + 'interpolation = "vertex"\n' + tab + ')\n'
    src += tab + 'int[] primvars:normals:indices = [' + printIndices(mesh['normalIndices']) + ']\n'
    src += tab + 'texCoord2f[] primvars:Texture_uv = [' + printVectors(mesh['uvs']) + '] (\n'
    src += tab + tab + 'interpolation = "faceVarying"\n' + tab + ')\n'
    src += tab + 'int[] primvars:Texture_uv:indices = [' + printIndices(mesh['uvIndices']) + ']\n'
    src += tab + 'uniform token subdivisionScheme = "none"\n'
    src += '}\n'
    src += '\n'
    return src

def printMeshes(meshes, options):
    src = ''
    for mesh in meshes:
        src += printMesh(mesh, options)
    return src

def printPbrShader(mat):
    src = 2*tab + 'def Shader "pbr"\n'
    src += 2*tab + '{\n'
    src += 3*tab + 'uniform token info:id = "UsdPreviewSurface"\n'
    src += 3*tab + 'float inputs:clearcoat = %.6g\n' % mat['clearcoat']
    src += 3*tab + 'float inputs:clearcoatRoughness = %.6g\n' % mat['clearcoatRoughness']
    src += 3*tab + 'color3f inputs:diffuseColor.connect = </Materials/' + mat['name'] + '/color_map.outputs:rgb>\n'
    src += 3*tab + 'float inputs:displacement = %.6g\n' % mat['displacement']
    src += 3*tab + 'color3f inputs:emissiveColor.connect = </Materials/' + mat['name'] + '/emissive_map.outputs:rgb>\n'
    src += 3*tab + 'float inputs:ior = %.6g\n' % mat['ior']
    src += 3*tab + 'float inputs:metallic.connect = </Materials/' + mat['name'] + '/metallic_map.outputs:r>\n'
    src += 3*tab + 'normal3f inputs:normal.connect = </Materials/' + mat['name'] + '/normal_map.outputs:rgb>\n'
    src += 3*tab + 'float inputs:occlusion.connect = </Materials/' + mat['name'] + '/ao_map.outputs:r>\n'
    src += 3*tab + 'float inputs:opacity = %.6g\n' % mat['opacity']
    src += 3*tab + 'float inputs:roughness.connect = </Materials/' + mat['name'] + '/roughness_map.outputs:r>\n'
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

    src += printShaderTexture('color_map', name, mat['color']+(1,), 3, mat['colorMap']) + '\n'
    src += printShaderTexture('normal_map', name, (0.0, 0.0, 1.0, 1.0), 3, mat['normalMap']) + '\n'
    src += printShaderTexture('ao_map', name, (0, 0, 0, 1), 1, mat['occlusionMap']) + '\n'
    src += printShaderTexture('emissive_map', name, mat['emissive']+(1,), 3, mat['emissiveMap']) + '\n'
    src += printShaderTexture('metallic_map', name, (mat['metallic'],) + (0, 0, 1), 1, mat['metallicMap']) + '\n'
    src += printShaderTexture('roughness_map', name, (mat['roughness'],) + (0, 0, 1), 1, mat['roughnessMap'])

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

def writeUSDA(meshes, materials, options):
    usdaFile = options['tempPath'] + options['fileName'] + '.usda'
    src = '#usda 1.0\n'

    # Write Default Primitive
    src += '(\n'
    src += tab + 'defaultPrim = "' + meshes[0]['name'] + '"\n'
    src += ')\n\n'

    # Add the Meshes
    src += printMeshes(meshes, options)

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
            args += ['-m', '/Materials/' + mat['name']]
            if mat['colorMap'] != None:
                args += ['-color_map', mat['colorMap']]
            else:
                color = mat['color']
                r = '%.6g' % color[0]
                g = '%.6g' % color[1]
                b = '%.6g' % color[2]
                a = '1.0'
                args += ['-color_default', r, g, b, a]
            if mat['normalMap'] != None:
                args += ['-normal_map', mat['normalMap']]

    subprocess.run(args)



################################################################################
##                           USD Export Methods                               ##
################################################################################

def exportUSD(objects, options):

    # Create Temp Directory
    tempDir = tempfile.mkdtemp()
    options['tempPath'] = options['basePath']
    if options['fileType'] == 'usdz' and not options['keepUSDA']:
        options['tempPath'] = tempDir + '/'

    meshes = exportMeshes(objects, options)
    materials = exportMaterials(objects, options)

    writeUSDA(meshes, materials, options)
    writeUSDZ(materials, options)

    # Cleanup Temp Directory
    shutil.rmtree(tempDir)



################################################################################
##                         Export Interface Function                          ##
################################################################################

def export_usdz(context, filepath = '', exportMaterials = True, keepUSDA = False):
    filePath, fileName = os.path.split(filepath)
    fileName, fileType = fileName.split('.')

    if len(context.selected_objects) > 0 and context.active_object != None:
        options = {}
        options['basePath'] = filePath + '/'
        options['fileName'] = fileName
        options['fileType'] = 'usdz'
        options['exportMaterials'] = exportMaterials
        options['keepUSDA'] = keepUSDA

        objects = organizeObjects(bpy.context.active_object, bpy.context.selected_objects)
        exportUSD(objects, options)
    return {'FINISHED'}
