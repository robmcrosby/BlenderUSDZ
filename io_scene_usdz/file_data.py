import os
import itertools
import binascii

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

def interleave_lists(lists):
    return [x for x in itertools.chain(*itertools.zip_longest(*lists)) if x is not None]

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
        entry['offset'] = self.file.tell()
        entry['crc'] = binascii.crc32(contents)
        entry['time'] = b'\x0C\x80'
        entry['date'] = b'\xB3\x4E'
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
        entry['size'] = self.file.tell() - entry['offset']
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


class FileItem:
    def __init__(self, type, name = '', data = None):
        self.type = type
        self.name = name
        self.data = data
        self.properties = {}
        self.items = []
        self.pathIndex = -1
        self.pathJump = -2
        self.nameToken = -1
        self.pathStr = ''
        self.pathItems = []

    def addItem(self, type, name = '', data = None):
        item = FileItem(type, name, data)
        self.items.append(item)
        return item

    def addTimeSample(self, frame, data):
        self.append((frame, data))

    def append(self, item):
        if item != None:
            self.items.append(item)

    def updatePathStrings(self, parentStr, pathMap):
        self.pathStr = parentStr + '/' + self.name
        pathMap[self.pathStr] = self
        if not self.hasTimeSamples():
            for item in self.items:
                item.updatePathStrings(self.pathStr, pathMap)

    def printUsda(self, indent = ''):
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

    def isAttribute(self):
        return self.type[:4] != 'def '

    def isPath(self):
        return type(self.data) == str and self.data.startswith('<') and self.data.endswith('>')

    def hasTimeSamples(self):
        return len(self.items) > 0 and type(self.items[0]) == tuple

    def getType(self):
        return self.type.split()[-1]

    def getName(self):
        if self.name[-8:] == '.connect':
            return self.name[:-8]
        if self.name[-12:] == '.timeSamples':
            return self.name[:-12]
        return self.name

    def getQualifiers(self):
        return self.type.split()[:-1]

    def getItems(self, excluded = []):
        if self.hasTimeSamples():
            return []
        return list(filter(lambda item: not item.getType() in excluded, self.items))

    def getChildren(self, excluded = []):
        if self.hasTimeSamples():
            return []
        return list(filter(lambda item: not item.isAttribute() and not item.getType() in excluded, self.items))

    def getAttributes(self, excluded = []):
        if self.hasTimeSamples():
            return []
        return list(filter(lambda item: item.isAttribute() and not item.getType() in excluded, self.items))

    def countItems(self, excluded = []):
        items = self.getItems(excluded)
        count = len(items)
        for item in items:
            count += item.countItems(excluded)
        return count

    def getItemsOfType(self, type):
        children = self.getChildren()
        items = list(filter(lambda c: c.getType() == type, children))
        for child in children:
            items += child.getItemsOfType(type)
        return items

    def getItemOfName(self, name):
        for item in self.items:
            if item.name == name:
                return item
        return None

    def writeSpecsAtt(self, crate):
        fset = []
        fset.append(crate.addField('typeName', self.getType()))
        for q in self.getQualifiers():
            if q == 'uniform':
                fset.append(crate.addField('variability', True, ValueType.Variability))
            elif q == 'custom':
                fset.append(crate.addField('custom', True))
        for field, value in self.properties.items():
            fset.append(crate.addField(field, value))
        if self.data != None:
            fset.append(crate.addField('default', self.data))
        if self.hasTimeSamples():
            fset.append(crate.addFieldTimeSamples('timeSamples', self.items, self.type))
        fset = crate.addFieldSet(fset)
        self.nameToken = crate.getTokenIndex(self.getName())
        self.pathIndex = crate.addSpec(fset, SpecType.Attribute)

    def writeSpecsPath(self, crate, pathMap):
        pathStr = self.data[1:-1].replace('.', '/')
        pathItem = pathMap[pathStr]
        pathIndex = pathItem.pathIndex
        if pathIndex < 0:
            pathItem.writeSpecs(crate, pathMap)
            pathIndex = pathItem.pathIndex
        type = self.getType()
        listOpField = 'targetPaths' if type == 'rel' else 'connectionPaths'
        vectorField = 'targetChildren' if type == 'rel' else 'connectionChildren'
        specType = SpecType.Relationship if type == 'rel' else SpecType.Attribute
        fset = []
        fset.append(crate.addField('variability', True, ValueType.Variability))
        fset.append(crate.addFieldPathListOp(listOpField, pathIndex))
        fset.append(crate.addFieldPathVector(vectorField, pathIndex))
        fset = crate.addFieldSet(fset)
        self.nameToken = crate.getTokenIndex(self.getName())
        self.pathIndex = crate.addSpec(fset, specType)

    def writeSpecsPrim(self, crate):
        fset = []
        fset.append(crate.addField('typeName', self.getType()))
        fset.append(crate.addField('specifier', SpecifierType.Def))
        children = self.getChildren()
        attributes = self.getAttributes()
        if len(attributes) > 0:
            fset.append(crate.addFieldTokenVector('properties', [a.getName() for a in attributes]))
        if len(children) > 0:
            fset.append(crate.addFieldTokenVector('primChildren', [c.getName() for c in children]))
        fset = crate.addFieldSet(fset)
        self.nameToken = crate.getTokenIndex(self.getName())
        self.pathIndex = crate.addSpec(fset, SpecType.Prim)

    def writeSpecs(self, crate, pathMap):
        if self.pathIndex < 0:
            if self.isAttribute():
                if self.isPath():
                    self.writeSpecsPath(crate, pathMap)
                else:
                    self.writeSpecsAtt(crate)
            else:
                self.writeSpecsPrim(crate)

    def addPath(self, crate):
        crate.addPath(self.pathIndex, self.nameToken, self.pathJump, self.isAttribute())

    def addPaths(self, crate):
        children = self.getChildren()
        attributes = self.getAttributes()
        for item in children:
            item.pathJump = -1 if item == children[-1] and len(attributes) == 0 else item.countItems() + 1
            item.addPath(crate)
            item.addPaths(crate)
        for item in attributes:
            item.pathJump = -2 if item == attributes[-1] else 0
            item.addPath(crate)

    def countItems(self):
        count = len(self.items)
        for item in self.getChildren():
            count += item.countItems()
        return count



class FileData:
    def __init__(self):
        self.properties = {}
        self.items = []
        self.pathMap = {}
        self.path = 0

    def addItem(self, type, name = '', data = None):
        item = FileItem(type, name, data)
        item.pathStr = '/' + name
        self.items.append(item)
        return item

    def append(self, item):
        if item != None:
            item.pathStr = '/' + item.name
            self.items.append(item)

    def updatePathStrings(self):
        self.pathMap = {}
        for item in self.items:
            item.updatePathStrings('', self.pathMap)

    def getChildren(self):
        return list(filter(lambda item: not item.isAttribute(), self.items))

    def getAttributes(self):
        return list(filter(lambda item: item.isAttribute(), self.items))

    def getItemsOfType(self, type):
        children = self.getChildren()
        items = list(filter(lambda c: c.getType() == type, children))
        for child in children:
            items += child.getItemsOfType(type)
        return items

    def printUsda(self):
        src = '#usda 1.0\n'
        # Print the Properties
        if len(self.properties) > 0:
            src += print_properties(self.properties, '')
        src += '\n'
        # Print the Items
        for item in self.items:
            src += item.printUsda()
        return src

    def writeUsda(self, filePath):
        src = self.printUsda()
        # Write to file
        f = open(filePath, 'w')
        f.write(src)
        f.close()

    def addPaths(self, crate):
        children = self.getChildren()
        attributes = self.getAttributes()
        # Add the first path
        jump = -1 if len(self.items) > 0 else -2
        token = crate.getTokenIndex('')
        crate.addPath(self.path, token, jump, False)
        for item in children:
            item.pathJump = -1 if item == children[-1] and len(attributes) == 0 else item.countItems() + 1
            item.addPath(crate)
            item.addPaths(crate)
        for item in attributes:
            item.pathJump = -2 if item == attributes[-1] else 0
            item.addPath(crate)

    def writeUsdc(self, filePath):
        file = open(filePath, 'wb')
        crate = CrateFile(file)
        crate.writeBootStrap()
        # Update Path Strings for the items
        self.updatePathStrings()
        # Add the fields
        fset = []
        for name, value in self.properties.items():
            if type(value) == str:
                value = value.replace('"', '')
            if name == 'startTimeCode' or name == 'endTimeCode' or name == 'timeCodesPerSecond':
                value = float(value)
                fset.append(crate.addFieldDouble(name, value))
            else:
                fset.append(crate.addField(name, value))
        children = self.getChildren()
        if len(children) > 0:
            fset.append(crate.addFieldTokenVector('primChildren', [c.name for c in children]))
        fset = crate.addFieldSet(fset)
        # Add the root spec
        self.path = crate.addSpec(fset, SpecType.PseudoRoot)
        # Write Xform Specs
        xforms = self.getItemsOfType('Xform')
        xforms += self.getItemsOfType('SkelRoot')
        for xform in xforms:
            xform.writeSpecs(crate, self.pathMap)

        # Write Materal Specs
        attLists = []
        materials = self.getItemsOfType('Material')
        for material in materials:
            attList = []
            material.writeSpecs(crate, self.pathMap)
            for child in material.getChildren():
                child.writeSpecs(crate, self.pathMap)
                attList += child.getAttributes()
            attLists.append(attList + material.getAttributes())
        materialAtts = interleave_lists(attLists)

        # Write Skeleton Animation Specs
        attLists = []
        animations = self.getItemsOfType('SkelAnimation')
        for animation in animations:
            animation.writeSpecs(crate, self.pathMap)
            attLists.append(animation.getAttributes())
        animationAtts = interleave_lists(attLists)

        # Write Skeleton Specs
        attLists = []
        skeletons = self.getItemsOfType('Skeleton')
        for skeleton in skeletons:
            skeleton.writeSpecs(crate, self.pathMap)
            attLists.append(skeleton.getAttributes())
        skeletonAtts = interleave_lists(attLists)

        # Write Mesh Specs
        meshes = self.getItemsOfType('Mesh')
        for mesh in reversed(meshes):
            mesh.writeSpecs(crate, self.pathMap)

        # Write Animation Attributes
        for att in animationAtts:
            att.writeSpecs(crate, self.pathMap)

        # Write Skelton Attributes
        for att in skeletonAtts:
            att.writeSpecs(crate, self.pathMap)

        # Write Material Attribute Specs
        for att in materialAtts:
            att.writeSpecs(crate, self.pathMap)

        # Write Mesh Attribute Specs
        meshAtts = interleave_lists([m.getAttributes() for m in reversed(meshes)])
        for att in meshAtts:
            att.writeSpecs(crate, self.pathMap)

        # Write Xform Attribute Specs
        atts = interleave_lists([x.getAttributes() for x in reversed(xforms)])
        for att in atts:
            att.writeSpecs(crate, self.pathMap)
        # Add Root Attribute specs
        for att in self.getAttributes():
            att.writeSpecs(crate, self.pathMap)

        # Add the Paths
        self.addPaths(crate)

        # Finish Writing the usdc file
        crate.writeSections()
        crate.writeTableOfContents()
        file.close()

    def printData(self, data, tab = ''):
        print(tab + '*'+data['name'] + '<'+data['type'].name+'>')
        for name, value in data['fields'].items():
            print(tab + '  -'+name, value)
        for item in data['items']:
            self.printData(item, tab+'  ')

    def buildPathMap(self, crate, index, basePath = ''):
        path, token, jump = crate.paths[index]
        basePath = basePath + '/' + crate.getTokenStr(token)
        self.pathMap[path] = basePath
        #print(path, basePath)

        if jump == 0 or jump == -2:
            return (index + 1, jump)
        index, jump = self.buildPathMap(crate, index + 1, basePath)
        while index < len(crate.paths) and jump != -2:
            index, jump = self.buildPathMap(crate, index, basePath)
        return (index, -1)


    def buildItemFromCrate(self, crate, index):
        path, token, jump = crate.paths[index]
        fset, spec = crate.specsMap[path]
        fset = crate.getFieldSet(fset)
        item = FileItem(SpecType(spec).name)
        item.name = crate.getTokenStr(token)
        item.pathJump = jump
        item.pathIndex = path
        self.nameToken = token

        # Get the Properties
        properties = {}
        for field in fset:
            if field < len(crate.reps):
                name = crate.getTokenStr(crate.fields[field])
                value = crate.getRepValue(crate.reps[field])
                properties[name] = value

        if 'typeName' in properties:
            typeName = properties.pop('typeName')
            if type(typeName) == list:
                typeName = typeName[0]
            if item.type == 'Prim':
                item.type = 'def ' + typeName
            else:
                item.type = typeName
        if 'default' in properties:
            # Set the Default value
            item.data = properties.pop('default')
        if item.type == 'token' and item.data != None:
            # Put quotes on tokens
            item.data = '"' + item.data + '"'
        if item.type == 'Relationship':
            item.type = 'rel'
            if 'targetPaths' in properties:
                paths = properties.pop('targetPaths')
                item.data = '<' + self.pathMap[paths['path']] + '>'
            if 'targetChildren' in properties:
                properties.pop('targetChildren')
            if 'variability' in properties:
                properties.pop('variability')
        elif 'variability' in properties:
            # Add uniform keyword
            item.type = 'uniform ' + item.type
            properties.pop('variability')
        if 'connectionPaths' in properties:
            paths = properties.pop('connectionPaths')
            if paths['path'] in self.pathMap:
                item.data = '<' + self.pathMap[paths['path']] + '>'
                # Replace last '/' with '.'
                item.data = item.data[::-1].replace('/', '.', 1)[::-1]
                item.name += '.connect'
        if 'connectionChildren' in properties:
            properties.pop('connectionChildren')
        item.properties = properties

        if jump == 0 or jump == -2:
            index += 1
        else:
            child, index = self.buildItemFromCrate(crate, index + 1)
            if 'def' in child.type or len(child.items) == 0:
                item.items.append(child)
            while index < len(crate.paths) and child.pathJump != -2:
                child, index = self.buildItemFromCrate(crate, index)
                if 'def' in child.type or len(child.items) == 0:
                    item.items.append(child)
        return (item, index)


    def buildFromCrate(self, crate):
        self.pathMap = {}
        path, token, jump = crate.paths[0]
        fset, spec = crate.specsMap[path]
        fset = crate.getFieldSet(fset)

        # Get the Properties
        for field in fset:
            if field < len(crate.reps):
                name = crate.getTokenStr(crate.fields[field])
                value = crate.getRepValue(crate.reps[field])
                self.properties[name] = value

        if jump != 0 and jump != -2:
            # Build the Path Map
            index = 1
            while index < len(crate.paths):
                index, jump = self.buildPathMap(crate, index)

            # Get the Items
            index = 1
            while index < len(crate.paths):
                item, index = self.buildItemFromCrate(crate, index)
                self.items.append(item)


    def readUsdc(self, filePath):
        file = open(filePath, 'rb')
        crate = CrateFile(file)
        crate.readTableOfContents()

        self.buildFromCrate(crate)
        file.close()
