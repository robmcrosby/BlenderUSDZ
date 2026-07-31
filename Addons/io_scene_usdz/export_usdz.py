import bpy
import os
import zipfile
import tempfile
import shutil

from pathlib import Path
from io_scene_usdz.scene_data import Scene
from io_scene_usdz.value_types import pxrUsdAvailable, UsdData


def export_usdz(context, filepath = '', collection= '', exportMaterials = True,
                bakeTextures = False, bakeTextureSize = 1024, bakeDiffuse = True,
                bakeRoughness = True, bakeMetallic = True, bakeOpacity = False,
                bakeEmission = False, bakeNormals = False, bakeAO = False,
                bakeAOSamples = 64, useGpu = True, exportAnimations = False,
                globalScale = 1.0, debugMode = False,
                ):
  filepath = Path(filepath)
  
  # Create temporary directory
  tempDir = Path(tempfile.mkdtemp())
  
  # Create images directory in temporary
  imagesDir = tempDir / '0'
  imagesDir.mkdir(parents=True, exist_ok=True)
  
  scene = Scene()
  scene.exportMaterials = True
  scene.exportPath = str(imagesDir)
  scene.bakeTextures = bakeTextures
  scene.bakeSize = bakeTextureSize
  scene.bakeDiffuse = bakeDiffuse
  scene.bakeRoughness = bakeRoughness
  scene.bakeMetallic = bakeMetallic
  scene.bakeOpacity = bakeOpacity
  scene.bakeEmission = bakeEmission
  scene.bakeNormals = bakeNormals
  scene.bakeAO = bakeAO
  scene.bakeSamples = bakeAOSamples
  scene.device = 'GPU' if useGpu else 'CPU'
  scene.animated = exportAnimations
  scene.scale = globalScale
  scene.loadContext(context, collection)
  # Export image files
  if scene.bakeTextures:
    scene.exportBakedTextures()
  # Export the USD Data
  usdData = scene.exportUsd()
  # Cleanup the scene
  scene.cleanup()
  
  # Print if debug
  if debugMode:
    print(usdData.toString(debug=True))
  
  # Write the usd file
  usdExt = 'usda' if debugMode else 'usdc'
  usdPath = tempDir/f'{filepath.stem}.{usdExt}'
  usdData.writeUsd(str(usdPath))
  
  # Zip temp directory
  _write_zip(filepath, tempDir)
  
  # Cleanup temp directory
  shutil.rmtree(tempDir)
  return {'FINISHED'}


def _write_zip(filepath, dir):
  with zipfile.ZipFile(filepath, "w", zipfile.ZIP_STORED) as zipf:
    _add_to_zip(zipf, dir)


def _add_to_zip(zipf, dir, base=None, level=0):
  # Max 2 levels of directories
  if level > 2:
    return
  base = base if base else dir
  for root, dirs, files in dir.walk():
    for file in files:
      path = root/file
      zipf.write(path, path.relative_to(base))
    for dir in dirs:
      _add_to_zip(zipf, root/dir, base, level+1)
