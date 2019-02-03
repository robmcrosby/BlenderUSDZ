import bpy

def get_material_name(material):
    return material.name.replace('.', '_')

def get_output_node(material):
    for node in material.node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
            return node
    return None

def get_shader_node(node):
    if  node != None and len(node.inputs[0].links) > 0:
        return node.inputs[0].links[0].from_node
    return None

def get_node_input(node, name):
    if node != None and name in node.inputs:
        return node.inputs[name]
    return None

def get_diffuse_input(node):
    input = get_node_input(node, 'Base Color')
    if input == None:
        input = get_node_input(node, 'Color')
    return input

def get_specular_input(node):
    return get_node_input(node, 'Specular')

def get_specular_tint_input(node):
    return get_node_input(node, 'Sheen Tint')

def get_metallic_input(node):
    return get_node_input(node, 'Metallic')

def get_roughness_input(node):
    return get_node_input(node, 'Roughness')

def get_clearcoat_input(node):
    return get_node_input(node, 'Clearcoat')

def get_clearcoat_roughness_input(node):
    return get_node_input(node, 'Clearcoat Roughness')

def get_ior_input(node):
    return get_node_input(node, 'IOR')

def get_transmission_input(node):
    return get_node_input(node, 'Transmission')

def get_normal_input(node):
    return get_node_input(node, 'Normal')

def get_diffuse_color(node, default = (0.6, 0.6, 0.6)):
    input = get_diffuse_input(node)
    if input == None:
        return default
    return input.default_value[:3]

def get_specular_value(node, default = 0.5):
    input = get_specular_input(node)
    if input == None:
        return default
    return input.default_value

def get_specular_tint_value(node, default = 0.0):
    input = get_specular_tint_input(node)
    if input == None:
        return default
    return input.default_value

def get_specular_color(node):
    specular = (get_specular_value(node),)*3
    return specular

def get_emissive_color(node, default = (0.0, 0.0, 0.0)):
    return default

def get_roughness_value(node, default = 0.0):
    input = get_roughness_input(node)
    if input == None:
        return default
    return input.default_value

def get_metallic_value(node, default = 0.0):
    input = get_metallic_input(node)
    if input == None:
        return default
    return input.default_value

def get_opacity_value(node, default = 1.0):
    input = get_transmission_input(node)
    if input == None:
        return default
    return 1.0 - input.default_value

def get_ior_value(node, default = 1.5):
    input = get_ior_input(node)
    if input == None:
        return default
    return input.default_value

def get_clearcoat_value(node, default = 0.0):
    input = get_clearcoat_input(node)
    if input == None:
        return default
    return input.default_value

def get_clearcoat_roughness_value(node, default = 0.0):
    input = get_clearcoat_roughness_input(node)
    if input == None:
        return default
    return input.default_value

def get_active_uv_map(obj):
    if obj.data.uv_layers.active != None:
        return obj.data.uv_layers.active.name
    return 'UVMap'

def get_input_uv_map(input, obj):
    if input != None and input.is_linked:
        node = input.links[0].from_node
        if node.type == 'TEX_IMAGE':
            return get_input_uv_map(node.inputs['Vector'], obj)
        elif node.type == 'UVMAP' and node.uv_map != None:
            return node.uv_map
    return get_active_uv_map(obj)

def save_image_to_file(image, file):
    image.save_render(filepath = file)

def bake_input_color_image(input, file, obj):
    if input.is_linked:
        node = input.links[0].from_node
        if node.type == 'TEX_IMAGE' and node.image != None:
            save_image_to_file(node.image, file)
            return True
    #TODO: Handle Other Setups
    print('Error Baking Color Image')
    return False
