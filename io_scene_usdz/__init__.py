
bl_info = {
    "name":        "USDZ Export",
    "author":      "Robert Crosby",
    "version":     (0, 0, 5),
    "blender":     (2, 80, 0),
    "location":    "File > Import-Export",
    "description": "Import/Export USDZ Files",
    "category":    "Import-Export"
    }


import bpy
from bpy.props import (
        BoolProperty,
        FloatProperty,
        IntProperty,
        StringProperty,
        EnumProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper,
        path_reference_mode,
        axis_conversion,
        )

class ImportUSDZ(bpy.types.Operator, ImportHelper):
    """Import a USDZ File"""

    bl_idname = "import.usdz"
    bl_label = "Import USDZ File"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ""
    filter_glob: StringProperty(
            default="*.usdz;*.usda;*.usdc",
            options={'HIDDEN'},
            )
    materials = BoolProperty(
        name="Import Materials",
        description="Import Materials and textures",
        default=True,
        )
    animations = BoolProperty(
        name="Import Animations",
        description="Import Animations",
        default=True,
        )

    def execute(self, context):
        from . import import_usdz
        keywords = self.as_keywords(ignore=("filter_glob",))
        return import_usdz.import_usdz(context, **keywords)


class ExportUSDZ(bpy.types.Operator, ExportHelper):
    """Save a USDZ File"""

    bl_idname = "export.usdz"
    bl_label = "Export USDZ File"
    bl_options = {'PRESET'}

    filename_ext = ""
    filter_glob: StringProperty(
            default="*.usdz;*.usda;*.usdc",
            options={'HIDDEN'},
            )
    exportMaterials = BoolProperty(
        name="Export Materials",
        description="Export Materials from Objects",
        default=True,
        )
    exportAnimations = BoolProperty(
        name="Export Animations",
        description="Export Animations",
        default=False,
        )
    bakeTextures = BoolProperty(
        name="Bake Textures",
        description="Bake Diffuse, Roughness, Normal, etc",
        default=False,
        )
    bakeAO = BoolProperty(
        name="Bake AO",
        description="Bake Ambiant Occlusion Texture",
        default=False,
        )
    bakeAOSamples = IntProperty(
        name="AO Samples",
        description="Number of Samples for Ambiant Occlusion",
        min=1,
        max=1000,
        default= 64,
        )
    bakeTextureSize = IntProperty(
        name="Bake Image Size",
        description="Default Size of any Baked Images",
        min=16,
        max=4096,
        default= 1024,
        )
    globalScale = FloatProperty(
        name="Scale",
        min=0.01,
        max=1000.0,
        default=1.0,
        )
    useConverter = BoolProperty(
        name="Use Usdz Converter Tool",
        description="Use Apple's Converter Tool to create the Usdz file",
        default=False,
        )

    def execute(self, context):
        from . import export_usdz
        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "global_scale",
                                            "check_existing",
                                            "filter_glob",
                                            ))
        return export_usdz.export_usdz(context, **keywords)


def menu_func_usdz_import(self, context):
    self.layout.operator(ImportUSDZ.bl_idname, text="USDZ (.usdz)")

def menu_func_usdz_export(self, context):
    self.layout.operator(ExportUSDZ.bl_idname, text="USDZ (.usdz)")


classes = (
    ImportUSDZ,
    ExportUSDZ,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_usdz_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_usdz_export)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_usdz_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_usdz_export)

    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
