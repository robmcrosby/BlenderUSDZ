import os
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
