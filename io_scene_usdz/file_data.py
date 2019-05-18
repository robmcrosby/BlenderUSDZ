import os
import itertools

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

def interleave_lists(lists):
    return [x for x in itertools.chain(*itertools.zip_longest(*lists)) if x is not None]

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
        if self.isAttribute():
            if self.isPath():
                self.writeSpecsPath(crate, pathMap)
            else:
                self.writeSpecsAtt(crate)
        else:
            self.writeSpecsPrim(crate)

    def writePath(self, crate):
        crate.addPath(self.pathIndex, self.nameToken, self.pathJump, self.isAttribute())

    def writeSubPaths(self, crate, excluded = []):
        children = self.getChildren(excluded)
        attributes = self.getAttributes(excluded)
        for child in children:
            isLast = child == children[-1] and len(attributes) == 0
            child.pathJump = -1 if isLast else child.countItems(excluded) + 1
            child.writePath(crate)
            child.writeSubPaths(crate)
        for attribute in attributes:
            attribute.pathJump = -2 if attribute == attributes[-1] else 0
            attribute.writePath(crate)


class FileData:
    def __init__(self):
        self.properties = {}
        self.items = []
        self.pathMap = {}

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
        path = crate.addSpec(fset, SpecType.PseudoRoot)
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

        # Add the first path
        jump = -1 if len(self.items) > 0 else -2
        token = crate.getTokenIndex('')
        crate.addPath(path, token, jump, False)
        count = 0
        for xform in reversed(xforms):
            count += xform.countItems(['Xform']) + 1
            xform.pathJump = -1 if xform == xforms[0] else count
        for xform in xforms:
            xform.writePath(crate)
        for xform in reversed(xforms):
            animations = xform.getItemsOfType('SkelAnimation')
            for animation in animations:
                animation.pathJump = animation.countItems() + 1
                animation.writePath(crate)
                animation.writeSubPaths(crate)
            skeletons = xform.getItemsOfType('Skeleton')
            for skeleton in skeletons:
                skeleton.pathJump = skeleton.countItems() + 1
                skeleton.writePath(crate)
                skeleton.writeSubPaths(crate)
            materials = xform.getItemsOfType('Material')
            for material in materials:
                material.pathJump = material.countItems() + 1
                material.writePath(crate)
                material.writeSubPaths(crate)
            xform.writeSubPaths(crate, ['Xform', 'Material', 'SkelAnimation', 'Skeleton'])

        """
        # Write items
        for item in self.items:
            jump = -2 if item == self.items[-1] else 0
            item.writeUsdc(crate)
        """
        # Finish Writing the usdc file
        crate.writeSections()
        crate.writeTableOfContents()
        file.close()
