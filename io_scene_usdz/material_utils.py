import bpy


def getBpyMaterialName(material):
    return material.name.replace('.', '_')

def getBpyOutputNode(material):
    if material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
                return node
    return None

def getBpyShaderNode(node):
    if  node != None and len(node.inputs[0].links) > 0:
        return node.inputs[0].links[0].from_node
    return None

def getBpyNodeInput(node, name):
    if node != None and name in node.inputs:
        return node.inputs[name]
    return None

def getBpyDiffuseInput(node):
    input = getBpyNodeInput(node, 'Base Color')
    if input == None:
        input = getBpyNodeInput(node, 'Color')
    return input

def getBpyEmissiveInput(node):
    return getBpyNodeInput(node, 'Emission')

def getBpySpecularInput(node):
    return getBpyNodeInput(node, 'Specular')

def getBpySpecularTintInput(node):
    return getBpyNodeInput(node, 'Sheen Tint')

def getBpyMetallicInput(node):
    return getBpyNodeInput(node, 'Metallic')

def getBpyRoughnessInput(node):
    return getBpyNodeInput(node, 'Roughness')

def getBpyClearcoatInput(node):
    return getBpyNodeInput(node, 'Clearcoat')

def getBpyClearcoatRoughnessInput(node):
    return getBpyNodeInput(node, 'Clearcoat Roughness')

def getBpyIorInput(node):
    return getBpyNodeInput(node, 'IOR')

def getBpyTransmissionInput(node):
    return getBpyNodeInput(node, 'Transmission')

def getBpyAlphaInput(node):
    return getBpyNodeInput(node, 'Alpha')

def getBpyNormalInput(node):
    return getBpyNodeInput(node, 'Normal')

def getBpyDiffuseColor(node, default = (0.6, 0.6, 0.6)):
    input = getBpyDiffuseInput(node)
    if input == None:
        return default
    return input.default_value[:3]

def getBpySpecularValue(node, default = 0.5):
    input = getBpySpecularInput(node)
    if input == None:
        return default
    return input.default_value

def getBpySpecularTintValue(node, default = 0.0):
    input = getBpySpecularTintInput(node)
    if input == None:
        return default
    return input.default_value

def getBpySpecularColor(node):
    specular = (getBpySpecularValue(node),)*3
    return specular

def getBpyEmissiveColor(node, default = (0.0, 0.0, 0.0)):
    input = getBpyEmissiveInput(node) # getBpyNodeInput(node, 'Emission')
    if input == None:
        return default
    return input.default_value[:3]

def getBpyRoughnessValue(node, default = 0.0):
    input = getBpyRoughnessInput(node)
    if input == None:
        return default
    return input.default_value

def getBpyMetallicValue(node, default = 0.0):
    input = getBpyMetallicInput(node)
    if input == None:
        return default
    return input.default_value

def getBpyAlphaValue(node, default = 1.0):
    input = getBpyAlphaInput(node)
    if input == None:
        return default
    return input.default_value

def getBpyIorValue(node, default = 1.5):
    input = getBpyIorInput(node)
    if input == None:
        return default
    return input.default_value

def getBpyClearcoatValue(node, default = 0.0):
    input = getBpyClearcoatInput(node)
    if input == None:
        return default
    return input.default_value

def getBpyClearcoatRoughnessValue(node, default = 0.0):
    input = getBpyClearcoatRoughnessInput(node)
    if input == None:
        return default
    return input.default_value

def getBpyActiveUvMap(obj):
    if obj.data.uv_layers.active != None:
        return obj.data.uv_layers.active.name
    return 'UVMap'

def getBpyInputUvMap(input, obj):
    if input != None and input.is_linked:
        node = input.links[0].from_node
        if node.type == 'TEX_IMAGE':
            return getBpyInputUvMap(node.inputs['Vector'], obj)
        elif node.type == 'UVMAP' and node.uv_map != None:
            return node.uv_map
    return getBpyActiveUvMap(obj)
