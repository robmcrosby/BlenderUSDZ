import bpy
import os
import subprocess
import tempfile
import shutil


# Defines
tab = '    '
pi = 3.1415926



############################################################
#                    Helper Methods                        #
############################################################

# Returns Tuple as comma seprated string
def printTuple(t):
    return ', '.join('%.6g' % round(f, 6) for f in t)



############################################################
#                  Mesh Helper Methods                     #
############################################################

# Extracts the Normals from the Object
def getIndexedNormals(obj):
    indices = []
    normals = []
    for poly in obj.data.polygons:
        if poly.use_smooth:
            for i in poly.vertices:
                normal = obj.data.vertices[i].normal[:]
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

# Extracts the UVs from the Object
def getIndexedUVs(obj):
    indices = []
    uvs = []
    map = obj.data.uv_layers.active
    for point in map.data:
        uv = point.uv[:]
        if uv in uvs:
            indices += [uvs.index(uv)]
        else:
            indices += [len(uvs)]
            uvs.append(uv)
    return (indices, uvs)



############################################################
#              USDA Geometry Export Methods                #
############################################################

# Prints the Object's bounds
def printBounds(obj):
    low = obj.bound_box[0][:]
    high = obj.bound_box[0][:]
    for v in obj.bound_box:
        low = min(low, v[:])
        high = max(high, v[:])
    low = printTuple(low)
    high = printTuple(high)
    return tab + 'float3[] extent = [(' + low + '), (' + high + ')]\n'

# Prints Face Vertex Counts of the Faces of the given Object
def printFaceVertexCounts(obj):
    src = tab + 'int[] faceVertexCounts = ['
    src += ', '.join(format(len(p.vertices), 'd') for p in obj.data.polygons)
    return src + ']\n'

# Prints Face Vertex Indices
def printFaceVertexIndices(obj):
    indices = []
    for poly in obj.data.polygons:
        indices += [i for i in poly.vertices]
    src = tab + 'int[] faceVertexIndices = ['
    src += ', '.join(format(i, 'd') for i in indices)
    return src + ']\n'

# Prints Normals and Normal Indices for the given Object
def printNormals(obj):
    normals = getIndexedNormals(obj)
    src = tab + 'normal3f[] primvars:normals = ['
    src += ', '.join('(' + printTuple(n) + ')' for n in normals[1])
    src += '] (\n' + tab + tab + 'interpolation = "vertex"\n' + tab + ')\n'
    src += tab + 'int[] primvars:normals:indices = ['
    src += ', '.join(format(i, 'd') for i in normals[0])
    return src + ']\n'

# Prints UVs and UV Indices for the given Object
def printUVs(obj):
    uvs = getIndexedUVs(obj)
    src = tab + 'texCoord2f[] primvars:Texture_uv = ['
    src += ', '.join('(' + printTuple(uv) + ')' for uv in uvs[1])
    src += '] (\n' + tab + tab + 'interpolation = "faceVarying"\n' + tab + ')\n'
    src += tab + 'int[] primvars:Texture_uv:indices = ['
    src += ', '.join(format(i, 'd') for i in uvs[0])
    src += ']\n'
    return src

# Prints the Vertex Points for the given Object
def printVertexPoints(obj):
    src = tab + 'point3f[] points = ['
    src += ', '.join('(' + printTuple(v.co[:]) + ')' for v in obj.data.vertices)
    return src + ']\n'

# Prints a Mesh Object
def printMeshObject(obj, name):
    # Define Object
    src = 'def Mesh "' + name + '"\n'
    src += '{\n'
    src += printBounds(obj)
    src += printFaceVertexCounts(obj)
    src += printFaceVertexIndices(obj)
    src += printVertexPoints(obj)
    src += printNormals(obj)
    if len(obj.data.uv_layers) > 0:
        src += printUVs(obj)
    src += tab + 'uniform token subdivisionScheme = "none"\n'
    src += '}\n'
    src += '\n'
    return src





############################################################
#                    USDA Export Method                    #
############################################################

def exportUSDA(filePath, fileName):
    usdaFile = filePath + fileName + '.usda'
    src = '#usda 1.0\n'
    
    activeObj = bpy.context.active_object
    defName = activeObj.name.replace('.', '_')
    
    # Write Default Object
    src += '(\n'
    src += tab + 'defaultPrim = "' + defName + '"\n'
    src += ')\n\n'
    
    # Write the Objects
    objects = bpy.context.selected_objects
    for obj in objects:
        objName = obj.name.replace('.', '_')
        
        # deselect all but the one Object
        bpy.ops.object.select_all(action='DESELECT')
        obj.select = True
        
        #Duplicate the selected Object
        bpy.ops.object.duplicate()
        objCopy = bpy.context.active_object
        
        #exportImageFiles(filePath, objCopy, objects)
        
        # deselect all but the one Object
        bpy.ops.object.select_all(action='DESELECT')
        objCopy.select = True
        
        #Rotate to USD Coorinate Space
        objCopy.rotation_mode = 'XYZ'
        objCopy.rotation_euler = (-pi/2.0, 0.0, 0.0)
        bpy.ops.object.transform_apply(location = True, scale = True, rotation = True)
        
        src += printMeshObject(objCopy, objName)
        
        #Delete the Duplicated Object
        bpy.ops.object.select_all(action='DESELECT')
        objCopy.select = True
        bpy.ops.object.delete()
        
    # Write the Materials
    #src += printMaterial()
    
    # Write to file
    f = open(usdaFile, 'w')
    f.write(src)
    f.close()
    
    # Re-select the Objects
    for obj in objects:
        obj.select = True
    bpy.context.scene.objects.active = activeObj


############################################################
#                      Object Methods                      #
############################################################

def getObjectNames(objs):
    return [obj.name.replace('.', '_') for obj in objs]

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

def joinObjects(objs):
    if len(objs) > 1:
        selectObjects(objs)
        bpy.ops.object.join()
        return bpy.context.active_object
    return objs[0]


def writeUSDA(options):
    usdaFile = options['tempPath'] + options['fileName'] + '.usda'
    
    src = '#usda 1.0\n'
    
    activeObj = bpy.context.active_object
    defName = activeObj.name.replace('.', '_')
    
    objs = options['objects']
    
    # Write Default Object
    src += '(\n'
    src += tab + 'defaultPrim = "' + options['objectNames'][0] + '"\n'
    src += ')\n\n'
    
    # Write the Objects
    for t in enumerate(objs):
        obj = t[1]
        objName = options['objectNames'][t[0]]
        objCopy = copyObject(obj)
        
        # Create UV Map if not avalible
        if len(objCopy.data.uv_layers) == 0:
            bpy.ops.uv.smart_project()
        
        # Rotate to USD Coorinate Space
        objCopy.rotation_mode = 'XYZ'
        objCopy.rotation_euler = (-pi/2.0, 0.0, 0.0)
        bpy.ops.object.transform_apply(location = True, scale = True, rotation = True)
        
        # Print Object to File Source and Cleanup 
        src += printMeshObject(objCopy, objName)    
        deleteObject(objCopy)
    
    # Write to file
    f = open(usdaFile, 'w')
    f.write(src)
    f.close()

def writeUSDZ(options):
    usdaFile = options['tempPath'] + options['fileName'] + '.usda'
    usdzFile = options['basePath'] + options['fileName'] + '.usdz'
    args = ['xcrun', 'usdz_converter', usdaFile, usdzFile]
    subprocess.run(args)


def exportUSD(options):
    tempDir = tempfile.mkdtemp()
    options['tempPath'] = options['basePath']
    if options['fileType'] == 'usdz' and not options['keepUSDA']:
        options['tempPath'] = tempDir + '/'
        
    objs = options['objects']
    options['objects'] = copyObjects(objs)
    if options['joinObjects'] and len(objs) > 1:
        obj = joinObjects(options['objects'])
        selectObject(obj)
        bpy.ops.uv.smart_project()
        options['objects'] = [obj]
    writeUSDA(options)
    deleteObjects(options['objects'])
    selectObjects(objs)
    
    if options['fileType'] == 'usdz':
        writeUSDZ(options)
    shutil.rmtree(tempDir)



################################################################################
##                         Export Interface Function                          ##
################################################################################

def export_usdz(context, filepath = '', joinObjects = True, keepUSDA = False):
    filePath, fileName = os.path.split(filepath)
    fileName, fileType = fileName.split('.')
    
    if len(context.selected_objects) > 0 and context.active_object != None:
        options = {}
        options['basePath'] = filePath + '/'
        options['fileName'] = fileName
        options['fileType'] = 'usdz'
        options['objects'] = organizeObjects(bpy.context.active_object, bpy.context.selected_objects)
        options['objectNames'] = getObjectNames(options['objects'])
        options['joinObjects'] = joinObjects
        options['exportUVs'] = True
        options['keepUSDA'] = keepUSDA
        exportUSD(options)
    return {'FINISHED'}
