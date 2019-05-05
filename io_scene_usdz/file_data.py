import os

#from io_scene_usdz.compression_utils import *
from io_scene_usdz.crate_file import *
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

    def getTokens(self, map):
        #tokens = self.type.replace('"', '').split()
        tokens = self.type.split()
        for token in tokens:
            map.add(token)
        if 'def' in self.type:
            for item in self.items:
                item.getTokens(map)

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

    def writeUsdcPrim(self, crate):
        fset = []
        fset.append(crate.addField('typeName', self.type[4:]))
        fset.append(crate.addField('specifier', SpecifierType.Def))
        children = []
        attributes = []
        for item in self.items:
            if len(item.items) > 0:
                children.append(item)
            else:
                attributes.append(item)
        jump = -2
        if len(attributes) > 0:
            jump = len(attributes) + 1
            fset.append(crate.addField('properties', [a.name for a in attributes]))
        if len(children) > 0:
            jump = -1
            fset.append(crate.addField('primChildren', [c.name for c in children]))
        fset = crate.addFieldSet(fset)
        path = crate.addPath(self.name, jump, False)
        crate.addSpec(path, fset, SpecType.Prim)
        for child in children:
            child.writeUsdc(crate)
        for att in attributes:
            jump -2 if att == attributes[-1] else 0
            att.writeUsdc(crate, jump)

    def writeUsdcAtt(self, crate, jump):
        fset = []
        types = self.type.split()
        fset.append(crate.addField('typeName', types[-1]))
        for v in types[:-1]:
            if v == 'uniform':
                fset.append(crate.addField('variability', True, ValueType.Variability))
            elif v == 'custom':
                fset.append(crate.addField('custom', True))
        for field, value in self.properties.items():
            fset.append(crate.addField(field, value))
        fset.append(crate.addField('default', self.data))
        fset = crate.addFieldSet(fset)
        path = crate.addPath(self.name, jump, True)
        crate.addSpec(path, fset, SpecType.Attribute)


    def writeUsdc(self, crate, jump = 0):
        if self.type[:4] == 'def ':
            self.writeUsdcPrim(crate)
        else:
            self.writeUsdcAtt(crate, jump)


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

    def getStrings(self):
        strings = []
        return strings

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

    def writeUsdc(self, filePath):
        file = open(filePath, 'wb')
        crate = CrateFile(file)
        crate.writeBootStrap()
        # Add the fields
        fset = []
        for name, value in self.properties.items():
            if type(value) == str:
                value = value.replace('"', '')
            fset.append(crate.addField(name, value))
        if len(self.items) > 0:
            names = []
            for item in self.items:
                names.append(item.name)
            fset.append(crate.addField('primChildren', names))
        fset = crate.addFieldSet(fset)
        # Add path and spec
        jump = -1 if len(self.items) > 0 else -2
        path = crate.addPath('', jump, False)
        crate.addSpec(path, fset, SpecType.PseudoRoot)
        # Write items
        for item in self.items:
            item.writeUsdc(crate)
        # Finish Writing the usdc file
        crate.writeSections()
        crate.writeTableOfContents()
        file.close()
