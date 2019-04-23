import os

from io_scene_usdz.compression_utils import *
tab = '   '

def print_data(data):
    if type(data) is str:
        return data
    if type(data) is int:
        return '%d' % data
    if type(data) is float:
        return '%.6g' % round(data, 6)
    if type(data) is list:
        return '[' + ', '.join(print_data(item) for item in data) + ']'
    if type(data) is tuple:
        return '(' + ', '.join(print_data(item) for item in data) + ')'
    return ''


def print_properties(properties, indent = ''):
    src = '(\n'
    for name, data in properties.items():
        src += indent+tab + name + ' = ' + print_data(data) + '\n'
    return src + indent + ')\n'

def print_time_samples(samples, indent = ''):
    src = '{\n'
    for frame, data in samples:
        src += indent+tab + print_data(frame) + ': ' + print_data(data) + ',\n'
    return src + indent + '}\n'


class FileItem:
    def __init__(self, type, name = '', data = None):
        self.type = type
        self.name = name
        self.data = data
        self.properties = {}
        self.items = []

    def addItem(self, type, name = '', data = None):
        item = FileItem(type, name, data)
        self.items.append(item)
        return item

    def addTimeSample(self, frame, data):
        self.append((frame, data))

    def append(self, item):
        if item != None:
            self.items.append(item)

    def getTokens(self, tokens):
        if 'def' in self.type:
            tokens.add('def')
            tokens.add(self.type[4:])
            for item in self.items:
                item.getTokens(tokens)
        else:
            tokens.add(self.type)

    def printUsda(self, indent):
        src = ''
        if 'def' in self.type:
            src += indent + '\n'
            src += indent + self.type + ' "' + self.name + '"\n'
            src += indent + '{\n'
            for item in self.items:
                src += item.printUsda(indent+tab)
            src += indent + '}\n'
        else:
            src += indent + self.type + ' ' + self.name
            if self.data != None:
                src += ' = ' + print_data(self.data)
                if len(self.properties) > 0:
                    src += ' ' + print_properties(self.properties, indent)
                else:
                    src += '\n'
            elif len(self.items) > 0:
                src += ' = ' + print_time_samples(self.items, indent)
            else:
                src += '\n'
        return src

class FileData:
    def __init__(self):
        self.properties = {}
        self.items = []

    def addItem(self, type, name = '', data = None):
        item = FileItem(type, name, data)
        self.items.append(item)
        return item

    def append(self, item):
        if item != None:
            self.items.append(item)

    def getTokens(self):
        tokens = set()
        for token in self.properties.keys():
            tokens.add(token)
        for item in self.items:
            item.getTokens(tokens)
        return tokens

    def printUsda(self):
        src = '#usda 1.0\n'

        # Print the Properties
        if len(self.properties) > 0:
            src += print_properties(self.properties, '')
        src += '\n'

        # Print the Items
        for item in self.items:
            src += item.printUsda('')
        return src

    def writeUsda(self, filePath):
        src = self.printUsda()
        # Write to file
        f = open(filePath, 'w')
        f.write(src)
        f.close()

    def writeBootStrap(self, file, toc = 0):
        file.seek(0)
        file.write(b'PXR-USDC')
        # Version
        file.write(b'\x00\x06\x00\x00\x00\x00\x00\x00')
        # Table of Contents Offset
        file.write(toc.to_bytes(8, byteorder='little'))
        file.write(bytes(64))

    def writeTokensSection(self, file, toc):
        start = file.tell()
        tokens = self.getTokens()
        buffer = b''
        for token in tokens:
            buffer += token.encode() + b'\0'
        compressed = lz4Compress(buffer)
        file.write(len(tokens).to_bytes(8, byteorder='little'))
        file.write(len(buffer).to_bytes(8, byteorder='little'))
        file.write(len(compressed).to_bytes(8, byteorder='little'))
        file.write(compressed)
        size = file.tell() - start
        toc.append((b'TOKENS', start, size))

    def writeStringsSection(self, file, toc):
        start = file.tell()
        file.write(bytes(8))
        size = file.tell() - start
        toc.append((b'STRINGS', start, size))

    def writeFieldsSection(self, file, toc):
        start = file.tell()
        file.write(bytes(41))
        size = file.tell() - start
        toc.append((b'FIELDS', start, size))

    def writeFieldSetsSection(self, file, toc):
        start = file.tell()
        file.write(bytes(24))
        size = file.tell() - start
        toc.append((b'FIELDSETS', start, size))

    def writePathsSection(self, file, toc):
        start = file.tell()
        file.write(bytes(61))
        size = file.tell() - start
        toc.append((b'PATHS', start, size))

    def writeSpecsSection(self, file, toc):
        start = file.tell()
        file.write(bytes(53))
        size = file.tell() - start
        toc.append((b'SPECS', start, size))

    def writeTableOfContents(self, file, toc):
        tocStart = file.tell()
        file.write(len(toc).to_bytes(8, byteorder='little'))
        for name, start, size in toc:
            file.write(name)
            file.write(bytes(16-len(name)))
            file.write(start.to_bytes(8, byteorder='little'))
            file.write(size.to_bytes(8, byteorder='little'))
        self.writeBootStrap(file, tocStart)

    def writeUsdc(self, filePath):
        toc = []
        file = open(filePath, 'wb')
        # Write Boot Strap to reserve space
        self.writeBootStrap(file)
        # Write the Sections
        self.writeTokensSection(file, toc)
        self.writeStringsSection(file, toc)
        self.writeFieldsSection(file, toc)
        self.writeFieldSetsSection(file, toc)
        self.writePathsSection(file, toc)
        self.writeSpecsSection(file, toc)
        # Write the Table of Contents and Boot Strap
        self.writeTableOfContents(file, toc)
        file.close()
