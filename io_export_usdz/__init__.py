
bl_info = {
    "name":        "USDZ Export",
    "author":      "Robert Crosby",
    "version":     (0, 0, 1),
    "blender":     (2, 79, 0),
    "location":    "File > Export",
    "description": "Export USDZ Files",
    "category":    "Import-Export"
    }

import bpy
from bpy.props import (
        BoolProperty,
        FloatProperty,
        StringProperty,
        EnumProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper,
        orientation_helper_factory,
        path_reference_mode,
        axis_conversion,
        )

from bpy_extras.io_utils import ExportHelper

class ExportUSDZ(bpy.types.Operator, ExportHelper):
    bl_idname       = "export.usdz"
    bl_label        = "Export USDZ File"
    bl_options      = {'PRESET'}

    filename_ext    = ".usdz"

    exportMaterials = BoolProperty(name="Export Materials", description="Export Materials from Objects", default=True)
    keepUSDA = BoolProperty(name="Keep USDA", description="Keep generated USDA and image files", default=False)

    def execute(self, context):
        from . import export_usdz
        keywords = self.as_keywords(ignore=("global_scale",
                                            "check_existing",
                                            "filter_glob",
                                            ))
        return export_usdz.export_usdz(context, **keywords)


def menu_func_usdz_export(self, context):
    self.layout.operator(ExportUSDZ.bl_idname, text="USDZ (.usdz)");

def register():
    bpy.utils.register_module(__name__);
    bpy.types.INFO_MT_file_export.append(menu_func_usdz_export);

def unregister():
    bpy.utils.unregister_module(__name__);
    bpy.types.INFO_MT_file_export.remove(menu_func_usdz_export);

if __name__ == "__main__":
    register()
