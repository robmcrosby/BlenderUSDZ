
bl_info = {
    "name":        "USDZ Export",
    "author":      "Robert Crosby",
    "version":     (0, 0, 6),
    "blender":     (3, 0, 0),
    "location":    "File > Import-Export",
    "description": "Import/Export USDZ Files",
    "category":    "Import-Export"
    }

if "bpy" in locals():
    import importlib
    if "import_usdz" in locals():
        importlib.reload(import_usdz)
    if "export_usdz" in locals():
        importlib.reload(export_usdz)

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
from bpy.types import (
    Operator,
    OperatorFileListElement,
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

    materials: BoolProperty(
        name="Materials",
        description="Import Materials and textures",
        default=True,
    )
    animations: BoolProperty(
        name="Animations",
        description="Import Animations",
        default=True,
    )

    def execute(self, context):
        from . import import_usdz
        keywords = self.as_keywords(ignore=("filter_glob",))
        return import_usdz.import_usdz(context, **keywords)

    def draw(self, context):
        pass


class USDZ_PT_import_include(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Include"
    bl_parent_id = "FILE_PT_operator"

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator
        return operator.bl_idname == "IMPORT_OT_usdz"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        sfile = context.space_data
        operator = sfile.active_operator

        col = layout.column(heading="Import")

        col.prop(operator, 'materials')
        col.prop(operator, 'animations')


class ExportUSDZ(bpy.types.Operator, ExportHelper):
    """Save a USDZ File"""

    bl_idname = "export.usdz"
    bl_label = "Export USDZ File"
    bl_options = {'PRESET'}

    filename_ext = ".usdz"
    filter_glob: StringProperty(
        default="*.usdz;*.usda;*.usdc",
        options={'HIDDEN'},
    )
    exportMaterials: BoolProperty(
        name="Materials",
        description="Export Materials from Objects",
        default=True,
    )
    exportAnimations: BoolProperty(
        name="Animations",
        description="Export Animations",
        default=False,
    )
    bakeTextures: BoolProperty(
        name="Textures",
        description="Bake Diffuse, Roughness, Normal, etc",
        default=False,
    )
    bakeAO: BoolProperty(
        name="Ambiant Occlusion",
        description="Bake Ambiant Occlusion Texture",
        default=False,
    )
    bakeAOSamples: IntProperty(
        name="AO Samples",
        description="Number of Samples for Ambiant Occlusion",
        min=1,
        max=1000,
        default= 64,
    )
    bakeTextureSize: IntProperty(
        name="Image Size",
        description="Default Size of any Baked Images",
        min=16,
        max=4096,
        default= 1024,
    )
    globalScale: FloatProperty(
        name="Scale",
        min=0.01,
        max=1000.0,
        default=1.0,
    )
    useConverter: BoolProperty(
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

    def draw(self, context):
        pass


class USDZ_PT_export_include(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Include"
    bl_parent_id = "FILE_PT_operator"

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator
        return operator.bl_idname == "EXPORT_OT_usdz"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        sfile = context.space_data
        operator = sfile.active_operator

        col = layout.column(heading="Export")
        col.prop(operator, 'exportMaterials')
        col.prop(operator, 'exportAnimations')
        layout.prop(operator, 'globalScale')


class USDZ_PT_export_textures(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Textures"
    bl_parent_id = "FILE_PT_operator"

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator
        return operator.bl_idname == "EXPORT_OT_usdz"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        sfile = context.space_data
        operator = sfile.active_operator

        col = layout.column(heading="Bake")
        col.prop(operator, 'bakeTextures')
        col.prop(operator, 'bakeAO')

        layout.separator()

        layout.prop(operator, 'bakeTextureSize')
        layout.prop(operator, 'bakeAOSamples')


def menu_func_usdz_import(self, context):
    self.layout.operator(ImportUSDZ.bl_idname, text="USDZ (.usdz)")


def menu_func_usdz_export(self, context):
    self.layout.operator(ExportUSDZ.bl_idname, text="USDZ (.usdz)")


classes = (
    ImportUSDZ,
    USDZ_PT_import_include,
    ExportUSDZ,
    USDZ_PT_export_include,
    USDZ_PT_export_textures,
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
