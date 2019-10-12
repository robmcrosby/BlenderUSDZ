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

def export_usdz(context, filepath = '', materials = True, keepUSDA = False,
                bakeTextures = False, bakeAO = False, samples = 64,
                scale = 1.0, animated = False, useConverter = False,
                bakeSize = 1024):
    filePath, fileName = os.path.split(filepath)
    fileName, fileType = fileName.split('.')
    usdaFile = filePath+'/'+fileName+'.usda'
    usdcFile = filePath+'/'+fileName+'.usdc'
    usdzFile = filePath+'/'+fileName+'.usdz'
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
    # Export image files
    if bakeTextures or bakeAO:
        scene.exportBakedTextures()
    # Export the USD Data
    usdData = scene.exportUsd()
    # Cleanup the scene
    scene.cleanup()
    if useConverter:
        # Crate text usda file and run the USDZ Converter Tool
        usdData.writeUsda(usdaFile)
        args = ['xcrun', 'usdz_converter', usdaFile, usdzFile]
        args += ['-v']
        subprocess.run(args)
    else:
        if keepUSDA:
            usdData.writeUsda(usdaFile)
        # Create Binary and Manually zip to a usdz file
        crateFile = open(usdcFile, 'wb')
        crate = CrateFile(crateFile)
        crate.writeUsd(usdData)
        crateFile.close()
        usdz = UsdzFile(usdzFile)
        usdz.addFile(usdcFile)
        for textureFile in scene.textureFilePaths:
            usdz.addFile(textureFile)
        usdz.close()
    if tempPath != None:
        # Delete temp files
        shutil.rmtree(tempPath)
    return {'FINISHED'}


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
