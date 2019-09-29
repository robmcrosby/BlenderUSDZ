import bpy
import os
import subprocess
import tempfile
import shutil

#from io_scene_usdz.file_data import *
#from io_scene_usdz.scene_data import *
from io_scene_usdz.value_types import *

def export_usdz(context, filepath = '', materials = True, keepUSDA = False,
                bakeTextures = False, bakeAO = False, samples = 64,
                scale = 1.0, animated = False, useConverter = False,
                bakeSize = 1024):
    filePath, fileName = os.path.split(filepath)
    fileName, fileType = fileName.split('.')

    usdaFile = filePath+'/'+fileName+'.usda'
    usdcFile = filePath+'/'+fileName+'.usdc'
    usdzFile = filePath+'/'+fileName+'.usdz'

    """
    tempPath = None
    if not keepUSDA:
        tempPath = tempfile.mkdtemp()
        filePath = tempPath
        usdaFile = tempPath+'/'+fileName+'.usda'
        usdcFile = tempPath+'/'+fileName+'.usdc'

    scene = Scene()
    scene.exportMaterials = materials
    scene.exportPath = filePath
    scene.bakeAO = bakeAO
    scene.bakeTextures = bakeTextures
    scene.bakeSamples = samples
    scene.bakeSize = bakeSize
    scene.scale = scale
    scene.animated = animated
    scene.loadContext(context)

    if bakeTextures or bakeAO:
        scene.exportBakedTextures()

    # Export image files
    data = scene.exportFileData()

    if useConverter:
        # Crate text usda file and run the USDZ Converter Tool
        data.writeUsda(usdaFile)
        args = ['xcrun', 'usdz_converter', usdaFile, usdzFile]
        args += ['-v']
        subprocess.run(args)
    else:
        if keepUSDA:
            data.writeUsda(usdaFile)
        # Create Binary and Manually zip to a usdz file
        data.writeUsdc(usdcFile)
        usdz = UsdzFile(usdzFile)
        usdz.addFile(usdcFile)
        for textureFile in scene.textureFilePaths:
            usdz.addFile(textureFile)
        usdz.close()

    scene.cleanup()
    if tempPath != None:
        shutil.rmtree(tempPath)
    """

    usdData = UsdData()
    usdData['upAxis'] = 'Y'
    usdData['test'] = {
        'one':1,
        'boolean':True,
        'str':'test',
        'dict':{'one':1.0, 'two':(2.0, 3.0)}
    }
    testObj = usdData.createChild('obj', ClassType.Xform)
    testObj['att1'] = 1
    testObj['att1'].value = 2
    testObj['att2'] = UsdAttribute('', 'test', ValueType.string)
    testObj['att3'] = ValueType.Specifier
    testObj['att4'] = 'test'
    testObj['att4'].addQualifier('uniform')
    testObj['scales'] = ValueType.vec3f
    testObj['scales'].addTimeSample(1, [(4, 4, 4), (1, 1, 1), (1, 1, 1)])
    testObj['scales'].addTimeSample(2, [(4, 4, 4), (1, 1, 1), (1, 1, 1)])
    testObj['scales'].addTimeSample(3, [(4, 4, 4), (1, 1, 1), (1, 1, 1)])
    testMesh1 = testObj.createChild('mesh1', ClassType.Mesh)
    testMesh1['test'] = 'test'
    testMesh1['test'].addQualifier('uniform')
    testMesh1['indices'] = [1, 2, 3]
    testMesh1['points'] = [(1.0, 2.0), (3.0, 4.0)]
    testMesh2 = testObj.createChild('mesh2', ClassType.Mesh)
    testMesh2['test2'] = testMesh1['test']
    testMesh2['indices'] = [1, 2, 3]
    testMesh2['points'] = [(1.0, 2.0), (3.0, 4.0)]
    testMesh2['points']['interpolation'] = 'faceVarying'

    print(usdData)

    return {'FINISHED'}
