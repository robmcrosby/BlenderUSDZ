import os

from io_scene_usdz.compression_utils import *


def writeInt32Compressed(file, data):
    buffer = lz4Compress(usdInt32Compress(data))
    file.write(len(buffer).to_bytes(8, byteorder='little'))
    file.write(buffer)


class CrateFile:
    def __init__(self, file):
        self.file = file
        self.toc = []
        self.tokenMap = {}
        self.tokens = []
        self.strings = []
        self.fields = []
        self.reps = []
        self.fsets = []
        self.paths = []
        self.specs = []

    def writeBootStrap(self, tocOffset = 0):
        self.file.seek(0)
        self.file.write(b'PXR-USDC')
        # Version
        self.file.write(b'\x00\x06\x00\x00\x00\x00\x00\x00')
        # Table of Contents Offset
        self.file.write(tocOffset.to_bytes(8, byteorder='little'))
        self.file.write(bytes(64))

    def writeTokensSection(self):
        start = self.file.tell()
        self.file.write(len(self.tokens).to_bytes(8, byteorder='little'))
        buffer = bytearray()
        for token in self.tokens:
            buffer += token.encode() + b'\0'
        self.file.write(len(buffer).to_bytes(8, byteorder='little'))
        buffer = lz4Compress(buffer)
        self.file.write(len(buffer).to_bytes(8, byteorder='little'))
        self.file.write(buffer)
        size = self.file.tell() - start
        self.toc.append((b'TOKENS', start, size))

    def writeStringsSection(self):
        start = self.file.tell()
        self.file.write(len(self.strings).to_bytes(8, 'little'))
        writeInt32Compressed(self.file, self.strings)
        size = self.file.tell() - start
        self.toc.append((b'STRINGS', start, size))

    def writeFieldsSection(self):
        start = self.file.tell()
        self.file.write(len(self.fields).to_bytes(8, byteorder='little'))
        writeInt32Compressed(self.file, self.fields)
        buffer = lz4Compress(encodeInts(self.reps, 8))
        self.file.write(len(buffer).to_bytes(8, byteorder='little'))
        self.file.write(buffer)
        size = self.file.tell() - start
        self.toc.append((b'FIELDS', start, size))

    def writeFieldSetsSection(self):
        start = self.file.tell()
        self.file.write(len(self.fsets).to_bytes(8, byteorder='little'))
        writeInt32Compressed(self.file, self.fsets)
        size = self.file.tell() - start
        self.toc.append((b'FIELDSETS', start, size))

    def writePathsSection(self):
        start = self.file.tell()
        paths = []
        tokens = []
        jumps = []
        for path, token, jump in self.paths:
            paths.append(path)
            tokens.append(token)
            jumps.appden(jump)
        self.file.write(len(self.paths).to_bytes(8, byteorder='little'))
        writeInt32Compressed(self.file, paths)
        writeInt32Compressed(self.file, tokens)
        writeInt32Compressed(self.file, jumps)
        size = self.file.tell() - start
        self.toc.append((b'PATHS', start, size))

    def writeSpecsSection(self):
        start = self.file.tell()
        paths = []
        fsets = []
        types = []
        for path, fset, type in self.specs:
            paths.append(path)
            fsets.append(fset)
            types.appden(type)
        self.file.write(len(self.specs).to_bytes(8, byteorder='little'))
        writeInt32Compressed(self.file, paths)
        writeInt32Compressed(self.file, fsets)
        writeInt32Compressed(self.file, types)
        size = self.file.tell() - start
        self.toc.append((b'SPECS', start, size))

    def writeSections(self):
        self.writeTokensSection()
        self.writeStringsSection()
        self.writeFieldsSection()
        self.writeFieldSetsSection()
        self.writePathsSection()
        self.writeSpecsSection()

    def writeTableOfContents(self):
        tocStart = self.file.tell()
        self.file.write(len(self.toc).to_bytes(8, byteorder='little'))
        for name, start, size in self.toc:
            self.file.write(name)
            self.file.write(bytes(16-len(name)))
            self.file.write(start.to_bytes(8, byteorder='little'))
            self.file.write(size.to_bytes(8, byteorder='little'))
        self.writeBootStrap(tocStart)
