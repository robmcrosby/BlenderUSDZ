import bpy
import os
import subprocess
import tempfile
import shutil
import time

try:
    import zlib
    crc32 = zlib.crc32
except ImportError:
    crc32 = binascii.crc32

from io_scene_usdz.scene_data import *
from io_scene_usdz.value_types import *
from io_scene_usdz.crate_file import *

def export_usdz(context, filepath = '', exportMaterials = True,
                bakeTextures = False, bakeTextureSize = 1024, bakeAO = False,
                bakeAOSamples = 64, exportAnimations = False,
                globalScale = 1.0, useConverter = False,
                ):
    exportDir, fileName = os.path.split(filepath)
    fileParts = fileName.split('.')
    fileName = fileParts[0] if len(fileParts) > 0 else 'file'
    fileType = fileParts[1] if len(fileParts) > 1 else 'usdz'
    filePath = exportDir + '/' + fileName + '.' + fileType
    tempDir = None
    if not fileType in ('usda', 'usdc'):
        tempDir = tempfile.mkdtemp()
        exportDir = tempDir
    usdData, texturePaths = exportUsdData(context = context,
                                          exportMaterials = exportMaterials,
                                          exportDir = exportDir,
                                          bakeTextures = bakeTextures,
                                          bakeTextureSize = bakeTextureSize,
                                          bakeAO = bakeAO,
                                          bakeAOSamples = bakeAOSamples,
                                          exportAnimations = exportAnimations,
                                          globalScale = globalScale)
    if fileType == 'usda':
        usdData.writeUsda(filePath)
    elif fileType == 'usdc':
        writeCrateFile(filePath, usdData)
    else:
        if useConverter:
            # Crate text usda file and run the USDZ Converter Tool
            usdaPath = tempDir + '/' + fileName + '.usda'
            usdData.writeUsda(usdaPath)
            convertToUsdz(filePath, usdaPath)
        else:
            # Create Binary and Manually zip to a usdz file
            usdcPath = tempDir + '/' + fileName + '.usdc'
            writeCrateFile(usdcPath, usdData)
            writeUsdzFile(filePath, usdcPath, texturePaths)
    if tempDir != None:
        # Cleanup the Temp Directory
        shutil.rmtree(tempDir)
    return {'FINISHED'}


def exportUsdData(context, exportMaterials, exportDir, bakeTextures,
                  bakeTextureSize, bakeAO, bakeAOSamples, exportAnimations,
                  globalScale):
    scene = Scene()
    scene.exportMaterials = exportMaterials
    scene.exportPath = exportDir
    scene.bakeTextures = bakeTextures
    scene.bakeSize = bakeTextureSize
    scene.bakeAO = bakeAO
    scene.bakeSamples = bakeAOSamples
    scene.animated = exportAnimations
    scene.scale = globalScale
    scene.loadContext(context)
    # Export image files
    if scene.bakeTextures:
        scene.exportBakedTextures()
    # Export the USD Data
    usdData = scene.exportUsd()
    texturePaths = scene.textureFilePaths
    # Cleanup the scene
    scene.cleanup()
    return usdData, texturePaths


def convertToUsdz(filePath, usdaPath):
    args = ['xcrun', 'usdz_converter', usdaPath, filePath]
    args += ['-v']
    subprocess.run(args)


def writeUsdzFile(filePath, usdcPath, texturePaths):
    usdz = UsdzFile(filePath)
    usdz.addFile(usdcPath)
    for texturePath in texturePaths:
        usdz.addFile(texturePath)
    usdz.close()


def writeCrateFile(filePath, usdData):
    crateFile = open(filePath, 'wb')
    crate = CrateFile(crateFile)
    crate.writeUsd(usdData)
    crateFile.close()


def readFileContents(filePath):
    file = open(filePath, 'rb')
    contents = file.read()
    file.close()
    return contents


class UsdzFile:
    def __init__(self, filePath):
        self.file = open(filePath, 'wb')
        self.entries = []
        self.cdOffset = 0
        self.cdLength = 0

    def getExtraAlignmentSize(self, name):
        return 64 - ((self.file.tell() + 30 + len(name) + 4) % 64)

    def addFile(self, filePath):
        contents = readFileContents(filePath)
        entry = {}
        entry['name'] = os.path.basename(filePath)
        # File offset and crc32 hash
        entry['offset'] = self.file.tell()
        entry['crc'] = crc32(contents) & 0xffffffff
        # Write the Current Date and Time
        dt = time.localtime(time.time())
        dosdate = (dt[0] - 1980) << 9 | dt[1] << 5 | dt[2]
        dostime = dt[3] << 11 | dt[4] << 5 | (dt[5] // 2)
        entry['time'] = dosdate.to_bytes(2, byteorder = 'little')
        entry['date'] = dostime.to_bytes(2, byteorder = 'little')
        extraSize = self.getExtraAlignmentSize(entry['name'])
        # Local Entry Signature
        self.file.write(b'\x50\x4b\x03\x04')
        # Version for Extract, Bits, Compression Method
        writeInt(self.file, 20, 2)
        writeInt(self.file, 0, 2)
        writeInt(self.file, 0, 2)
        # Mod Time/Date
        self.file.write(entry['time'])
        self.file.write(entry['date'])
        # CRC Hash
        writeInt(self.file, entry['crc'], 4)
        # Size Uncompressed/Compressed
        writeInt(self.file, len(contents), 4)
        writeInt(self.file, len(contents), 4)
        # Filename/Extra Length
        writeInt(self.file, len(entry['name']), 2)
        writeInt(self.file, extraSize+4, 2)
        # Filename
        self.file.write(entry['name'].encode())
        # Extra Header Id/Size
        writeInt(self.file, 1, 2)
        writeInt(self.file, extraSize, 2)
        # Padding Bytes and File Contents
        self.file.write(bytes(extraSize))
        self.file.write(contents)
        entry['size'] = len(contents)
        self.entries.append(entry)

    def writeCentralDir(self):
        self.cdOffset = self.file.tell()
        for entry in self.entries:
            # Central Directory Signature
            self.file.write(b'\x50\x4B\x01\x02')
            # Version Made By
            writeInt(self.file, 62, 2)
            # Version For Extract
            writeInt(self.file, 20, 2)
            # Bits
            writeInt(self.file, 0, 2)
            # Compression Method
            writeInt(self.file, 0, 2)
            self.file.write(entry['time'])
            self.file.write(entry['date'])
            # CRC Hash
            writeInt(self.file, entry['crc'], 4)
            # Size Compressed/Uncompressed
            writeInt(self.file, entry['size'], 4)
            writeInt(self.file, entry['size'], 4)
            # Filename Length, Extra Field Length, Comment Length
            writeInt(self.file, len(entry['name']), 2)
            writeInt(self.file, 0, 2)
            writeInt(self.file, 0, 2)
            # Disk Number Start, Internal Attrs, External Attrs
            writeInt(self.file, 0, 2)
            writeInt(self.file, 0, 2)
            writeInt(self.file, 0, 4)
            # Local Header Offset
            writeInt(self.file, entry['offset'], 4)
            # Add the file name again
            self.file.write(entry['name'].encode())
            # Get Central Dir Length
        self.cdLength = self.file.tell() - self.cdOffset

    def writeEndCentralDir(self):
        # End Central Directory Signature
        self.file.write(b'\x50\x4B\x05\x06')
        # Disk Number and Disk Number for Central Dir
        writeInt(self.file, 0, 2)
        writeInt(self.file, 0, 2)
        # Num Central Dir Entries on Disk and Num Central Dir Entries
        writeInt(self.file, len(self.entries), 2)
        writeInt(self.file, len(self.entries), 2)
        # Central Dir Length/Offset
        writeInt(self.file, self.cdLength, 4)
        writeInt(self.file, self.cdOffset, 4)
        # Comment Length
        writeInt(self.file, 0, 2)

    def close(self):
        self.writeCentralDir()
        self.writeEndCentralDir()
        self.file.close()
